# app/commandos/command_handler.py
import logging
import inspect
from typing import Dict, Any, Callable, Tuple, Optional
import json
import re
import time
from datetime import datetime

logger = logging.getLogger(__name__)

# Registro global de comandos
COMMAND_REGISTRY: Dict[str, Dict[str, Any]] = {}

def command(name: str, description: str):
    """
    Decorador para registrar un comando.
    """
    def decorator(func: Callable):
        COMMAND_REGISTRY[name] = {
            "name": name,
            "description": description,
            "handler": func
        }
        return func
    return decorator

class CommandHandler:
    """
    Manejador de comandos especiales que comienzan con &.
    """
    
    @staticmethod
    def is_command(message: str) -> bool:
        """
        Verifica si un mensaje es un comando.
        """
        return message.strip().startswith("&")
    
    @staticmethod
    def extract_command(message: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrae el nombre del comando y los argumentos.
        
        Args:
            message: El mensaje completo
            
        Returns:
            Tuple: (nombre_comando, argumentos_str) o (None, None) si no es un comando válido
        """
        if not CommandHandler.is_command(message):
            return None, None
        
        # Quitar el prefijo "&"
        message = message.strip()[1:]
        
        # Separar el comando de los argumentos
        parts = message.split(maxsplit=1)
        command_name = parts[0].lower()
        args_str = parts[1] if len(parts) > 1 else ""
        
        return command_name, args_str
    
    @staticmethod
    async def process_command(chat_id: str, message: str) -> str:
        """
        Procesa un comando y retorna la respuesta.
        
        Args:
            chat_id: ID del chat o sesión
            message: Mensaje original que contiene el comando
            
        Returns:
            str: Respuesta al comando o mensaje de error
        """
        try:
            command_name, args_str = CommandHandler.extract_command(message)
            
            if not command_name:
                return "Comando no válido. Los comandos deben comenzar con &."
            
            # Buscar en el registro de comandos
            if command_name not in COMMAND_REGISTRY:
                return f"Comando '&{command_name}' no reconocido. Comandos disponibles: {', '.join(['&' + cmd for cmd in COMMAND_REGISTRY.keys()])}"
            
            command_info = COMMAND_REGISTRY[command_name]
            handler = command_info["handler"]
            
            # Parsear argumentos si existen
            args = {}
            if args_str:
                # Intentar parsear como JSON
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    # Si no es JSON, intentar parsear como argumentos simples
                    args_pattern = re.compile(r'(\w+)=(?:"([^"]+)"|(\S+))')
                    matches = args_pattern.findall(args_str)
                    for match in matches:
                        key = match[0]
                        value = match[1] if match[1] else match[2]
                        args[key] = value
            
            # Ejecutar el handler con los argumentos extraídos
            result = handler(chat_id, **args)
            
            # Si es async, esperar el resultado
            if inspect.isawaitable(result):
                result = await result
                
            # Formatear respuesta
            return f"Comando ejecutado: &{command_name}\n\n{result}"
            
        except Exception as e:
            logger.error(f"Error ejecutando comando: {str(e)}", exc_info=True)
            return f"Error al ejecutar el comando: {str(e)}"

# Implementación del comando para limpiar mensajes
@command(name="clear_msg", description="Limpia todos los mensajes de la sesión")
async def clear_messages(chat_id: str, **kwargs) -> str:
    """
    Limpia todos los mensajes de una sesión en Redis.
    
    Args:
        chat_id: ID del chat o sesión
        
    Returns:
        str: Mensaje de confirmación
    """
    try:
        from behemot_framework.context import redis_client, save_conversation
        from behemot_framework.config import Config
        
        # Obtener la configuración desde el gestor centralizado
        config = Config.get_config()
        
        # Obtener el prompt del sistema
        prompt_sistema = config.get("PROMPT_SISTEMA", "")
        
        # Registrar para debugging
        logger.info(f"Reiniciando chat {chat_id} con prompt desde config_path: {Config.get_config_path()}")
        logger.info(f"Primeros 50 caracteres del prompt: {prompt_sistema[:50]}...")
        
        # Crear una nueva conversación solo con el mensaje del sistema
        new_conversation = [{"role": "system", "content": prompt_sistema}]
        
        # Guardar la nueva conversación
        save_conversation(chat_id, new_conversation)
        
        return "Historial de mensajes eliminado correctamente. El asistente ha sido reiniciado con su configuración original."
    except Exception as e:
        logger.error(f"Error al limpiar mensajes: {str(e)}", exc_info=True)
        return f"Error al limpiar mensajes: {str(e)}"

@command(name="help", description="Muestra la lista de comandos disponibles")
async def help_command(chat_id: str, **kwargs) -> str:
    """
    Muestra la lista de comandos disponibles y su descripción.
    """
    commands = []
    for name, info in COMMAND_REGISTRY.items():
        commands.append(f"&{name}: {info['description']}")
    
    return "Comandos disponibles:\n\n" + "\n".join(commands)

# Importar funciones del módulo system_status
from behemot_framework.commandos.system_status import (
    check_redis,
    check_rag,
    check_model,
    check_config,
    check_tools,
    get_performance_metrics
)

@command(name="status", description="Muestra información detallada del estado del sistema")
async def enhanced_status_command(chat_id: str, **kwargs) -> str:
    """
    Comando mejorado para mostrar el estado detallado del sistema.
    Similar al endpoint /status pero en formato de texto.
    """
    try:
        # Verificar permisos
        from behemot_framework.commandos.permissions import get_permission_manager
        
        perm_manager = get_permission_manager()
        if not perm_manager.has_permission(chat_id, "status"):
            return "❌ **Acceso denegado**: No tienes permisos para ver el estado del sistema.\n\nUsa `&whoami` para ver tus permisos actuales."
        
    except Exception as perm_error:
        logger.error(f"Error verificando permisos para status: {perm_error}")
        return f"❌ Error verificando permisos: {str(perm_error)}"
    
    start_time = time.time()
    
    # Recolectar información de todos los sistemas
    checks = {}
    checks["config"] = check_config()
    checks["redis"] = await check_redis()
    checks["tools"] = check_tools()
    checks["rag"] = await check_rag()
    checks["model"] = check_model()
    
    # Calcular tiempo de verificación
    checks["performance"] = get_performance_metrics()
    checks["performance"]["check_time_ms"] = round((time.time() - start_time) * 1000, 2)
    
    # Formatear resultado en texto
    result = "📊 ESTADO DEL SISTEMA BEHEMOT 📊\n"
    result += f"Tiempo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    # Configuración
    result += "🔧 CONFIGURACIÓN\n"
    result += f"Estado: {checks['config']['status']}\n"
    result += f"Versión: {checks['config']['version']}\n"
    result += f"Asistente: {checks['config']['assistant_name']}\n"
    result += f"Modelo: {checks['config']['model']}\n"
    result += f"Nivel de seguridad: {checks['config']['safety_level']}\n"
    result += f"Archivo de configuración: {checks['config'].get('config_path', 'Por defecto')}\n"
    if checks["config"].get("error"):
        result += f"Error: {checks['config']['error']}\n"
    result += "\n"
    
    # Redis
    result += "💾 REDIS\n"
    result += f"Estado: {checks['redis']['status']}\n"
    if checks["redis"]["connected"]:
        result += f"Tiempo de respuesta: {checks['redis']['response_time_ms']} ms\n"
        result += f"Lectura/Escritura: {checks['redis']['read_write']}\n"
    if checks["redis"].get("error"):
        result += f"Error: {checks['redis']['error']}\n"
    result += "\n"
    
    # Herramientas
    result += "🔧 HERRAMIENTAS\n"
    result += f"Total: {checks['tools']['count']}\n"
    
    if checks["tools"]["rag_tools"]:
        result += f"Herramientas RAG ({len(checks['tools']['rag_tools'])})\n"
        for tool in checks["tools"]["rag_tools"]:
            result += f"- {tool['name']}\n"
    
    if checks["tools"]["tools"]:
        result += f"Otras herramientas ({len(checks['tools']['tools'])})\n"
        for tool in checks["tools"]["tools"]:
            result += f"- {tool['name']}\n"
    
    if checks["tools"].get("error"):
        result += f"Error: {checks['tools']['error']}\n"
    result += "\n"
    
    # Sistema RAG
    result += "📚 SISTEMA RAG\n"
    result += f"Estado: {checks['rag']['status']}\n"
    if checks["rag"]["enabled"]:
        result += f"Proveedor: {checks['rag']['embedding_provider']}\n"
        result += f"Modelo: {checks['rag']['embedding_model']}\n"
        
        if checks["rag"]["collections"]:
            result += "Colecciones:\n"
            for collection in checks["rag"]["collections"]:
                status = "✓ Inicializada" if collection.get("initialized") else "✗ No inicializada"
                result += f"- {collection['name']}: {status}\n"
                if collection.get("error"):
                    result += f"  Error: {collection['error']}\n"
    
    if checks["rag"].get("error"):
        result += f"Error: {checks['rag']['error']}\n"
    result += "\n"
    
    # Modelo
    result += "🧠 MODELO LLM\n"
    result += f"Modelo: {checks['model']['model_name']}\n"
    result += f"API Key: {checks['model']['api_key_status']}\n"
    result += f"Temperatura: {checks['model']['temperature']}\n"
    result += f"Máx. Tokens: {checks['model']['max_tokens']}\n"
    if checks["model"].get("error"):
        result += f"Error: {checks['model']['error']}\n"
    result += "\n"
    
    # Rendimiento
    result += "⚡ RENDIMIENTO\n"
    result += f"Tiempo verificación: {checks['performance']['check_time_ms']} ms\n"
    result += f"Memoria utilizada: {checks['performance']['memory_usage']} MB\n"
    result += f"Tiempo desde inicio: {checks['performance']['startup_time']} s\n"
    
    return result

@command(name="reset_to_fabric", description="Borra todos los mensajes de Redis y reinicia el prompt del sistema")
async def reset_to_fabric_command(chat_id: str, **kwargs) -> str:
    """
    Borra todo el contenido de Redis y reinicia el prompt.
    Este comando es más drástico que clear_msg ya que elimina TODAS las sesiones.
    """
    try:
        # 1. Obtener la configuración y el prompt del sistema
        from behemot_framework.config import Config
        from behemot_framework.context import redis_client, save_conversation
        
        config = Config.get_config()
        prompt_sistema = config.get("PROMPT_SISTEMA", "")
        
        # 2. Verificar que Redis esté disponible
        redis_status = await check_redis()
        if not redis_status["connected"]:
            return f"Error: No se puede conectar a Redis. {redis_status.get('error', '')}"
        
        # 3. Obtener todas las claves en Redis
        all_keys = redis_client.keys("chat:*")
        num_sessions = len(all_keys)
        
        # 4. Eliminar todas las claves de chat
        if all_keys:
            redis_client.delete(*all_keys)
        
        # 5. Reiniciar la sesión actual con el prompt del sistema
        new_conversation = [{"role": "system", "content": prompt_sistema}]
        save_conversation(chat_id, new_conversation)
        
        logger.info(f"Reset a fabric realizado. {num_sessions} sesiones eliminadas.")
        
        return (f"✅ Reset a fabric completado. Se han eliminado {num_sessions} sesiones de Redis.\n\n"
                f"La sesión actual ha sido reiniciada con el prompt original del sistema.\n\n"
                f"Configuración actual:\n"
                f"- Asistente: {config.get('ASSISTANT_NAME', 'Behemot')}\n"
                f"- Versión: {config.get('VERSION', '1.0.0')}\n"
                f"- Modelo: {config.get('MODEL_NAME', 'gpt-4o-mini')}")
    
    except Exception as e:
        logger.error(f"Error en reset_to_fabric: {str(e)}", exc_info=True)
        return f"Error al realizar el reset a fabric: {str(e)}"

@command(name="delete_session", description="Elimina una sesión específica de Redis")
async def delete_session_command(chat_id: str, target_id: str = None, **kwargs) -> str:
    """
    Elimina una sesión específica de Redis por su ID.
    
    Args:
        chat_id: ID de la sesión actual
        target_id: ID de la sesión a eliminar (si es None, se usa chat_id)
    """
    try:
        from behemot_framework.context import redis_client
        
        # Si no se proporciona target_id, usar el chat_id actual
        if not target_id:
            return "Error: Se requiere especificar el ID de la sesión a eliminar con el parámetro 'target_id'."
        
        # Verificar que Redis esté disponible
        redis_status = await check_redis()
        if not redis_status["connected"]:
            return f"Error: No se puede conectar a Redis. {redis_status.get('error', '')}"
        
        # Verificar si la sesión existe
        key = f"chat:{target_id}"
        if not redis_client.exists(key):
            return f"Error: La sesión con ID '{target_id}' no existe en Redis."
        
        # Eliminar la sesión
        redis_client.delete(key)
        
        logger.info(f"Sesión {target_id} eliminada correctamente.")
        
        return f"✅ Sesión con ID '{target_id}' eliminada correctamente."
    
    except Exception as e:
        logger.error(f"Error en delete_session: {str(e)}", exc_info=True)
        return f"Error al eliminar la sesión: {str(e)}"

@command(name="list_sessions", description="Lista todas las sesiones almacenadas en Redis")
async def list_sessions_command(chat_id: str, **kwargs) -> str:
    """
    Lista todas las sesiones almacenadas en Redis.
    """
    try:
        from behemot_framework.context import redis_client
        
        # Verificar que Redis esté disponible
        redis_status = await check_redis()
        if not redis_status["connected"]:
            return f"Error: No se puede conectar a Redis. {redis_status.get('error', '')}"
        
        # Obtener todas las claves de chat
        all_keys = redis_client.keys("chat:*")
        
        if not all_keys:
            return "No hay sesiones almacenadas en Redis."
        
        # Analizar cada sesión para obtener información básica
        sessions_info = []
        for key in all_keys:
            session_id = key.split(":")[-1]
            
            try:
                # Obtener datos de la sesión
                session_data = redis_client.get(key)
                if session_data:
                    conversation = json.loads(session_data)
                    num_messages = len(conversation) - 1  # Restar el mensaje del sistema
                    
                    # Obtener el último mensaje del usuario (si existe)
                    last_user_msg = None
                    for msg in reversed(conversation):
                        if msg.get("role") == "user":
                            content = msg.get("content", "")
                            last_user_msg = content[:30] + "..." if len(content) > 30 else content
                            break
                    
                    sessions_info.append({
                        "id": session_id,
                        "messages": max(0, num_messages),
                        "last_msg": last_user_msg
                    })
            except Exception as e:
                sessions_info.append({
                    "id": session_id,
                    "error": str(e)
                })
        
        # Formatear resultado
        result = f"📋 SESIONES EN REDIS ({len(all_keys)})\n\n"
        
        for info in sessions_info:
            result += f"ID: {info['id']}\n"
            if "messages" in info:
                result += f"Mensajes: {info['messages']}\n"
                if info.get("last_msg"):
                    result += f"Último mensaje: \"{info['last_msg']}\"\n"
            if "error" in info:
                result += f"Error: {info['error']}\n"
            result += "\n"
        
        return result
    
    except Exception as e:
        logger.error(f"Error en list_sessions: {str(e)}", exc_info=True)
        return f"Error al listar sesiones: {str(e)}"
    


from behemot_framework.commandos.system_monitor import (
    get_monitoring_data,
    get_quick_monitoring_snapshot,
    format_monitoring_results,
    format_monitoring_snapshot,
    stop_monitoring
)

@command(name="monitor", description="Monitorea el estado del sistema en tiempo real")
async def monitor_command(chat_id: str, duration: str = "5", interval: str = "10", stop: str = "false", snapshot: str = "false", **kwargs) -> str:
    """
    Monitorea el estado del sistema en tiempo real.
    
    Args:
        chat_id: ID del chat o sesión
        duration: Duración del monitoreo en minutos (default: 5)
        interval: Intervalo entre mediciones en segundos (default: 10)
        stop: Si es "true", detiene el monitoreo activo
        snapshot: Si es "true", devuelve una instantánea rápida del estado actual
        
    Returns:
        str: Resultados del monitoreo
    """
    try:
        # Convertir parámetros a tipos correctos
        try:
            duration_min = int(duration)
            interval_sec = int(interval)
        except ValueError:
            duration_min = 5
            interval_sec = 10
        
        # Limitar valores para evitar abusos
        duration_min = max(1, min(duration_min, 30))  # Entre 1 y 30 minutos
        interval_sec = max(5, min(interval_sec, 60))  # Entre 5 y 60 segundos
        
        # Verificar si se debe detener un monitoreo existente
        if stop.lower() == "true":
            results = stop_monitoring()
            if "error" in results:
                return results["error"]
            return format_monitoring_results(results)
        
        # Verificar si se solicita una instantánea rápida
        if snapshot.lower() == "true":
            snapshot_data = await get_quick_monitoring_snapshot()
            return format_monitoring_snapshot(snapshot_data)
        
        # Iniciar monitoreo completo
        logger.info(f"Iniciando monitoreo por {duration_min} minutos con intervalo de {interval_sec} segundos")
        
        # Notificar al usuario que el monitoreo comenzó
        initial_message = (
            f"🔍 Iniciando monitoreo del sistema...\n\n"
            f"⏱️ Duración: {duration_min} minutos\n"
            f"⏱️ Intervalo: {interval_sec} segundos\n\n"
            f"El monitoreo está en progreso. Por favor, espera.\n"
            f"Para detener antes de tiempo, usa '&monitor stop=true'"
        )
        
        # Iniciar monitoreo en segundo plano
        results = await get_monitoring_data(duration_min, interval_sec)
        
        # Formatear resultados para mostrar al usuario
        formatted_results = format_monitoring_results(results)
        
        return initial_message + "\n\n" + formatted_results
        
    except Exception as e:
        logger.error(f"Error en comando monitor: {str(e)}", exc_info=True)
        return f"Error al monitorear el sistema: {str(e)}\n\nPrueba con '&monitor snapshot=true' para un estado rápido."
    


from behemot_framework.commandos.session_analyzer import analyze_session, analyze_current_session, format_session_analysis

# Importar comandos de administración
from behemot_framework.commandos.admin_commands import get_admin_commands

@command(name="sendmsg", description="Envía un mensaje a todos los usuarios activos del bot")
async def sendmsg_command(chat_id: str, message: str = None, platform: str = None, **kwargs) -> str:
    """
    Envía un mensaje masivo a todos los usuarios activos.
    
    Args:
        chat_id: ID del usuario administrador que ejecuta el comando
        message: Mensaje a enviar (puede incluir comillas)
        platform: Plataforma específica (opcional: telegram, whatsapp, api, google_chat)
        
    Returns:
        str: Resultado del envío masivo
    """
    try:
        # Verificar permisos
        from behemot_framework.commandos.permissions import get_permission_manager
        
        perm_manager = get_permission_manager()
        if not perm_manager.has_permission(chat_id, "sendmsg"):
            return "❌ **Acceso denegado**: No tienes permisos para enviar mensajes masivos.\n\nUsa `&whoami` para ver tus permisos actuales."
        
        # Obtener comandos de administración
        admin_commands = get_admin_commands()
        
        # Verificar que se proporcione un mensaje
        if not message:
            return ("❌ Error: Debes proporcionar un mensaje.\n\n"
                   "Uso: &sendmsg message=\"Tu mensaje aquí\"\n"
                   "O: &sendmsg message=\"Tu mensaje\" platform=\"telegram\"\n\n"
                   "Plataformas disponibles: telegram, whatsapp, api, google_chat")
        
        # Validar plataforma si se especifica
        valid_platforms = ["telegram", "whatsapp", "api", "google_chat"]
        if platform and platform not in valid_platforms:
            return f"❌ Plataforma inválida: {platform}\n\nPlataformas válidas: {', '.join(valid_platforms)}"
        
        # Ejecutar el comando de envío masivo
        logger.info(f"Ejecutando sendmsg desde {chat_id}, mensaje: {message[:50]}..., plataforma: {platform}")
        
        result = await admin_commands.execute_sendmsg(
            admin_user_id=chat_id,
            broadcast_message=message,
            target_platform=platform
        )
        
        return result["message"]
        
    except Exception as e:
        logger.error(f"Error en comando sendmsg: {str(e)}", exc_info=True)
        return f"❌ Error al enviar mensaje masivo: {str(e)}"

@command(name="list_users", description="Lista usuarios activos por plataforma")
async def list_users_command(chat_id: str, platform: str = None, days: str = "7", **kwargs) -> str:
    """
    Lista usuarios activos por plataforma.
    
    Args:
        chat_id: ID del usuario que ejecuta el comando
        platform: Plataforma específica (opcional)
        days: Días de actividad a considerar (default: 7)
        
    Returns:
        str: Lista de usuarios activos
    """
    try:
        # Verificar permisos
        from behemot_framework.commandos.permissions import get_permission_manager
        
        perm_manager = get_permission_manager()
        if not perm_manager.has_permission(chat_id, "list_users"):
            return "❌ **Acceso denegado**: No tienes permisos para listar usuarios.\n\nUsa `&whoami` para ver tus permisos actuales."
        
        from behemot_framework.users import get_user_tracker
        
        # Convertir días
        try:
            active_days = int(days)
            active_days = max(1, min(active_days, 365))  # Entre 1 y 365 días
        except ValueError:
            active_days = 7
        
        user_tracker = get_user_tracker()
        
        if platform:
            # Lista de una plataforma específica
            users = user_tracker.get_users_by_platform(platform, active_days)
            
            if not users:
                return f"📭 No hay usuarios activos en {platform} en los últimos {active_days} días."
            
            result = f"👥 **Usuarios activos en {platform.title()}** (últimos {active_days} días):\n\n"
            
            for i, user in enumerate(users, 1):
                user_id = user["user_id"]
                last_seen = user["last_seen"][:10]  # Solo fecha
                metadata = user.get("metadata", {})
                
                result += f"{i}. ID: `{user_id}`\n"
                result += f"   Última actividad: {last_seen}\n"
                
                # Información específica por plataforma
                if platform == "telegram":
                    if metadata.get("username_handle"):
                        result += f"   Username: {metadata['username_handle']}\n"
                    if metadata.get("display_name"):
                        result += f"   Nombre: {metadata['display_name']}\n"
                    if metadata.get("language_code"):
                        result += f"   Idioma: {metadata['language_code']}\n"
                        
                elif platform == "whatsapp":
                    if metadata.get("phone_number"):
                        result += f"   📱 Teléfono: {metadata['phone_number']}\n"
                    if metadata.get("profile_name"):
                        result += f"   Nombre: {metadata['profile_name']}\n"
                    if metadata.get("country_code"):
                        result += f"   País: {metadata['country_code']}\n"
                        
                elif platform == "google_chat":
                    if metadata.get("email"):
                        result += f"   📧 Email: {metadata['email']}\n"
                    if metadata.get("display_name"):
                        result += f"   Nombre: {metadata['display_name']}\n"
                    if metadata.get("domain"):
                        result += f"   Dominio: {metadata['domain']}\n"
                        
                elif platform == "api":
                    if metadata.get("ip_address"):
                        result += f"   🌐 IP: {metadata['ip_address']}\n"
                    if metadata.get("user_agent"):
                        user_agent = metadata['user_agent'][:50] + "..." if len(metadata['user_agent']) > 50 else metadata['user_agent']
                        result += f"   Navegador: {user_agent}\n"
                
                result += "\n"
                
        else:
            # Lista de todas las plataformas
            all_users = user_tracker.get_all_active_users(active_days)
            
            if not all_users:
                return f"📭 No hay usuarios activos en ninguna plataforma en los últimos {active_days} días."
            
            result = f"👥 **Usuarios activos por plataforma** (últimos {active_days} días):\n\n"
            
            total_users = 0
            for platform, users in all_users.items():
                result += f"**{platform.title()}**: {len(users)} usuarios\n"
                total_users += len(users)
                
                # Mostrar algunos ejemplos
                for i, user in enumerate(users[:3]):
                    user_id = user["user_id"]
                    last_seen = user["last_seen"][:10]
                    result += f"  • {user_id} (última: {last_seen})\n"
                
                if len(users) > 3:
                    result += f"  • ... y {len(users) - 3} más\n"
                
                result += "\n"
            
            result += f"**Total**: {total_users} usuarios activos\n\n"
            result += "💡 Usa `&list_users platform=\"telegram\"` para ver detalles de una plataforma específica."
        
        return result
        
    except Exception as e:
        logger.error(f"Error en comando list_users: {str(e)}", exc_info=True)
        return f"❌ Error al listar usuarios: {str(e)}"

@command(name="whoami", description="Muestra información del usuario actual y sus permisos")
async def whoami_command(chat_id: str, **kwargs) -> str:
    """
    Muestra información del usuario actual incluyendo permisos y metadata.
    
    Args:
        chat_id: ID del usuario que ejecuta el comando
        
    Returns:
        str: Información detallada del usuario
    """
    try:
        from behemot_framework.users import get_user_tracker
        from behemot_framework.commandos.admin_commands import get_admin_commands
        from datetime import datetime
        
        # Obtener información del usuario
        user_tracker = get_user_tracker()
        admin_commands = get_admin_commands()
        
        # Buscar el usuario en todas las plataformas
        user_info = None
        user_platform = None
        
        for platform in ["telegram", "whatsapp", "api", "google_chat"]:
            users = user_tracker.get_users_by_platform(platform, 365)  # Buscar en el último año
            for user in users:
                if user["user_id"] == chat_id:
                    user_info = user
                    user_platform = platform
                    break
            if user_info:
                break
        
        if not user_info:
            return "❌ No se encontró información de usuario. Esto puede suceder si es tu primera interacción."
        
        # Obtener metadata específica de la plataforma
        metadata = user_info.get("metadata", {})
        
        # Formatear información básica
        result = "👤 **Tu información de usuario:**\n\n"
        result += f"🆔 **User ID**: `{chat_id}`\n"
        result += f"📱 **Plataforma**: `{user_platform}`\n"
        
        # Formatear fechas
        try:
            first_seen = datetime.fromisoformat(user_info["first_seen"])
            last_seen = datetime.fromisoformat(user_info["last_seen"])
            result += f"⏰ **Primera vez visto**: `{first_seen.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            result += f"🕐 **Última actividad**: `{last_seen.strftime('%Y-%m-%d %H:%M:%S')}`\n"
        except:
            result += f"⏰ **Primera vez visto**: `{user_info.get('first_seen', 'Desconocido')}`\n"
            result += f"🕐 **Última actividad**: `{user_info.get('last_seen', 'Desconocido')}`\n"
        
        # Información específica por plataforma
        result += "\n📋 **Información de la plataforma:**\n"
        
        if user_platform == "telegram":
            if metadata.get("username_handle"):
                result += f"• **Username**: @{metadata['username_handle']}\n"
            if metadata.get("display_name"):
                result += f"• **Nombre**: {metadata['display_name']}\n"
            if metadata.get("language_code"):
                result += f"• **Idioma**: {metadata['language_code']}\n"
            if metadata.get("is_premium"):
                result += f"• **Telegram Premium**: {'Sí' if metadata['is_premium'] else 'No'}\n"
                
        elif user_platform == "whatsapp":
            if metadata.get("phone_number"):
                result += f"• **📱 Teléfono**: {metadata['phone_number']}\n"
            if metadata.get("profile_name"):
                result += f"• **Nombre**: {metadata['profile_name']}\n"
            if metadata.get("country_code"):
                result += f"• **País**: {metadata['country_code']}\n"
                
        elif user_platform == "google_chat":
            if metadata.get("email"):
                result += f"• **📧 Email**: {metadata['email']}\n"
            if metadata.get("display_name"):
                result += f"• **Nombre**: {metadata['display_name']}\n"
            if metadata.get("domain"):
                result += f"• **Dominio**: {metadata['domain']}\n"
            if metadata.get("space_type"):
                result += f"• **Tipo de espacio**: {metadata['space_type']}\n"
                
        elif user_platform == "api":
            if metadata.get("ip_address"):
                result += f"• **🌐 IP**: {metadata['ip_address']}\n"
            if metadata.get("user_agent"):
                user_agent = metadata['user_agent'][:50] + "..." if len(metadata['user_agent']) > 50 else metadata['user_agent']
                result += f"• **Navegador**: {user_agent}\n"
            if metadata.get("session_id"):
                result += f"• **Sesión**: {metadata['session_id']}\n"
        
        # Obtener información de permisos real
        from behemot_framework.commandos.permissions import get_permission_manager
        
        perm_manager = get_permission_manager()
        perm_info = perm_manager.get_permission_info(chat_id, user_platform)
        
        result += "\n🔑 **Permisos actuales:**\n"
        
        # Mostrar si es admin
        if perm_info["is_admin"]:
            result += f"👑 **Administrador** (modo: {perm_info['admin_mode']})\n"
        else:
            result += "👤 **Usuario regular**\n"
        
        # Mostrar permisos detallados
        for perm_name, perm_data in perm_info["permission_details"].items():
            status = "✅" if perm_data["has_permission"] else "❌"
            result += f"{status} **{perm_name}** - {perm_data['description']}\n"
        
        # Comandos disponibles basados en permisos reales
        available_commands = perm_info["available_commands"]
        
        result += "\n📊 **Comandos disponibles:**\n"
        if available_commands:
            for cmd in available_commands:
                result += f"• `&{cmd}` - {_get_command_description(cmd)}\n"
        else:
            result += "• `&whoami` - Ver tu información (comando básico)\n"
        
        result += "\n💡 **Tip**: Usa `&help` para ver todos los comandos disponibles."
        
        return result
        
    except Exception as e:
        logger.error(f"Error en comando whoami: {str(e)}", exc_info=True)
        return f"❌ Error al obtener información del usuario: {str(e)}"

def _get_command_description(cmd: str) -> str:
    """
    Obtiene la descripción de un comando.
    
    Args:
        cmd: Nombre del comando
        
    Returns:
        Descripción del comando
    """
    descriptions = {
        "whoami": "Ver tu información y permisos",
        "sendmsg": "Envío masivo de mensajes",
        "list_users": "Ver usuarios activos",
        "delete_session": "Eliminar sesiones específicas",
        "list_sessions": "Listar todas las sesiones",
        "status": "Estado del sistema",
        "monitor": "Monitorear sistema en tiempo real",
        "reset_to_fabric": "Reiniciar todo el sistema",
        "clear_msg": "Limpiar historial de mensajes",
        "help": "Lista completa de comandos",
        "analyze_session": "Analizar estadísticas de sesión"
    }
    return descriptions.get(cmd, "Comando disponible")

@command(name="analyze_session", description="Analiza una sesión para obtener estadísticas e insights")
async def analyze_session_command(chat_id: str, session_id: str = None, detailed: str = "false", **kwargs) -> str:
    """
    Analiza una sesión para obtener estadísticas e insights.
    
    Args:
        chat_id: ID del chat o sesión actual
        session_id: ID de la sesión a analizar (si es None, se usa chat_id)
        detailed: Si es "true", incluye análisis más detallados
        
    Returns:
        str: Resultados del análisis formateados
    """
    try:
        # Convertir parámetros
        detailed_bool = detailed.lower() in ("true", "1", "yes", "y")
        target_id = session_id if session_id else chat_id
        
        # Verificar si la sesión existe
        from behemot_framework.context import redis_client
        key = f"chat:{target_id}"
        if not redis_client.exists(key):
            return f"Error: La sesión con ID '{target_id}' no existe en Redis."
        
        # Determinar si es la sesión actual o una diferente
        if target_id == chat_id:
            logger.info(f"Analizando sesión actual: {chat_id}")
            analysis_results = await analyze_current_session(chat_id, detailed_bool)
        else:
            logger.info(f"Analizando sesión externa: {target_id}")
            analysis_results = await analyze_session(target_id, detailed_bool)
        
        # Formatear resultados
        formatted_results = format_session_analysis(analysis_results, detailed_bool)
        
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error en comando analyze_session: {str(e)}", exc_info=True)
        return f"Error al analizar la sesión: {str(e)}"
