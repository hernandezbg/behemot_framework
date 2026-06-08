"""
Servicio de observabilidad con Langfuse.

Habilitado cuando LANGFUSE_SECRET_KEY y LANGFUSE_PUBLIC_KEY están configuradas.
Todas las funciones son no-op si Langfuse no está inicializado, por lo que
no hay impacto en deploys que no usen observabilidad.
"""
import logging
import contextvars
from typing import Optional, Any, Dict, List

logger = logging.getLogger(__name__)

_langfuse = None
_enabled = False

# Trace activo en el contexto async actual (safe para FastAPI)
_current_trace: contextvars.ContextVar = contextvars.ContextVar(
    "langfuse_trace", default=None
)


def init_observability(
    secret_key: str,
    public_key: str,
    host: str = "https://cloud.langfuse.com",
) -> bool:
    """
    Inicializa el cliente Langfuse. Retorna True si tuvo éxito.
    Llamar una vez en create_behemot_app() cuando las claves están configuradas.
    """
    global _langfuse, _enabled
    if not secret_key or not public_key:
        return False
    try:
        from langfuse import Langfuse
        _langfuse = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        _enabled = True
        logger.info("Langfuse observability enabled (host=%s)", host)
        return True
    except ImportError:
        logger.warning(
            "langfuse no instalado — observabilidad deshabilitada. "
            "Instalar con: pip install behemot-framework[observability]"
        )
        return False
    except Exception as e:
        logger.error("Error inicializando Langfuse: %s", e)
        return False


def is_enabled() -> bool:
    return _enabled


def start_trace(
    name: str,
    user_id: str,
    input_data: Any,
    metadata: Optional[Dict] = None,
):
    """
    Inicia un nuevo trace y lo deja activo en el contexto async.
    Retorna el objeto trace o None si observabilidad está deshabilitada.
    """
    if not _enabled or _langfuse is None:
        return None
    try:
        trace = _langfuse.trace(
            name=name,
            user_id=str(user_id),
            input=input_data,
            metadata=metadata or {},
        )
        _current_trace.set(trace)
        return trace
    except Exception as e:
        logger.debug("Langfuse start_trace error: %s", e)
        return None


def end_trace(trace, output: Any) -> None:
    """Cierra el trace con el output final y hace flush."""
    if not _enabled or trace is None:
        return
    try:
        trace.update(output=output)
        _langfuse.flush()
    except Exception as e:
        logger.debug("Langfuse end_trace error: %s", e)
    finally:
        _current_trace.set(None)


def get_current_trace():
    """Retorna el trace activo en este contexto async, o None."""
    return _current_trace.get(None)


def record_generation(
    trace,
    name: str,
    model: str,
    input_messages: List[Dict],
    output: str,
    usage: Optional[Dict] = None,
) -> None:
    """
    Registra una llamada al LLM dentro del trace activo.
    `usage` debe tener claves "input" (prompt tokens) y "output" (completion tokens).
    """
    if not _enabled or trace is None:
        return
    try:
        kwargs: Dict[str, Any] = dict(
            name=name,
            model=model,
            input=input_messages,
            output=output,
        )
        if usage:
            kwargs["usage"] = usage
        trace.generation(**kwargs)
    except Exception as e:
        logger.debug("Langfuse record_generation error: %s", e)


def record_tool_span(name: str, input_data: Any, output: Any) -> None:
    """
    Registra una tool call como span dentro del trace activo en el contexto.
    No-op si no hay trace activo o si observabilidad está deshabilitada.
    """
    if not _enabled:
        return
    trace = get_current_trace()
    if trace is None:
        return
    try:
        span = trace.span(name=f"tool:{name}", input=input_data)
        span.end(output=str(output)[:2000])  # truncar para evitar payloads enormes
    except Exception as e:
        logger.debug("Langfuse record_tool_span error: %s", e)
