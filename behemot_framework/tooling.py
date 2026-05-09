# app/tooling.py
from functools import wraps
from typing import Callable, Dict, Any, List
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

async def call_tool(name: str, arguments: str, auto_response: bool = True) -> str:
    """
    Llama a la herramienta registrada de forma asíncrona.
    Si la función es asíncrona, awaita su resultado; de lo contrario, la
    ejecuta y devuelve el valor.

    Antes de invocar el handler, valida `arguments` contra el JSON Schema
    declarado al registrar la tool. Argumentos inválidos se rechazan sin
    ejecutar la tool — esto evita tool poisoning vía prompt injection.
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
    result = handler(args)
    if asyncio.iscoroutine(result):
        result = await result

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
