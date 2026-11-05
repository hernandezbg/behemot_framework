# behemot_framework/security/abuse_guard.py
"""
Control de abuso por usuario, previo a cualquier llamada que consuma tokens.

Corta mensajes por lista negra, exceso de mensajes, repeticiones exactas e insultos,
y aplica un bloqueo temporal a quien acumula infracciones. Usa Redis si está disponible
y, si no, contadores en memoria (se pierden al reiniciar y no se comparten entre réplicas).

Ante un error del almacenamiento deja pasar el mensaje: un Redis caído no debe dejar
al bot sin responder.
"""
import hashlib
import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_BLOCK_MESSAGE = (
    "Recibimos muchos mensajes seguidos. Esperá unos minutos y volvé a escribirnos."
)

_RATE_WINDOW_SECONDS = 60
_MEMORY_PRUNE_THRESHOLD = 10_000


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    # Texto a enviarle al usuario. None significa ignorar el mensaje en silencio.
    notice: Optional[str] = None
    reason: Optional[str] = None


_ALLOW = GuardDecision(allowed=True)


class _MemoryStore:
    """Almacén con TTL en memoria del proceso, para agentes sin Redis."""

    def __init__(self):
        self._data: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def _read(self, key: str) -> Optional[Any]:
        item = self._data.get(key)
        if item is None:
            return None
        if item[1] <= time.monotonic():
            del self._data[key]
            return None
        return item[0]

    def _write(self, key: str, value: Any, ttl: int) -> None:
        if len(self._data) >= _MEMORY_PRUNE_THRESHOLD:
            now = time.monotonic()
            self._data = {k: v for k, v in self._data.items() if v[1] > now}
        self._data[key] = (value, time.monotonic() + ttl)

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            value = self._read(key)
            return None if value is None else str(value)

    def setex(self, key: str, ttl: int, value: str) -> None:
        with self._lock:
            self._write(key, value, ttl)

    def set_once(self, key: str, ttl: int) -> bool:
        with self._lock:
            if self._read(key) is not None:
                return False
            self._write(key, "1", ttl)
            return True

    def incr(self, key: str, ttl: int) -> int:
        with self._lock:
            current = self._read(key)
            if current is None:
                self._write(key, 1, ttl)
                return 1
            value = int(current) + 1
            # Conserva el vencimiento original: la ventana no se extiende con cada mensaje.
            self._data[key] = (value, self._data[key][1])
            return value


class _RedisStore:
    def __init__(self, client):
        self._client = client

    def get(self, key: str) -> Optional[str]:
        return self._client.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._client.set(key, value, ex=ttl)

    def set_once(self, key: str, ttl: int) -> bool:
        return bool(self._client.set(key, "1", nx=True, ex=ttl))

    def incr(self, key: str, ttl: int) -> int:
        value = int(self._client.incr(key))
        if value == 1:
            self._client.expire(key, ttl)
        return value


def _normalize_words(text: str) -> str:
    """Minúsculas y sin acentos, pero conserva la ñ: "año" no debe coincidir con "ano"."""
    composed = unicodedata.normalize("NFC", text.casefold()).replace("ñ", "\0")
    decomposed = unicodedata.normalize("NFKD", composed)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return plain.replace("\0", "ñ")


def _normalize_user_id(user_id: Any) -> str:
    return str(user_id).strip().lstrip("+")


def _as_list(value: Any) -> list:
    """Acepta una lista de YAML o un texto separado por comas de una variable de entorno."""
    if not value:
        return []
    items: Iterable = value.split(",") if isinstance(value, str) else value
    return [str(item).strip() for item in items if str(item).strip()]


def _as_int(config: dict, key: str, default: int) -> int:
    value = config.get(key)
    if value is None or value == "":
        return default
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        logger.warning("%s inválido (%r); se usa %s", key, value, default)
        return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


class AbuseGuard:
    """Un valor 0 en cualquier límite desactiva solo esa regla."""

    def __init__(
        self,
        redis_client=None,
        enabled: bool = True,
        rate_limit_per_minute: int = 30,
        repeat_max: int = 3,
        repeat_window_seconds: int = 60,
        max_strikes: int = 3,
        strike_window_seconds: int = 3600,
        block_seconds: int = 300,
        block_message: str = DEFAULT_BLOCK_MESSAGE,
        blacklist: Optional[Iterable[Any]] = None,
        insult_words: Optional[Iterable[str]] = None,
    ):
        self.enabled = enabled
        self.rate_limit_per_minute = rate_limit_per_minute
        self.repeat_max = repeat_max
        self.repeat_window_seconds = repeat_window_seconds
        self.max_strikes = max_strikes
        self.strike_window_seconds = strike_window_seconds
        self.block_seconds = block_seconds
        self.block_message = block_message
        self._blacklist = {_normalize_user_id(user) for user in (blacklist or [])}
        self._store = _RedisStore(redis_client) if redis_client is not None else _MemoryStore()
        self._insult_pattern = self._compile_insults(insult_words or [])

        # Una ráfaga cuenta como una sola infracción, no una por cada mensaje.
        self._strike_cooldown = max(_RATE_WINDOW_SECONDS, repeat_window_seconds, 1)
        # El aviso se repite como máximo una vez por incidente.
        self._notice_ttl = max(block_seconds, self._strike_cooldown)

    @classmethod
    def from_config(cls, config: dict, redis_client=None) -> "AbuseGuard":
        return cls(
            redis_client=redis_client,
            enabled=_as_bool(config.get("ABUSE_GUARD_ENABLED", True)),
            rate_limit_per_minute=_as_int(config, "ABUSE_RATE_LIMIT_PER_MINUTE", 30),
            repeat_max=_as_int(config, "ABUSE_REPEAT_MAX", 3),
            repeat_window_seconds=_as_int(config, "ABUSE_REPEAT_WINDOW_SECONDS", 60),
            max_strikes=_as_int(config, "ABUSE_MAX_STRIKES", 3),
            strike_window_seconds=_as_int(config, "ABUSE_STRIKE_WINDOW_SECONDS", 3600),
            block_seconds=_as_int(config, "ABUSE_BLOCK_SECONDS", 300),
            block_message=config.get("ABUSE_BLOCK_MESSAGE") or DEFAULT_BLOCK_MESSAGE,
            blacklist=_as_list(config.get("ABUSE_BLACKLIST")),
            insult_words=_as_list(config.get("ABUSE_INSULT_WORDS")),
        )

    @staticmethod
    def _compile_insults(words: Iterable[str]) -> Optional[re.Pattern]:
        normalized = [_normalize_words(str(word)).strip() for word in words]
        normalized = [re.escape(word) for word in normalized if word]
        if not normalized:
            return None
        return re.compile(r"\b(?:" + "|".join(normalized) + r")\b")

    def check(
        self,
        channel: str,
        user_id: Any,
        text: Optional[str] = None,
        exempt: bool = False,
    ) -> GuardDecision:
        """
        Decide si un mensaje puede seguir su curso.

        Args:
            channel: Canal de origen, para separar contadores ("whatsapp", "telegram"...).
            user_id: Identificador del usuario o chat.
            text: Texto del mensaje. None si aún no se conoce (por ejemplo, audio sin
                transcribir): solo se aplican los controles que no dependen del contenido.
            exempt: Solo aplica la lista negra. Se usa cuando el mensaje no llega al modelo,
                como durante una conversación con un asesor humano.
        """
        if not self.enabled:
            return _ALLOW

        uid = _normalize_user_id(user_id)
        if uid in self._blacklist:
            return self._deny(channel, uid, "lista negra", notify=False)

        # Los comandos con "&" no llaman al modelo y los usan los administradores.
        if exempt or (text and text.lstrip().startswith("&")):
            return _ALLOW

        try:
            return self._evaluate(channel, uid, text)
        except Exception as e:
            logger.error("AbuseGuard: error de almacenamiento, se permite el mensaje: %s", e)
            return _ALLOW

    def _evaluate(self, channel: str, uid: str, text: Optional[str]) -> GuardDecision:
        prefix = f"abuse:{channel}:{uid}"

        if self.block_seconds and self._store.get(f"{prefix}:block"):
            return self._deny(channel, uid, "bloqueo temporal", prefix=prefix)

        # Se cuenta siempre, para que ninguna otra regla deje mensajes fuera del límite.
        over_rate = self._over_rate_limit(prefix)
        repeated = self._is_repeated(prefix, text)
        insulting = self._is_insulting(text)

        if not (over_rate or repeated or insulting):
            return _ALLOW

        reason = "insulto" if insulting else "mensaje repetido" if repeated else "límite de mensajes"
        # Cada insulto es una infracción; las ráfagas cuentan una sola vez.
        self._add_strike(prefix, per_message=insulting)
        return self._deny(channel, uid, reason, prefix=prefix)

    def _over_rate_limit(self, prefix: str) -> bool:
        if not self.rate_limit_per_minute:
            return False
        count = self._store.incr(f"{prefix}:rate", _RATE_WINDOW_SECONDS)
        return count > self.rate_limit_per_minute

    def _is_repeated(self, prefix: str, text: Optional[str]) -> bool:
        """Cuenta repeticiones consecutivas: un texto distinto reinicia el contador."""
        if not self.repeat_max or not self.repeat_window_seconds or not text or not text.strip():
            return False

        normalized = " ".join(text.casefold().split())
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        key = f"{prefix}:repeat"

        last_digest, _, last_count = (self._store.get(key) or "").partition(":")
        count = int(last_count) + 1 if last_digest == digest and last_count else 1
        self._store.setex(key, self.repeat_window_seconds, f"{digest}:{count}")
        return count > self.repeat_max

    def _is_insulting(self, text: Optional[str]) -> bool:
        if self._insult_pattern is None or not text:
            return False
        return bool(self._insult_pattern.search(_normalize_words(text)))

    def _add_strike(self, prefix: str, per_message: bool) -> None:
        if not self.max_strikes or not self.block_seconds or not self.strike_window_seconds:
            return
        if not per_message and not self._store.set_once(f"{prefix}:strike_mark", self._strike_cooldown):
            return
        strikes = self._store.incr(f"{prefix}:strikes", self.strike_window_seconds)
        if strikes >= self.max_strikes:
            self._store.setex(f"{prefix}:block", self.block_seconds, "1")
            logger.warning(
                "AbuseGuard: bloqueo temporal de %ss para %s (%s infracciones)",
                self.block_seconds, prefix, strikes,
            )

    def _deny(
        self,
        channel: str,
        uid: str,
        reason: str,
        prefix: Optional[str] = None,
        notify: bool = True,
    ) -> GuardDecision:
        logger.warning("AbuseGuard: mensaje bloqueado canal=%s usuario=%s motivo=%s", channel, uid, reason)
        notice = None
        if notify and prefix and self._store.set_once(f"{prefix}:notified", self._notice_ttl):
            notice = self.block_message
        return GuardDecision(allowed=False, notice=notice, reason=reason)
