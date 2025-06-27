# app/tooling.py
from functools import wraps
from typing import Callable, Dict, Any, List
import json
import asyncio


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
    Si la función es asíncrona, awaita su resultado; de lo contrario, la ejecuta y devuelve el valor.
    """
    try:
        args = json.loads(arguments)
    except Exception:
        args = {}


    if name in TOOL_REGISTRY:
        handler = TOOL_REGISTRY[name]["handler"]
        result = handler(args)
        if asyncio.iscoroutine(result):
            result = await result
        
        # Si hay un callback registrado para esta herramienta, ejecútalo
        if auto_response and name in TOOL_CALLBACKS:
            callback = TOOL_CALLBACKS[name]
            await callback(name, args, result)


        return result
    return f"No se encontró la herramienta: {name}"


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
