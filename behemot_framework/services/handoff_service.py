"""
Servicio de Human Handoff para behemot_framework.

Cuando un usuario solicita hablar con un humano, este servicio:
1. Registra la sesión en behemot.net (o cualquier endpoint compatible)
2. Pausa el bot para ese usuario (flag en Redis)
3. Reenvía mensajes del usuario al asesor mientras dure el handoff
4. Retoma el bot cuando el asesor cierra la conversación

Habilitado cuando HANDOFF_API_KEY y HANDOFF_WEBHOOK_URL están configuradas.
Todo es no-op si no están configuradas.
"""
import hmac
import hashlib
import json
import logging
from typing import Optional, Dict

import requests

logger = logging.getLogger(__name__)

_api_key = ""
_webhook_url = ""
_enabled = False
_redis_client = None


def init_handoff(api_key: str, webhook_url: str) -> bool:
    """Inicializa el servicio. Llamar una vez en create_behemot_app()."""
    global _api_key, _webhook_url, _enabled
    if not api_key or not webhook_url:
        return False
    _api_key = api_key
    _webhook_url = webhook_url.rstrip("/") + "/"
    _enabled = True
    logger.info("Handoff service inicializado (url=%s)", _webhook_url)
    return True


def is_enabled() -> bool:
    return _enabled


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------

def _redis():
    global _redis_client
    if _redis_client is None:
        try:
            from behemot_framework.context import redis_client
            _redis_client = redis_client
        except Exception:
            pass
    return _redis_client


def is_in_handoff(user_id: str) -> bool:
    r = _redis()
    if r is None:
        return False
    return bool(r.exists(f"handoff:{user_id}"))


def get_handoff_data(user_id: str) -> Optional[Dict]:
    r = _redis()
    if r is None:
        return None
    raw = r.get(f"handoff:{user_id}")
    return json.loads(raw) if raw else None


def _set_handoff(user_id: str, session_id: str, channel: str, ttl: int = 86400) -> None:
    r = _redis()
    if r is None:
        logger.warning("Redis no disponible — estado handoff no persistido para %s", user_id)
        return
    data = json.dumps({"session_id": session_id, "channel": channel})
    r.setex(f"handoff:{user_id}", ttl, data)
    # reverse mapping: session_id → user_id (para el webhook de retorno)
    r.setex(f"handoff_session:{session_id}", ttl, user_id)


def clear_handoff(user_id: str) -> None:
    r = _redis()
    if r is None:
        return
    data = get_handoff_data(user_id)
    if data:
        r.delete(f"handoff_session:{data['session_id']}")
    r.delete(f"handoff:{user_id}")


def get_user_id_by_session(session_id: str) -> Optional[str]:
    """Retorna el user_id asociado a un session_id (para el webhook de retorno)."""
    r = _redis()
    if r is None:
        return None
    raw = r.get(f"handoff_session:{session_id}")
    return raw.decode() if isinstance(raw, bytes) else raw


# ---------------------------------------------------------------------------
# API calls a behemot.net
# ---------------------------------------------------------------------------

def _headers() -> Dict:
    return {
        "Authorization": f"Bearer {_api_key}",
        "Content-Type": "application/json",
    }


def start_handoff(
    channel: str,
    user_id: str,
    user_name: str,
    framework_webhook_url: str,
    history: list,
) -> Optional[str]:
    """
    Registra una nueva sesión de handoff en behemot.net.
    Retorna el session_id o None si falla.
    """
    if not _enabled:
        return None
    try:
        payload = {
            "channel": channel,
            "user_id": user_id,
            "user_name": user_name or "",
            "framework_webhook_url": framework_webhook_url,
            "history": history,
        }
        resp = requests.post(
            f"{_webhook_url}start/",
            json=payload,
            headers=_headers(),
            timeout=10,
        )
        if resp.ok:
            session_id = resp.json().get("session_id")
            _set_handoff(user_id, session_id, channel)
            logger.info("Handoff iniciado: session=%s user=%s", session_id, user_id)
            return session_id
        logger.error("Error iniciando handoff: %s %s", resp.status_code, resp.text)
        return None
    except Exception as e:
        logger.error("Excepción iniciando handoff: %s", e)
        return None


def forward_message(user_id: str, content: str) -> bool:
    """Reenvía un mensaje del usuario al asesor mientras el handoff está activo."""
    if not _enabled:
        return False
    data = get_handoff_data(user_id)
    if not data:
        return False
    session_id = data["session_id"]
    try:
        resp = requests.post(
            f"{_webhook_url}{session_id}/message/",
            json={"content": content},
            headers=_headers(),
            timeout=10,
        )
        if resp.ok:
            return True
        logger.error("Error reenviando mensaje handoff: %s", resp.text)
        # Sesión cerrada en behemot.net → limpiar flag local
        if resp.status_code in (404, 409):
            clear_handoff(user_id)
        return False
    except Exception as e:
        logger.error("Excepción reenviando mensaje: %s", e)
        return False


def end_handoff_local(user_id: str, reason: str = "bot_retake") -> bool:
    """Cierra el handoff desde el lado del framework y notifica a behemot.net."""
    if not _enabled:
        return False
    data = get_handoff_data(user_id)
    if not data:
        return False
    session_id = data["session_id"]
    try:
        requests.post(
            f"{_webhook_url}{session_id}/end/",
            json={"reason": reason},
            headers=_headers(),
            timeout=10,
        )
    except Exception as e:
        logger.error("Excepción cerrando handoff en behemot.net: %s", e)
    finally:
        clear_handoff(user_id)
    return True


# ---------------------------------------------------------------------------
# Trigger detection
# ---------------------------------------------------------------------------

def is_trigger(text: str, phrases: list) -> bool:
    """Retorna True si el texto contiene alguna de las frases de activación."""
    text_lower = text.lower()
    return any(phrase.lower() in text_lower for phrase in phrases)


# ---------------------------------------------------------------------------
# Signature verification (webhooks entrantes de behemot.net)
# ---------------------------------------------------------------------------

def verify_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    """
    Verifica la firma HMAC-SHA256 del webhook entrante.
    Si secret está vacío, acepta todo (solo para desarrollo).
    """
    if not secret:
        logger.warning("HANDOFF_WEBHOOK_SECRET no configurado — firma no verificada")
        return True
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)


# ---------------------------------------------------------------------------
# Utilidad: construir historial para el /start
# ---------------------------------------------------------------------------

def build_history(chat_id: str, max_messages: int = 20) -> list:
    """
    Construye el historial de conversación a enviar en el /start.
    Toma los últimos `max_messages` mensajes, excluyendo los del sistema.
    """
    try:
        from behemot_framework.context import get_conversation
        conv = get_conversation(chat_id)
        history = []
        for msg in conv:
            role = msg.get("role")
            if role == "user":
                history.append({"role": "user", "content": msg.get("content", "")})
            elif role == "assistant":
                history.append({"role": "assistant", "content": msg.get("content", "")})
        return history[-max_messages:]
    except Exception as e:
        logger.warning("No se pudo construir historial para handoff: %s", e)
        return []
