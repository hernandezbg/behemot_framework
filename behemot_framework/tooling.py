# app/tooling.py
from functools import wraps
from typing import Callable, Dict, Any, List, Optional
import inspect
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

# jsonschema es opcional: si está disponible validamos los argumentos del LLM
# contra el schema declarado en el decorador @tool antes de ejecutar el handler.
# Esto cierra una vía de tool poisoning detectada en la auditoría: un LLM
# secuestrado por prompt injection podía llamar tools con argumentos fuera de
# spec y el handler los recibía sin validar.
try:
    from jsonschema import validate as _jsonschema_validate, ValidationError as _JsonSchemaError
    _JSONSCHEMA_AVAILABLE = True
except Exception:  # pragma: no cover
    _JSONSCHEMA_AVAILABLE = False


class ToolContext:
    """
    Contexto de sesión inyectado como primer argumento (`agente`) en tools que
    lo declaran explícitamente.

    Atributos disponibles según el canal:
      - phone_number        : número o ID del usuario que disparó la conversación
      - whatsapp_connector  : instancia de WhatsAppConnector (solo canal whatsapp)
    """
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _handler_wants_agente(handler: Callable) -> bool:
    """True si el primer parámetro del handler se llama 'agente'."""
    try:
        params = list(inspect.signature(handler).parameters.keys())
        return bool(params) and params[0] == "agente"
    except (ValueError, TypeError):
        return False


# Variable global para registrar callbacks de herramientas
TOOL_CALLBACKS = {}


def register_auto_response_handler(tool_name: str, handler: Callable):
    """Registra un callback para cuando se ejecuta una herramienta específica"""
    TOOL_CALLBACKS[tool_name] = handler




# Registro global de herramientas
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}

class Param:
    def __init__(self, name: str, type_: str, description: str, required: bool = False):
        self.name = name
        self.type = type_
        self.description = description
        self.required = required

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "description": self.description}

def tool(name: str, description: str, params: List[Param] = []):
    """
    Decorador para registrar una herramienta.

    La función decorada debe aceptar un único argumento posicional `args: dict`
    que contendrá todos los parámetros que el LLM pasó a la tool. No usar
    parámetros individuales — call_tool siempre llama handler(args_dict).

    Ejemplo::

        @tool("buscar", "Busca algo", [Param("query", "string", "Texto", required=True)])
        async def buscar(args: dict):
            query = args["query"]
            return f"Resultado para: {query}"
    """
    def decorator(func: Callable):
        # Construir el esquema de parámetros en formato JSON Schema
        param_schema = {
            "type": "object",
            "properties": {p.name: p.to_dict() for p in params},
            "required": [p.name for p in params if p.required],
            "additionalProperties": False
        }
        TOOL_REGISTRY[name] = {
            "name": name,
            "description": description,
            "parameters": param_schema,
            "handler": func
        }
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Retorna una lista de definiciones de herramientas para pasar al modelo.
    """
    return [
        {
            "name": tool_info["name"],
            "description": tool_info["description"],
            "parameters": tool_info["parameters"]
        }
        for tool_info in TOOL_REGISTRY.values()
    ]

async def call_tool(
    name: str,
    arguments: str,
    auto_response: bool = True,
    session_context: Optional[dict] = None,
) -> str:
    """
    Llama a la herramienta registrada de forma asíncrona.
    Si la función es asíncrona, awaita su resultado; de lo contrario, la
    ejecuta y devuelve el valor.

    Antes de invocar el handler, valida `arguments` contra el JSON Schema
    declarado al registrar la tool. Argumentos inválidos se rechazan sin
    ejecutar la tool — esto evita tool poisoning vía prompt injection.

    Si `session_context` está presente y el handler declara `agente` como
    primer parámetro, se construye un ToolContext y se inyecta automáticamente:
        handler(agente, args)   ← con contexto
        handler(args)           ← sin contexto (comportamiento anterior)
    """
    try:
        args = json.loads(arguments) if arguments else {}
    except Exception as e:
        logger.warning(f"[tool:{name}] argumentos no son JSON válido: {e}")
        return f"Error: argumentos para '{name}' no son JSON válido"

    if name not in TOOL_REGISTRY:
        return f"No se encontró la herramienta: {name}"

    tool_info = TOOL_REGISTRY[name]

    # Validación de argumentos contra el schema declarado.
    if _JSONSCHEMA_AVAILABLE:
        try:
            _jsonschema_validate(instance=args, schema=tool_info["parameters"])
        except _JsonSchemaError as e:
            logger.warning(
                f"[tool:{name}] argumentos rechazados por schema: {e.message}"
            )
            # Devolver al LLM un error estructurado: corregirá la siguiente llamada.
            return (
                f"Error: los argumentos para '{name}' no cumplen el schema. "
                f"Detalle: {e.message}"
            )
    else:
        logger.debug(
            "jsonschema no instalado — validación de argumentos de tools deshabilitada"
        )

    handler = tool_info["handler"]
    if session_context and _handler_wants_agente(handler):
        agente = ToolContext(**session_context)
        result = handler(agente, args)
    else:
        result = handler(args)
    if asyncio.iscoroutine(result):
        result = await result

    # Observability: registrar la tool call en el trace activo (no-op si no hay trace)
    from behemot_framework.services.observability import record_tool_span
    record_tool_span(name, args, result)

    # Si hay un callback registrado para esta herramienta, ejecútalo
    if auto_response and name in TOOL_CALLBACKS:
        callback = TOOL_CALLBACKS[name]
        await callback(name, args, result)

    return result


def get_tool_handler(name: str) -> Callable:
    """
    Retorna el handler de una herramienta registrada.
    """
    return TOOL_REGISTRY.get(name, {}).get("handler")

def get_tool_names() -> List[str]:
    """
    Retorna una lista de los nombres de todas las herramientas registradas.
    """
    return list(TOOL_REGISTRY.keys())
