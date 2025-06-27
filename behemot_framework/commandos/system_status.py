# app/commandos/system_status.py
import logging
import time
import os
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Variable para almacenar el tiempo de inicio del framework
BEHEMOT_START_TIME = time.time()

async def check_redis() -> Dict[str, Any]:
    """Verifica el estado de Redis"""
    result = {
        "status": "Desconocido",
        "connected": False,
        "response_time_ms": 0,
        "read_write": "N/A",
        "error": None
    }
    
    try:
        from behemot_framework.context import redis_client
        
        # Verificar conexión
        start_time = time.time()
        response = redis_client.ping()
        response_time = time.time() - start_time
        
        if response:
            result["connected"] = True
            result["response_time_ms"] = round(response_time * 1000, 2)
            result["status"] = "Conectado"
            
            # Test de escritura/lectura
            test_key = f"behemot_status_test_{int(time.time())}"
            redis_client.set(test_key, "test_value", ex=60)
            read_value = redis_client.get(test_key)
            redis_client.delete(test_key)
            
            if read_value == "test_value":
                result["read_write"] = "OK"
            else:
                result["read_write"] = "Error"
                result["error"] = "Prueba de lectura/escritura falló"
        else:
            result["status"] = "Error"
            result["error"] = "Redis no respondió al ping"
    
    except Exception as e:
        result["status"] = "Error"
        result["error"] = str(e)
    
    return result

async def check_rag() -> Dict[str, Any]:
    """Verifica el estado del sistema RAG"""
    result = {
        "status": "Desconocido",
        "enabled": False,
        "embedding_provider": "N/A",
        "embedding_model": "N/A",
        "collections": [],
        "error": None
    }
    
    try:
        # Importar componentes RAG
        try:
            from behemot_framework.rag.rag_manager import RAGManager
            RAG_AVAILABLE = True
        except ImportError:
            RAG_AVAILABLE = False
            result["status"] = "No disponible"
            result["error"] = "Módulos RAG no están disponibles"
            return result
        
        from behemot_framework.config import Config
        config = Config.get_config()
        
        # Verificar configuración de RAG
        rag_enabled = config.get("ENABLE_RAG", False)
        rag_folders = config.get("RAG_FOLDERS", [])
        has_folders = len(rag_folders) > 0
        
        if not rag_enabled and not has_folders:
            result["status"] = "Deshabilitado"
            return result
        
        # RAG está habilitado o hay carpetas configuradas
        result["enabled"] = True
        result["embedding_provider"] = config.get("RAG_EMBEDDING_PROVIDER", "openai")
        result["embedding_model"] = config.get("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
        
        # Verificar colecciones
        collections = []
        for folder in rag_folders:
            try:
                pipeline = RAGManager.get_pipeline(folder)
                collections.append({
                    "name": folder if folder else "default",
                    "initialized": pipeline.vectorstore is not None
                })
            except Exception as e:
                collections.append({
                    "name": folder if folder else "default",
                    "initialized": False,
                    "error": str(e)
                })
        
        result["collections"] = collections
        
        # Verificar si alguna colección está inicializada
        initialized = any(c.get("initialized", False) for c in collections)
        if initialized:
            result["status"] = "Disponible"
        else:
            result["status"] = "No inicializado"
            result["error"] = "Ninguna colección está inicializada"
    
    except Exception as e:
        result["status"] = "Error"
        result["error"] = str(e)
    
    return result

def check_model() -> Dict[str, Any]:
    """Verifica el estado del modelo de IA"""
    result = {
        "status": "Configurado",
        "model_name": "gpt-4o-mini",
        "api_key_status": "Válida",
        "temperature": 0.7,
        "max_tokens": 150,
        "error": None
    }
    
    try:
        from behemot_framework.config import Config
        config = Config.get_config()
        
        # Información básica
        result["model_name"] = config.get("MODEL_NAME", "gpt-4o-mini")
        result["temperature"] = config.get("MODEL_TEMPERATURE", 0.7)
        result["max_tokens"] = config.get("MODEL_MAX_TOKENS", 150)
        
        # Verificar API key
        api_key = config.get("GPT_API_KEY", "")
        if not api_key:
            result["status"] = "API Key faltante"
            result["api_key_status"] = "No configurada"
        elif len(api_key) < 20:
            result["status"] = "API Key inválida"
            result["api_key_status"] = "Formato incorrecto"
        else:
            # Enmascarar la API key
            result["api_key_status"] = f"{''*(len(api_key)-8)}{api_key[-4:]}" if len(api_key) > 8 else "Configurada"
    
    except Exception as e:
        result["status"] = "Error"
        result["error"] = str(e)
    
    return result

def check_config() -> Dict[str, Any]:
    """Verifica la configuración"""
    result = {
        "status": "Cargada",
        "version": "1.0.0",
        "assistant_name": "Behemot",
        "model": "gpt-4o-mini",
        "safety_level": "medium",
        "error": None
    }
    
    try:
        from behemot_framework.config import Config
        config = Config.get_config()
        
        # Información básica
        result["version"] = config.get("VERSION", "1.0.0")
        result["assistant_name"] = config.get("ASSISTANT_NAME", "Behemot")
        result["model"] = config.get("MODEL_NAME", "gpt-4o-mini")
        result["safety_level"] = config.get("SAFETY_LEVEL", "medium")
        result["config_path"] = config.get("_config_path", "Por defecto")
        
        # Verificar valores clave
        required_keys = ["GPT_API_KEY", "PROMPT_SISTEMA"]
        missing_keys = [key for key in required_keys if not config.get(key)]
        
        if missing_keys:
            result["status"] = "Incompleta"
            result["error"] = f"Faltan configuraciones: {', '.join(missing_keys)}"
    
    except Exception as e:
        result["status"] = "Error"
        result["error"] = str(e)
    
    return result

def check_tools() -> Dict[str, Any]:
    """Verifica las herramientas disponibles"""
    result = {
        "status": "Disponibles",
        "count": 0,
        "tools": [],
        "rag_tools": [],
        "error": None
    }
    
    try:
        from behemot_framework.tooling import get_tool_definitions
        tools = get_tool_definitions()
        result["count"] = len(tools)
        
        # Clasificar herramientas
        rag_tools = []
        regular_tools = []
        
        rag_keywords = ["search", "buscar", "document", "rag", "retriev", "query"]
        
        for tool in tools:
            tool_name = tool.get("name", "").lower()
            description = tool.get("description", "").lower()
            
            # Determinar si es una herramienta RAG
            is_rag_tool = any(keyword in tool_name or keyword in description for keyword in rag_keywords)
            
            # Formatear información
            tool_info = {
                "name": tool.get("name", ""),
                "description": tool.get("description", "")
            }
            
            # Añadir a la categoría correspondiente
            if is_rag_tool:
                rag_tools.append(tool_info)
            else:
                regular_tools.append(tool_info)
        
        # Actualizar resultado
        result["tools"] = regular_tools
        result["rag_tools"] = rag_tools
        
        # Verificar si hay herramientas
        if not tools:
            result["status"] = "Sin herramientas"
    
    except Exception as e:
        result["status"] = "Error"
        result["error"] = str(e)
    
    return result

def get_memory_usage() -> float:
    """Obtiene el uso de memoria en MB"""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        return round(memory_info.rss / (1024 * 1024), 2)  # Convertir a MB
    except ImportError:
        return 0.0

def get_performance_metrics() -> Dict[str, Any]:
    """Obtiene métricas de rendimiento"""
    result = {
        "check_time_ms": 0,
        "memory_usage": get_memory_usage(),
        "startup_time": 0
    }
    
    # Obtener tiempo desde el inicio
    if 'BEHEMOT_START_TIME' in globals():
        result["startup_time"] = round(time.time() - BEHEMOT_START_TIME, 2)
    
    return result
