# app/routes/status.py
import hmac
import os
import re
import time
import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from behemot_framework.config import Config
from behemot_framework.tooling import get_tool_definitions

# Cualquier variable cuyo nombre matchee esta regex no se incluye nunca en la
# respuesta de /status (defensa en profundidad junto al enmascaramiento).
_SENSITIVE_VAR_PATTERN = re.compile(
    r"(KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL|PRIVATE)", re.IGNORECASE
)


def _require_status_auth(request: Request) -> None:
    """
    Exige Bearer token si STATUS_API_TOKEN está configurado.

    Si no hay token configurado, /status queda accesible — el operador es
    responsable de protegerlo a nivel de red (firewall/proxy). Loguemos un
    warning visible al servir la primera petición sin token.
    """
    expected = Config.get("STATUS_API_TOKEN", "") or ""
    if not expected:
        # No hay auth configurada; permitir pero advertir una vez.
        if not getattr(_require_status_auth, "_warned", False):
            logger.warning(
                "STATUS_API_TOKEN no configurado: /status queda accesible sin "
                "autenticación. Configúralo o restringe el endpoint a nivel de red."
            )
            _require_status_auth._warned = True
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    received = auth_header[len("Bearer "):]
    if not hmac.compare_digest(received, expected):
        raise HTTPException(status_code=401, detail="Invalid token")

# Variable global para almacenar la ruta de configuración
CONFIG_PATH = None

# Variable global para almacenar el tiempo de inicio
BEHEMOT_START_TIME = None

# Intentar importar componentes opcionales
try:
    import redis
    from behemot_framework.context import redis_client
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from behemot_framework.rag.rag_manager import RAGManager
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# Configurar logging
logger = logging.getLogger(__name__)

# Crear router
router = APIRouter()

# Configurar templates (será configurado durante la inicialización)
templates = None

def load_app_config():
    """Carga la configuración usando la misma ruta que la aplicación principal"""
    return Config.get_config()

def initialize_templates(directory="templates"):
    """Inicializa los templates para las respuestas HTML"""
    global templates
    
    # Crear directorio de templates si no existe
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
            # Crear archivo de template
            template_path = os.path.join(directory, "status.html")
            with open(template_path, "w") as f:
                f.write(STATUS_TEMPLATE)
        except Exception as e:
            logger.warning(f"No se pudo crear directorio de templates: {e}")
    
    # Inicializar Jinja2Templates
    try:
        templates = Jinja2Templates(directory=directory)
    except Exception as e:
        logger.error(f"Error al inicializar templates: {e}")
        templates = None

async def check_redis() -> Dict[str, Any]:
    """Verifica el estado de Redis"""
    result = {
        "status": "Desconocido",
        "connected": False,
        "icon": "❓",
        "icon_class": "status-disabled",
        "error": None,
        "response_time_ms": 0,
        "read_write": "N/A"
    }
    
    if not REDIS_AVAILABLE:
        result["status"] = "Deshabilitado"
        result["error"] = "Módulo redis no disponible"
        return result
    
    config = load_app_config()
    redis_url = config.get("REDIS_PUBLIC_URL")
    
    if not redis_url:
        result["status"] = "Deshabilitado"
        result["error"] = "REDIS_PUBLIC_URL no configurado"
        return result
    
    try:
        # Usar cliente existente o crear uno nuevo
        client = redis_client if "redis_client" in globals() else redis.from_url(redis_url, decode_responses=True)
        
        # Verificar conexión
        start_time = time.time()
        response = client.ping()
        response_time = time.time() - start_time
        
        if response:
            result["connected"] = True
            result["response_time_ms"] = round(response_time * 1000, 2)
            result["status"] = "Conectado"
            result["icon"] = "✅"
            result["icon_class"] = "status-ok"
            
            # Test de escritura/lectura
            test_key = f"behemot_status_test_{int(time.time())}"
            client.set(test_key, "test_value", ex=60)
            read_value = client.get(test_key)
            client.delete(test_key)
            
            if read_value == "test_value":
                result["read_write"] = "OK"
            else:
                result["read_write"] = "Error"
                result["icon"] = "⚠️"
                result["icon_class"] = "status-warning"
                result["error"] = "Prueba de lectura/escritura falló"
        else:
            result["status"] = "Error"
            result["icon"] = "❌"
            result["icon_class"] = "status-error"
            result["error"] = "Redis no respondió al ping"
    
    except Exception as e:
        result["status"] = "Error"
        result["icon"] = "❌"
        result["icon_class"] = "status-error"
        result["error"] = str(e)
    
    return result

async def check_rag() -> Dict[str, Any]:
    """Verifica el estado del sistema RAG"""
    result = {
        "status": "Desconocido",
        "enabled": False,
        "icon": "❓",
        "icon_class": "status-disabled",
        "error": None,
        "embedding_provider": "N/A",
        "embedding_model": "N/A",
        "collections": [],
        "config_path": CONFIG_PATH
    }
    
    if not RAG_AVAILABLE:
        result["status"] = "No disponible"
        result["error"] = "Módulos RAG no están disponibles"
        return result
    
    config = load_app_config()
    
    # Verificar configuración de RAG
    rag_enabled = config.get("ENABLE_RAG", False)
    rag_folders = config.get("RAG_FOLDERS", [])
    has_folders = len(rag_folders) > 0
    
    if not rag_enabled and not has_folders:
        result["status"] = "Deshabilitado"
        result["icon"] = "💤"
        result["icon_class"] = "status-disabled"
        return result
    
    # RAG está habilitado o hay carpetas configuradas
    result["enabled"] = True
    result["embedding_provider"] = config.get("RAG_EMBEDDING_PROVIDER", "openai")
    result["embedding_model"] = config.get("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Verificar colecciones
    try:
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
            result["icon"] = "✅"
            result["icon_class"] = "status-ok"
        else:
            result["status"] = "No inicializado"
            result["icon"] = "⚠️"
            result["icon_class"] = "status-warning"
            result["error"] = "Ninguna colección está inicializada"
    
    except Exception as e:
        result["status"] = "Error"
        result["icon"] = "❌"
        result["icon_class"] = "status-error"
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
        "icon": "✅",
        "icon_class": "status-ok",
        "error": None,
        "env_vars": {},
        "config_path": CONFIG_PATH or "Por defecto"
    }
    
    try:
        config = load_app_config()
        
        # Información básica
        result["version"] = config.get("VERSION", "1.0.0")
        result["assistant_name"] = config.get("ASSISTANT_NAME", "Behemot")
        result["model"] = config.get("MODEL_NAME", "gpt-4o-mini")
        result["safety_level"] = config.get("SAFETY_LEVEL", "medium")
        
        # Verificar valores clave
        required_keys = ["GPT_API_KEY", "PROMPT_SISTEMA"]
        missing_keys = [key for key in required_keys if not config.get(key)]
        
        if missing_keys:
            result["status"] = "Incompleta"
            result["icon"] = "⚠️"
            result["icon_class"] = "status-warning"
            result["error"] = f"Faltan configuraciones: {', '.join(missing_keys)}"
        
        # Variables de entorno relevantes (filtradas y seguras).
        # Cualquier variable cuyo nombre matchee _SENSITIVE_VAR_PATTERN NO se
        # expone en /status — solo se indica si está configurada o no, sin
        # revelar ni siquiera los primeros/últimos caracteres del valor.
        relevant_prefixes = ["GPT_", "OPENAI_", "REDIS_", "TELEGRAM_", "RAG_", "GS_"]

        for key, value in os.environ.items():
            if not any(key.startswith(prefix) for prefix in relevant_prefixes):
                continue

            if _SENSITIVE_VAR_PATTERN.search(key):
                # Solo indicar si está configurada; nunca el valor ni un prefijo.
                result["env_vars"][key] = "<configured>" if value else "<not set>"
            else:
                if value and len(value) > 50:
                    result["env_vars"][key] = value[:50] + "..."
                else:
                    result["env_vars"][key] = value
    
    except Exception as e:
        result["status"] = "Error"
        result["icon"] = "❌"
        result["icon_class"] = "status-error"
        result["error"] = str(e)
    
    return result

def check_tools() -> Dict[str, Any]:
    """Verifica las herramientas disponibles"""
    result = {
        "status": "Disponibles",
        "count": 0,
        "tools": [],
        "rag_tools": [],
        "icon": "✅",
        "icon_class": "status-ok",
        "error": None
    }
    
    try:
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
                "description": tool.get("description", "")[:100] + "..." if len(tool.get("description", "")) > 100 else tool.get("description", "")
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
            result["icon"] = "⚠️"
            result["icon_class"] = "status-warning"
    
    except Exception as e:
        result["status"] = "Error"
        result["icon"] = "❌"
        result["icon_class"] = "status-error"
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
        "icon": "✅",
        "icon_class": "status-ok",
        "error": None
    }
    
    try:
        config = load_app_config()
        
        # Información básica
        result["model_name"] = config.get("MODEL_NAME", "gpt-4o-mini")
        result["temperature"] = config.get("MODEL_TEMPERATURE", 0.7)
        result["max_tokens"] = config.get("MODEL_MAX_TOKENS", 150)
        
        # Verificar API key (sin revelar ningún carácter del valor).
        api_key = config.get("GPT_API_KEY", "")
        if not api_key:
            result["status"] = "API Key faltante"
            result["api_key_status"] = "No configurada"
            result["icon"] = "❌"
            result["icon_class"] = "status-error"
        elif len(api_key) < 20:
            result["status"] = "API Key inválida"
            result["api_key_status"] = "Formato incorrecto"
            result["icon"] = "⚠️"
            result["icon_class"] = "status-warning"
        else:
            # No exponer prefijos/sufijos del secreto: revelan entropía del token.
            result["api_key_status"] = "Configurada"
    
    except Exception as e:
        result["status"] = "Error"
        result["icon"] = "❌"
        result["icon_class"] = "status-error"
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
    if BEHEMOT_START_TIME is not None:
        result["startup_time"] = round(time.time() - BEHEMOT_START_TIME, 2)
    
    return result

def determine_overall_status(checks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Determina el estado general del sistema"""
    # Contar estados por tipo
    error_count = sum(1 for check in checks.values() if check.get("icon_class") == "status-error")
    warning_count = sum(1 for check in checks.values() if check.get("icon_class") == "status-warning")
    
    if error_count > 0:
        return {
            "status": "Problemas Críticos",
            "icon": "❌",
            "class": "status-error"
        }
    elif warning_count > 0:
        return {
            "status": "Advertencias",
            "icon": "⚠️",
            "class": "status-warning"
        }
    else:
        return {
            "status": "Operativo",
            "icon": "✅",
            "class": "status-ok"
        }

@router.get("/health")
async def get_health() -> JSONResponse:
    """Endpoint público y minimalista para health-checks de orquestador.

    No expone configuración ni estado interno — útil para Kubernetes /
    Cloud Run / load balancers sin tener que abrir /status.
    """
    return JSONResponse({"status": "ok"})


@router.get("/status", response_class=HTMLResponse)
async def get_status(request: Request):
    """Endpoint para mostrar el estado del framework Behemot.

    Protegido con Bearer token si STATUS_API_TOKEN está definido. Sin token
    configurado el endpoint queda accesible (con warning); en producción debe
    configurarse el token o cerrarse el endpoint a nivel de red.
    """
    _require_status_auth(request)

    start_time = time.time()
    
    # Asegurar que los templates estén inicializados
    if templates is None:
        initialize_templates()
    
    # Realizar todas las verificaciones
    checks = {}
    checks["config"] = check_config()
    checks["redis"] = await check_redis()
    checks["tools"] = check_tools()
    checks["rag"] = await check_rag()
    checks["model"] = check_model()
    
    # Calcular tiempo de verificación
    checks["performance"] = get_performance_metrics()
    checks["performance"]["check_time_ms"] = round((time.time() - start_time) * 1000, 2)
    
    # Determinar estado general
    overall = determine_overall_status(checks)
    
    # Si los templates no están disponibles, usar el template incorporado
    if templates is None:
        from fastapi.responses import HTMLResponse
        import jinja2
        
        # Crear ambiente Jinja2 desde la plantilla incorporada
        template = jinja2.Template(STATUS_TEMPLATE)
        
        # Renderizar plantilla
        html_content = template.render(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            overall_status=overall["status"],
            overall_status_icon=overall["icon"],
            overall_status_class=overall["class"],
            config_status=checks["config"],
            redis_status=checks["redis"],
            tools_status=checks["tools"],
            rag_status=checks["rag"],
            model_status=checks["model"],
            performance=checks["performance"]
        )
        
        return HTMLResponse(content=html_content)
    else:
        # Renderizar usando Jinja2Templates
        return templates.TemplateResponse(
            "status.html",
            {
                "request": request,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "overall_status": overall["status"],
                "overall_status_icon": overall["icon"],
                "overall_status_class": overall["class"],
                "config_status": checks["config"],
                "redis_status": checks["redis"],
                "tools_status": checks["tools"],
                "rag_status": checks["rag"],
                "model_status": checks["model"],
                "performance": checks["performance"]
            }
        )

def setup_routes(app, config_path=None):
    """
    Configura las rutas de estado en la aplicación FastAPI
    
    Args:
        app: Aplicación FastAPI
        config_path: Ruta al archivo de configuración utilizado por la aplicación
    """
    # Almacenar la ruta de configuración globalmente
    global CONFIG_PATH
    CONFIG_PATH = config_path
    
    # Inicializar templates
    initialize_templates()
    
    # Registrar el router
    app.include_router(router)
    
    # Registrar el tiempo de inicio
    global BEHEMOT_START_TIME
    BEHEMOT_START_TIME = time.time()
    
    logger.info(f"Rutas de estado configuradas (/status) con configuración: {config_path or 'por defecto'}")

# Template HTML para la página de estado
STATUS_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Behemot Status</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .status-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .status-card {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            padding: 20px;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .status-item {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 15px;
            display: flex;
            flex-direction: column;
        }
        .status-icon {
            font-size: 24px;
            margin-right: 10px;
        }
        .status-label {
            font-weight: bold;
            margin-bottom: 5px;
        }
        .status-value {
            margin-top: 5px;
            word-break: break-word;
        }
        .status-ok {
            color: #27ae60;
        }
        .status-warning {
            color: #f39c12;
        }
        .status-error {
            color: #e74c3c;
        }
        .status-disabled {
            color: #7f8c8d;
        }
        .tools-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        .tool-item {
            background-color: #f8f9fa;
            border-radius: 4px;
            padding: 8px;
            font-size: 14px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .tool-item:hover {
            background-color: #e9ecef;
        }
        .refresh-button {
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.3s;
        }
        .refresh-button:hover {
            background-color: #2980b9;
        }
        .timestamp {
            color: #7f8c8d;
            font-size: 14px;
            margin-top: 5px;
        }
        .env-vars {
            max-height: 200px;
            overflow-y: auto;
            margin-top: 10px;
            background-color: #f8f9fa;
            border-radius: 4px;
            padding: 10px;
            font-family: monospace;
            font-size: 13px;
        }
        .collapsible {
            cursor: pointer;
            padding: 8px;
            background-color: #f1f1f1;
            border-radius: 4px;
            margin-top: 10px;
        }
        .collapsible-content {
            display: none;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 4px;
        }
        .rag-item {
            background-color: #f8f9fa;
            border-radius: 4px;
            padding: 8px;
            margin-top: 8px;
            font-size: 14px;
        }
        .tool-section {
            margin-bottom: 15px;
        }
        .rag-tools-list {
            background-color: #e8f4f8;
        }
        .rag-tool-item {
            background-color: #d1ecf1;
            border-left: 3px solid #0c7cd5;
        }
        .rag-tool-item:hover {
            background-color: #c1e1ea;
        }
        .error-detail {
            font-size: 12px;
            color: #e74c3c;
            margin-top: 5px;
            font-style: italic;
        }
        .mt-10 {
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="status-header">
        <h1>Behemot Status Dashboard</h1>
        <button class="refresh-button" onclick="window.location.reload()">Refrescar</button>
    </div>
    
    <div class="status-card">
        <div class="status-label">Estado General:</div>
        <div class="status-value">
            <span class="status-icon {{ overall_status_class }}">{{ overall_status_icon }}</span>
            {{ overall_status }}
        </div>
        <div class="timestamp">Actualizado: {{ timestamp }}</div>
    </div>
    
    <div class="status-grid">
        <!-- Configuración -->
        <div class="status-item">
            <div class="status-label">
                <span class="status-icon {{ config_status.icon_class }}">{{ config_status.icon }}</span>
                Configuración
            </div>
            <div class="status-value">
                <strong>Versión:</strong> {{ config_status.version }}<br>
                <strong>Nombre:</strong> {{ config_status.assistant_name }}<br>
                <strong>Modelo:</strong> {{ config_status.model }}<br>
                <strong>Seguridad:</strong> {{ config_status.safety_level }}<br>
                <strong>Archivo de configuración:</strong> {{ config_status.config_path }}
            </div>
            <div class="collapsible">Ver Variables de Entorno</div>
            <div class="collapsible-content">
                <div class="env-vars">
                    {% for key, value in config_status.env_vars.items() %}
                    <div><strong>{{ key }}:</strong> {{ value }}</div>
                    {% endfor %}
                </div>
            </div>
        </div>
        
        <!-- Redis -->
        <div class="status-item">
            <div class="status-label">
                <span class="status-icon {{ redis_status.icon_class }}">{{ redis_status.icon }}</span>
                Redis
            </div>
            <div class="status-value">
                <strong>Estado:</strong> {{ redis_status.status }}<br>
                {% if redis_status.connected %}
                <strong>Tiempo de respuesta:</strong> {{ redis_status.response_time_ms }} ms<br>
                <strong>Lectura/Escritura:</strong> {{ redis_status.read_write }}<br>
                {% endif %}
                {% if redis_status.error %}
                <div class="status-error">{{ redis_status.error }}</div>
                {% endif %}
            </div>
        </div>
        
        <!-- Herramientas -->
        <div class="status-item">
            <div class="status-label">
                <span class="status-icon {{ tools_status.icon_class }}">{{ tools_status.icon }}</span>
                Herramientas ({{ tools_status.count }})
            </div>
            <div class="status-value">
                {% if tools_status.rag_tools %}
                <div class="tool-section">
                    <strong>Herramientas RAG ({{ tools_status.rag_tools|length }}):</strong>
                    <div class="tools-list rag-tools-list">
                        {% for tool in tools_status.rag_tools %}
                        <div class="tool-item rag-tool-item" title="{{ tool.description }}">{{ tool.name }}</div>
                        {% endfor %}
                    </div>
                </div>
                {% endif %}
                
                {% if tools_status.tools %}
                <div class="tool-section">
                    <strong>Otras Herramientas ({{ tools_status.tools|length }}):</strong>
                    <div class="tools-list">
                        {% for tool in tools_status.tools %}
                        <div class="tool-item" title="{{ tool.description }}">{{ tool.name }}</div>
                        {% endfor %}
                    </div>
                </div>
                {% endif %}
                
                {% if not tools_status.tools and not tools_status.rag_tools %}
                <div class="status-warning">No hay herramientas registradas</div>
                {% endif %}
                
                {% if tools_status.error %}
                <div class="status-error">{{ tools_status.error }}</div>
                {% endif %}
            </div>
        </div>
        
        <!-- Sistema RAG -->
        <div class="status-item">
            <div class="status-label">
                <span class="status-icon {{ rag_status.icon_class }}">{{ rag_status.icon }}</span>
                Sistema RAG
            </div>
            <div class="status-value">
                <strong>Estado:</strong> {{ rag_status.status }}<br>
                {% if rag_status.enabled %}
                <strong>Proveedor:</strong> {{ rag_status.embedding_provider }}<br>
                <strong>Modelo:</strong> {{ rag_status.embedding_model }}<br>
                <div class="collapsible">Colecciones configuradas</div>
                <div class="collapsible-content">
                    {% if rag_status.collections %}
                    {% for collection in rag_status.collections %}
                    <div class="rag-item">
                        {{ collection.name }}: 
                        {% if collection.initialized == True %}
                        <span class="status-ok">✓ Inicializada</span>
                        {% elif collection.initialized == False %}
                        <span class="status-error">✗ No inicializada</span>
                        {% else %}
                        <span class="status-warning">? Estado desconocido</span>
                        {% endif %}
                        {% if collection.error %}
                        <div class="error-detail">{{ collection.error }}</div>
                        {% endif %}
                    </div>
                    {% endfor %}
                    {% else %}
                    <div class="status-warning">No hay colecciones configuradas</div>
                    {% endif %}
                </div>
                {% endif %}
                {% if rag_status.error %}
                <div class="status-error mt-10">{{ rag_status.error }}</div>
                {% endif %}
            </div>
        </div>
        
        <!-- Modelo -->
        <div class="status-item">
            <div class="status-label">
                <span class="status-icon {{ model_status.icon_class }}">{{ model_status.icon }}</span>
                Modelo LLM
            </div>
            <div class="status-value">
                <strong>Modelo:</strong> {{ model_status.model_name }}<br>
                <strong>API Key:</strong> {{ model_status.api_key_status }}<br>
                <strong>Temperatura:</strong> {{ model_status.temperature }}<br>
                <strong>Máx. Tokens:</strong> {{ model_status.max_tokens }}
            </div>
        </div>
        
        <!-- Rendimiento -->
        <div class="status-item">
            <div class="status-label">
                <span class="status-icon status-ok">📊</span>
                Rendimiento
            </div>
            <div class="status-value">
                <strong>Tiempo total verificación:</strong> {{ performance.check_time_ms }} ms<br>
                <strong>Memoria utilizada:</strong> {{ performance.memory_usage }} MB<br>
                <strong>Tiempo de carga:</strong> {{ performance.startup_time }} s<br>
            </div>
        </div>
    </div>

    <script>
        // Script para el comportamiento de los elementos colapsables
        var collapsibles = document.getElementsByClassName("collapsible");
        for (var i = 0; i < collapsibles.length; i++) {
            collapsibles[i].addEventListener("click", function() {
                this.classList.toggle("active");
                var content = this.nextElementSibling;
                if (content.style.display === "block") {
                    content.style.display = "none";
                } else {
                    content.style.display = "block";
                }
            });
        }
    </script>
</body>
</html>
"""
