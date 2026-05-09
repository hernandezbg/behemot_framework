# app/utils/logger.py
import logging
import re
from typing import Optional

# Configuración básica del logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Obtener un logger para el módulo actual
logger = logging.getLogger(__name__)


def mask_secret(value: Optional[str], visible: int = 0) -> str:
    """
    Devuelve una representación segura de un secreto para logs.

    Por defecto enmascara TODO el valor. Si `visible` > 0, deja visibles los
    primeros `visible` caracteres (útil solo en niveles DEBUG/dev). Nunca uses
    `visible` con valores cortos: tokens cortos no deben revelar entropía.

    Args:
        value: Secreto a enmascarar (api key, token, etc.).
        visible: Número de caracteres iniciales que se mantienen visibles.

    Returns:
        Cadena enmascarada segura para incluir en logs.
    """
    if not value:
        return "<empty>"
    if visible <= 0 or len(value) <= visible * 2:
        return "***"
    return f"{value[:visible]}***"


# Patrones de secretos comunes que el filtro neutraliza si aparecen literales en logs
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),                # OpenAI / Anthropic-like
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{16,}", re.IGNORECASE),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),               # Google API keys
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),                  # GitHub PAT
    re.compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}"),         # Slack tokens
    re.compile(r"\b\d{6,}:[A-Za-z0-9_\-]{20,}\b"),        # Telegram bot tokens
]


# Patrones de PII enmascarados según LOG_REDACT_PII (default true).
# Cubre: emails, teléfonos internacionales, tokens largos opacos.
_PII_PATTERNS = [
    re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),  # email
    re.compile(r"\+\d{8,15}\b"),                                       # phone E.164
    re.compile(r"\b[A-Za-z0-9_\-]{40,}\b"),                            # tokens/IDs largos
]


def _redact_pii_enabled() -> bool:
    """Lee la preferencia desde env. Default seguro: true."""
    val = os.getenv("LOG_REDACT_PII", "true").strip().lower()
    return val not in ("false", "0", "no", "off")


# os es necesario para el helper anterior
import os  # noqa: E402


class SecretRedactionFilter(logging.Filter):
    """Filtro defensivo: redacta secretos y opcionalmente PII en logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = msg
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub("***", redacted)
        if _redact_pii_enabled():
            for pattern in _PII_PATTERNS:
                redacted = pattern.sub("<redacted>", redacted)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


# Aplicar el filtro a todos los handlers del root logger.
# Es defensa en profundidad — el primer mecanismo es no loguear secretos en absoluto.
for _handler in logging.getLogger().handlers:
    _handler.addFilter(SecretRedactionFilter())


# Ejemplo de uso:
# from behemot_framework.utils.logger import logger, mask_secret
# logger.info("API key cargada: %s", mask_secret(api_key))
