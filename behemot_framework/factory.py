# app/factory.py
import importlib
import inspect
import os
import logging
import pkgutil
from typing import List, Dict, Any, Optional, Callable
from fastapi import FastAPI, Request

from behemot_framework.config import Config, load_config
from behemot_framework.models import ModelFactory
from behemot_framework.assistants.assistant import Assistant
from behemot_framework.connectors.telegram_connector import TelegramConnector
from behemot_framework.connectors.api_connector import ApiConnector
from behemot_framework.services.transcription_service import TranscriptionService

# Opcional para tipos futuros
try:
    from behemot_framework.connectors.whatsapp_connector import WhatsAppConnector
    WHATSAPP_AVAILABLE = True
except ImportError:
    WHATSAPP_AVAILABLE = False

logger = logging.getLogger(__name__)

class BehemotFactory:
    """
    Factory para crear y configurar componentes del framework Behemot.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa el factory con la configuración.
        Args:
            config: Diccionario con la configuración del framework
        """
        self.config = config

        
        
        # Inicializar componentes básicos
        # Usar ModelFactory para crear el modelo basado en la configuración
        self.modelo = ModelFactory.create_model()
        self.asistente = Assistant(
            self.modelo, 
            prompt_sistema=config.get("PROMPT_SISTEMA"),
            safety_level=config.get("SAFETY_LEVEL", "medium")
        )
        
        # Inicializar servicio de transcripción si se configura
        if config.get("ENABLE_VOICE", False):
            self.transcriptor = TranscriptionService(api_key=config.get("GPT_API_KEY"))
        else:
            self.transcriptor = None
            
        # Conectores (se inicializan bajo demanda)
        self.telegram_connector = None
        self.api_connector = None
        self.whatsapp_connector = None
        
        # Registro de herramientas cargadas
        self.loaded_tools = []
    
    def load_tools(self, tool_names: List[str] = None) -> None:
        """
        Carga herramientas específicas por nombre.
        Args:
            tool_names: Lista de nombres de herramientas a cargar
        """
        # Si no se proporcionó ninguna herramienta, no cargar nada
        if not tool_names:
            logger.info("No se especificaron herramientas para cargar")
            return
            
        for tool_name in tool_names:
            try:
                # Importar dinámicamente el módulo de la herramienta
                module_path = f"tools.{tool_name}"
                importlib.import_module(module_path)
                self.loaded_tools.append(tool_name)
                logger.info(f"Herramienta cargada: {tool_name}")
            except ImportError as e:
                logger.warning(f"No se pudo cargar la herramienta {tool_name}: {e}")
    
    def load_all_tools(self) -> None:
        """
        Carga todas las herramientas disponibles en el directorio tools.
        """
        tools_path = os.path.join(os.path.dirname(__file__), "tools")
        if not os.path.exists(tools_path):
            logger.warning(f"Directorio de herramientas no encontrado: {tools_path}")
            return
            
        for _, name, is_pkg in pkgutil.iter_modules([tools_path]):
            if not is_pkg and name != "__init__":
                try:
                    importlib.import_module(f"{self.tools_dir.replace(os.sep, '.')}.{name}" if self.tools_dir else f"behemot_framework.tools.{name}")
                    self.loaded_tools.append(name)
                except ImportError as e:
                    logger.warning(f"Error al cargar herramienta {name}: {e}")
        
        logger.info(f"Herramientas cargadas: {', '.join(self.loaded_tools)}")
    
    def setup_telegram_connector(self, fastapi_app: FastAPI) -> None:
        """
        Configura el conector de Telegram y sus endpoints.
        Args:
            app: Aplicación FastAPI a configurar
        """
        token = self.config.get("TELEGRAM_TOKEN")
        if not token:
            logger.error("No se encontró TELEGRAM_TOKEN en la configuración")
            return
                
        self.telegram_connector = TelegramConnector(token)
        
        # Priorizar la configuración específica de Telegram
        telegram_webhook_url = self.config.get("TELEGRAM_WEBHOOK_URL", "")
        
        # Si no hay URL específica para Telegram, usar la URL general
        if not telegram_webhook_url:
            webhook_url = self.config.get("WEBHOOK_URL", "")
            
            # Asegurarse de que la URL termine con /webhook para Telegram
            if webhook_url and not webhook_url.endswith("/webhook"):
                telegram_webhook_url = webhook_url + "/webhook"
            else:
                telegram_webhook_url = webhook_url
        
        # Configurar webhook si está definido
        if telegram_webhook_url:
            from behemot_framework.startup import set_telegram_webhook
            logger.info(f"Configurando webhook de Telegram: {telegram_webhook_url}")
            # Usar la URL específica para Telegram
            set_telegram_webhook(token, telegram_webhook_url)
        
        @fastapi_app.post("/webhook")
        async def procesar_mensaje_telegram(request: Request):
            update = await request.json()
            chat_id, mensaje = self.telegram_connector.extraer_mensaje(update)
            
            if mensaje is None:
                return {"status": "ok"}
            
            # Indicar que el bot está "escribiendo"
            self.telegram_connector.enviar_accion(chat_id, "typing")
            
            if mensaje["type"] == "text":
                texto = mensaje["content"]
            elif mensaje["type"] == "voice" and self.transcriptor:
                # Transcribir audio a texto
                audio_path = mensaje["content"]
                self.telegram_connector.enviar_accion(chat_id, "typing")
                texto = self.transcriptor.transcribe_audio(audio_path)
                logging.info(f"Audio transcrito del chat {chat_id}: {texto}")
                
                try:
                    os.remove(audio_path)
                except:
                    pass
            else:
                return {"status": "ok"}
            
            if texto:
                self.telegram_connector.enviar_accion(chat_id, "typing")
                respuesta = await self.asistente.generar_respuesta(str(chat_id), texto)
                # Verificar si el conector tiene método procesar_respuesta
                if hasattr(self.telegram_connector, 'procesar_respuesta'):
                    await self.telegram_connector.procesar_respuesta(chat_id, respuesta)
                else:
                    # Fallback al método enviar_mensaje
                    self.telegram_connector.enviar_mensaje(chat_id, respuesta)
            
            return {"status": "ok"}
        
        logger.info("Conector de Telegram configurado")
    
    def setup_api_connector(self, fastapi_app: FastAPI) -> None:
        """
        Configura el conector de API REST y sus endpoints.
        Args:
            fastapi_app: Aplicación FastAPI a configurar
        """
        self.api_connector = ApiConnector()
        
        # Verificar si el procesamiento de voz está habilitado
        voice_enabled = self.transcriptor is not None
        
        @fastapi_app.post("/api/chat")
        async def process_api_message(request: Request):
            """Endpoint para recibir mensajes de texto o audio de cualquier cliente via API."""
            try:
                # Verificar el tipo de contenido
                content_type = request.headers.get("Content-Type", "")
                
                if "multipart/form-data" in content_type and voice_enabled:
                    # Caso de archivo de audio
                    form = await request.form()
                    
                    session_id = form.get("session_id")
                    audio_file = form.get("audio_file")
                    
                    if not session_id or not audio_file:
                        return {"error": "Formato de mensaje inválido. Se requiere session_id y audio_file", "status": "error"}
                    
                    # Guardar el archivo temporalmente
                    import time
                    import os
                    temp_path = f"temp_audio_{session_id}_{int(time.time())}.ogg"
                    with open(temp_path, "wb") as f:
                        audio_content = await audio_file.read()
                        f.write(audio_content)
                    
                    # Transcribir el audio
                    logger.info(f"Transcribiendo audio para session: {session_id}")
                    texto = self.transcriptor.transcribe_audio(temp_path)
                    
                    # Eliminar archivo temporal
                    try:
                        os.remove(temp_path)
                    except Exception as e:
                        logger.warning(f"No se pudo eliminar archivo temporal: {e}")
                    
                    if not texto:
                        return {"error": "No se pudo transcribir el audio", "status": "error"}
                    
                    # Registrar la transcripción en logs
                    logger.info(f"Transcripción para session {session_id}: {texto}")
                    
                elif "multipart/form-data" in content_type and not voice_enabled:
                    # Si se recibe un archivo de audio pero el procesamiento de voz no está habilitado
                    return {
                        "error": "El procesamiento de voz no está habilitado en esta instancia. Configure 'enable_voice=True' en create_behemot_app()",
                        "status": "error"
                    }
                else:
                    # Caso de mensaje de texto (JSON)
                    data = await request.json()
                    session_id, texto = self.api_connector.extraer_mensaje(data)
                    
                    if not session_id or not texto:
                        return {"error": "Formato de mensaje inválido", "status": "error"}
                
                # Indicador para el log (no visible al usuario)
                logger.info(f"Mensaje recibido de session: {session_id}")
                
                # Generar respuesta
                respuesta = await self.asistente.generar_respuesta(str(session_id), texto)
                
                # Verificar si hay mensajes divididos
                if "\n---SPLIT_MESSAGE---\n" in respuesta:
                    mensajes = respuesta.split("\n---SPLIT_MESSAGE---\n")
                    # Usar el último mensaje como la respuesta principal
                    respuesta_final = mensajes[-1].strip()
                    
                    # Mensajes intermedios
                    mensajes_intermedios = [m.strip() for m in mensajes[:-1] if m.strip()]
                    
                    # Preparar y enviar respuesta
                    response_data = self.api_connector.preparar_respuesta(respuesta_final)
                    response_data["status"] = "ok"
                    
                    # Solo incluir transcripción si viene de una solicitud de audio
                    if "multipart/form-data" in content_type and voice_enabled:
                        response_data["transcription"] = texto
                    
                    # Agregar mensajes intermedios si existen
                    if mensajes_intermedios:
                        response_data["intermediate_messages"] = mensajes_intermedios
                    
                    return response_data
                else:
                    # Respuesta simple, sin división
                    response_data = self.api_connector.preparar_respuesta(respuesta)
                    response_data["status"] = "ok"
                    
                    # Solo incluir transcripción si viene de una solicitud de audio
                    if "multipart/form-data" in content_type and voice_enabled:
                        response_data["transcription"] = texto
                    
                    return response_data
                    
            except Exception as e:
                logger.error(f"Error procesando mensaje: {str(e)}", exc_info=True)
                return {"error": f"Error interno: {str(e)}", "status": "error"}
        
        # Registrar el estado de la funcionalidad de voz
        if voice_enabled:
            logger.info("Conector de API configurado con soporte para procesamiento de voz")
        else:
            logger.info("Conector de API configurado (procesamiento de voz deshabilitado)")
    
    def setup_whatsapp_connector(self, fastapi_app: FastAPI) -> None:
        """
        Configura el conector de WhatsApp y sus endpoints.
        Args:
            fastapi_app: Aplicación FastAPI a configurar
        """
        from fastapi import Query
        from fastapi.responses import PlainTextResponse
        import os
        
        # Obtener tokens desde configuración
        api_token = self.config.get("WHATSAPP_TOKEN")
        phone_number_id = self.config.get("WHATSAPP_PHONE_ID") 
        verify_token = self.config.get("WHATSAPP_VERIFY_TOKEN")
        
        # Priorizar la configuración específica de WhatsApp
        whatsapp_webhook_url = self.config.get("WHATSAPP_WEBHOOK_URL", "")
        
        # Si no hay URL específica para WhatsApp, usar la URL general
        if not whatsapp_webhook_url:
            webhook_url = self.config.get("WEBHOOK_URL", "")
            
            # WhatsApp normalmente espera una ruta específica como /whatsapp-webhook
            if webhook_url and not webhook_url.endswith("/whatsapp-webhook"):
                whatsapp_webhook_url = webhook_url + "/whatsapp-webhook"
            else:
                whatsapp_webhook_url = webhook_url
        
        logger.info(f"Configurando WhatsApp con phone_id={phone_number_id}, verify_token={verify_token}")
        logger.info(f"URL de webhook para WhatsApp: {whatsapp_webhook_url}")
        
        if not api_token or not phone_number_id:
            logger.error("No se encontró WHATSAPP_TOKEN o WHATSAPP_PHONE_ID en la configuración")
            return
            
        if not WHATSAPP_AVAILABLE:
            logger.error("Conector de WhatsApp no disponible. Módulo no encontrado.")
            return
            
        # Inicializar el conector con el token de API y el phone ID
        self.whatsapp_connector = WhatsAppConnector(api_token, phone_number_id)
        
        @fastapi_app.get("/whatsapp-webhook")
        async def verify_whatsapp_webhook(
            hub_mode: str = Query(None, alias="hub.mode"),
            hub_verify_token: str = Query(None, alias="hub.verify_token"),
            hub_challenge: str = Query(None, alias="hub.challenge")
        ):
            """Endpoint para verificar el webhook de WhatsApp."""
            logger.info(f"Recibida solicitud de verificación: modo={hub_mode}, token={hub_verify_token}, challenge={hub_challenge}")
            
            # Verificar el token con el token de verificación configurado
            if not verify_token:
                logger.error("No se ha configurado WHATSAPP_VERIFY_TOKEN")
                return PlainTextResponse("Token de verificación no configurado", status_code=400)
                
            if hub_mode == "subscribe" and hub_verify_token == verify_token:
                logger.info(f"Verificación exitosa, devolviendo challenge: {hub_challenge}")
                return PlainTextResponse(hub_challenge)
            else:
                logger.warning(f"Verificación fallida: token recibido={hub_verify_token}, esperado={verify_token}")
                return PlainTextResponse("Verificación fallida", status_code=403)
        
        @fastapi_app.post("/whatsapp-webhook")
        async def procesar_mensaje_whatsapp(request: Request):
            """Endpoint para recibir mensajes de WhatsApp."""
            try:
                update = await request.json()
                logger.debug(f"Mensaje de WhatsApp recibido: {update}")
                
                # Verificar que sea un mensaje
                entry = update.get("entry", [{}])[0]
                changes = entry.get("changes", [{}])[0]
                value = changes.get("value", {})
                
                if "messages" not in value:
                    logger.debug("No se encontraron mensajes en la actualización")
                    return {"status": "ok"}
                    
                # Extraer número de teléfono y mensaje
                phone_number, mensaje = self.whatsapp_connector.extraer_mensaje(update)
                
                if mensaje is None or phone_number is None:
                    logger.debug("No se pudo extraer número de teléfono o mensaje")
                    return {"status": "ok"}
                
                logger.info(f"Mensaje recibido de {phone_number}: tipo={mensaje['type']}")
                
                if mensaje["type"] == "text":
                    texto = mensaje["content"]
                    logger.info(f"Mensaje de texto: {texto[:50]}...")
                elif mensaje["type"] == "voice" and self.transcriptor:
                    # Transcribir audio a texto
                    audio_path = mensaje["content"]
                    logger.info(f"Transcribiendo audio de {phone_number}")
                    texto = self.transcriptor.transcribe_audio(audio_path)
                    logger.info(f"Audio transcrito: {texto[:50]}...")
                    
                    # Limpiar archivo temporal
                    try:
                        os.remove(audio_path)
                        logger.debug(f"Archivo temporal eliminado: {audio_path}")
                    except Exception as e:
                        logger.warning(f"No se pudo eliminar archivo temporal: {e}")
                else:
                    logger.debug(f"Tipo de mensaje no soportado: {mensaje['type']}")
                    return {"status": "ok"}
                
                if texto:
                    # Generar respuesta del asistente
                    logger.info(f"Generando respuesta para {phone_number}")
                    respuesta = await self.asistente.generar_respuesta(str(phone_number), texto)
                    
                    # Enviar respuesta
                    logger.info(f"Enviando respuesta a {phone_number}")
                    await self.whatsapp_connector.procesar_respuesta(phone_number, respuesta)
                    logger.info("Respuesta enviada correctamente")
                else:
                    logger.warning(f"No se pudo extraer texto del mensaje")
                
                return {"status": "ok"}
            except Exception as e:
                logger.error(f"Error procesando mensaje de WhatsApp: {str(e)}", exc_info=True)
                return {"status": "error", "message": str(e)}
        
        logger.info("Conector de WhatsApp configurado correctamente")

    

    def setup_google_chat_connector(self, fastapi_app: FastAPI) -> None:
        """
        Configura el conector de Google Chat y sus endpoints.
        Args:
            fastapi_app: Aplicación FastAPI a configurar
        """
        # Verificar que las variables GC_* necesarias estén configuradas
        required_vars = ["GC_PROJECT_ID", "GC_PRIVATE_KEY", "GC_CLIENT_EMAIL"]
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        
        if missing_vars:
            logger.error(f"No se puede configurar Google Chat: Faltan variables de entorno: {', '.join(missing_vars)}")
            return
        
        # Obtener la URL del webhook específica para Google Chat
        webhook_url = os.environ.get("GC_WEBHOOK_URL", "")
        
        # Si no hay una URL específica, intentar construir una a partir de la URL general
        if not webhook_url:
            general_webhook = os.environ.get("WEBHOOK_URL", "")
            if general_webhook:
                webhook_url = f"{general_webhook.rstrip('/')}/google-chat-webhook"
        
        # Registrar dónde escuchará el webhook
        if webhook_url:
            logger.info(f"Configurando webhook para Google Chat en: {webhook_url}")
        else:
            logger.warning("No se ha especificado GC_WEBHOOK_URL. Asegúrate de configurar el webhook manualmente.")
        
        try:
            # Importar e inicializar el conector
            from behemot_framework.connectors.google_chat_connector import GoogleChatConnector
            self.google_chat_connector = GoogleChatConnector()

            if self.transcriptor:
                self.google_chat_connector.transcriptor = self.transcriptor
                logger.info("Servicio de transcripción habilitado para Google Chat")
            else:
                logger.warning("Transcripción de voz no habilitada para Google Chat")
            
            # Configurar el endpoint para el webhook
            @fastapi_app.post("/google-chat-webhook")
            async def procesar_mensaje_google_chat(request: Request):
                try:
                    update = await request.json()
                    
                    # Verificar el tipo de evento (solo procesar mensajes)
                    if update.get("type") != "MESSAGE":
                        return {"text": "Evento no procesable"}
                    
                    # Extraer el mensaje
                    chat_id, mensaje = self.google_chat_connector.extraer_mensaje(update)
                    
                    if mensaje is None or chat_id is None:
                        return {"text": "No se pudo procesar el mensaje"}
                    
                    # Manejar diferentes tipos de mensaje
                    if mensaje["type"] == "text":
                        texto = mensaje["content"]
                        # Generar respuesta
                        respuesta = await self.asistente.generar_respuesta(str(chat_id), texto)
                        
                        # Aplicar conversión de Markdown a formato Google Chat
                        from behemot_framework.utils.markdown_converter import markdown_to_google_chat
                        respuesta_formateada = markdown_to_google_chat(respuesta)
                        
                        logger.info(f"📝 Respuesta original (primeros 100 chars): {respuesta[:100]}...")
                        logger.info(f"✨ Respuesta formateada (primeros 100 chars): {respuesta_formateada[:100]}...")
                        
                        return {"text": respuesta_formateada}
                    
                    elif mensaje["type"] == "audio_url":
                        # Respuesta informativa para mensajes de audio
                        return {"text": "He recibido tu mensaje de audio, pero actualmente no puedo procesarlo. Por favor, envía tu mensaje como texto."}
                    
                    elif mensaje["type"] == "unsupported_audio":
                        # Respuesta para audio cuando no hay transcripción
                        return {"text": 'He recibido tu mensaje de audio, pero la transcripción de voz no está habilitada en este bot. Por favor, envía tu mensaje como texto.'}
                    
                    # Por defecto, si no es un tipo conocido
                    return {"text": "No puedo procesar este tipo de mensaje. Por favor, envía texto."}
                    
                except Exception as e:
                    logger.error(f"Error procesando mensaje: {str(e)}", exc_info=True)
                    return {"text": f"Lo siento, ocurrió un error al procesar tu mensaje: {str(e)}"}
        except Exception as e:
            logger.error(f"Error al configurar Google Chat: {str(e)}", exc_info=True)

    def setup_test_local_interface(self) -> None:
        """
        Configura la interfaz de prueba local usando Gradio.
        Ejecuta la interfaz en un hilo separado para no bloquear FastAPI.
        """
        try:
            from behemot_framework.connectors.gradio_connector import GradioConnector
            from behemot_framework.tooling import get_tool_definitions
            import threading
            import time
            
            logger.info("🚀 Configurando interfaz de prueba local con Gradio...")
            
            # Crear el conector Gradio
            gradio_connector = GradioConnector(
                assistant=self.asistente,
                tools_registry=get_tool_definitions(),
                transcriptor=self.transcriptor
            )
            
            def launch_gradio():
                """Función para lanzar Gradio en un hilo separado"""
                try:
                    # Esperar un poco para que FastAPI termine de inicializar
                    time.sleep(2)
                    
                    # Lanzar la interfaz Gradio
                    gradio_connector.launch(port=7860, share=False)
                    
                except Exception as e:
                    logger.error(f"Error al lanzar interfaz Gradio: {e}", exc_info=True)
            
            # Lanzar Gradio en un hilo separado para no bloquear FastAPI
            gradio_thread = threading.Thread(target=launch_gradio, daemon=True)
            gradio_thread.start()
            
            # Marcar que Gradio está habilitado para mostrar en logs de startup
            self._gradio_enabled = True
            
            logger.info("✅ Interfaz de prueba local configurada")
            
        except ImportError:
            logger.error("❌ No se pudo importar Gradio. Instala con: pip install gradio")
        except Exception as e:
            logger.error(f"❌ Error al configurar interfaz de prueba local: {e}", exc_info=True)

    def initialize_app(self, fastapi_app: FastAPI) -> None:
        """
        Inicializa la aplicación con configuraciones comunes.
        Args:
            fastapi_app: Aplicación FastAPI a configurar
        """
        # Guardar una referencia a self para usarla en las funciones internas
        factory = self

         # Cargar herramientas genéricas del framework
        try:
            import behemot_framework.core.tools.date_tools
            logger.info("Herramientas genéricas del framework cargadas automáticamente")
        except ImportError:
            logger.warning("No se pudieron cargar las herramientas genéricas del framework")

        # Importar herramientas RAG genéricas
        if factory.config.get("ENABLE_RAG", False):
            try:
                import behemot_framework.rag.tools
                logger.info("✓ Herramientas RAG genéricas registradas")
                
                # Verificar que las herramientas se registraron correctamente
                from behemot_framework.tooling import get_tool_definitions
                tool_defs = get_tool_definitions()
                rag_tools = [t for t in tool_defs if t['name'] in ['search_documents', 'list_document_collections']]
                logger.info(f"  → Herramientas RAG disponibles: {[t['name'] for t in rag_tools]}")
                
            except Exception as e:
                logger.error(f"Error al registrar herramientas RAG: {str(e)}")
        else:
            logger.info("ℹ RAG deshabilitado - Herramientas RAG no registradas")

        # Importar comandos especiales
        try:
            import behemot_framework.commandos.command_handler
            logger.info("Comandos especiales registrados")
        except ImportError:
            logger.warning("No se pudieron cargar los comandos especiales")

        # Configurar rutas de status (nuevo)
        try:
            from behemot_framework.routes.status import setup_routes
            # Pasar la misma ruta de configuración que se usó para crear la aplicación
            setup_routes(fastapi_app, config_path=self.config.get("_config_path"))
            logger.info("Dashboard de estado configurado en /status")
        except ImportError:
            logger.warning("No se pudo cargar el módulo de status. El dashboard no estará disponible.")

        # Agregar eventos de inicio
        @fastapi_app.on_event("startup")
        async def startup_event():
            # Forzar el nivel de logging para asegurar que se muestre
            import logging
            logging.basicConfig(level=logging.INFO, force=True)
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)
            
            print("=" * 60)
            print("🚀 Iniciando aplicación Behemot Framework...")
            print("=" * 60)
            logger.info("=" * 60)
            logger.info("🚀 Iniciando aplicación Behemot Framework...")
            logger.info("=" * 60)
            
            # 1. Mostrar configuración del modelo
            model_provider = factory.config.get("MODEL_PROVIDER", "openai")
            model_name = factory.config.get("MODEL_NAME", "default")
            print(f"✓ Modelo configurado: {model_provider} - {model_name}")
            logger.info(f"✓ Modelo configurado: {model_provider} - {model_name}")
            
            # 2. Estado de Redis con diagnóstico
            redis_url = factory.config.get("REDIS_PUBLIC_URL", "")
            if redis_url:
                # Importar y ejecutar diagnóstico
                from behemot_framework.context import redis_diagnostics
                redis_status = redis_diagnostics()
                
                if redis_status.get("connection_status") and redis_status.get("can_write") and redis_status.get("can_read"):
                    logger.info("✅ Redis configurado y funcionando correctamente")
                    logger.info(f"  → URL: {redis_url}")
                else:
                    logger.error("❌ Redis configurado pero con problemas de conectividad")
                    logger.error(f"  → URL: {redis_url}")
                    logger.error(f"  → Conexión: {'✅' if redis_status.get('connection_status') else '❌'}")
                    logger.error(f"  → Escritura: {'✅' if redis_status.get('can_write') else '❌'}")
                    logger.error(f"  → Lectura: {'✅' if redis_status.get('can_read') else '❌'}")
                    if "error" in redis_status:
                        logger.error(f"  → Error: {redis_status['error']}")
            else:
                logger.warning("⚠ Redis NO configurado - Contexto no persistente")
                logger.warning("  → Configure REDIS_PUBLIC_URL para habilitar persistencia")
            
            # 3. Estado de seguridad
            if hasattr(factory.asistente, 'safety_filter') and factory.asistente.safety_filter:
                logger.info(f"✓ Filtro de seguridad activado (nivel: {factory.config.get('SAFETY_LEVEL', 'medium')})")
            else:
                logger.info("ℹ Filtro de seguridad desactivado")
            
            # 4. Estado de RAG
            if factory.config.get("ENABLE_RAG", False):
                print("🔍 RAG habilitado - Inicializando...")
                logger.info("🔍 RAG habilitado - Inicializando...")
                rag_provider = factory.config.get("RAG_EMBEDDING_PROVIDER", "openai")
                rag_model = factory.config.get("RAG_EMBEDDING_MODEL", "default")
                print(f"  → Proveedor de embeddings: {rag_provider}")
                print(f"  → Modelo de embeddings: {rag_model}")
                logger.info(f"  → Proveedor de embeddings: {rag_provider}")
                logger.info(f"  → Modelo de embeddings: {rag_model}")
                
                if factory.config.get("RAG_FOLDERS"):
                    folders = factory.config.get("RAG_FOLDERS")
                    print(f"  → Carpetas a indexar: {folders}")
                    logger.info(f"  → Carpetas a indexar: {folders}")
                    from behemot_framework.startup import initialize_rag
                    await initialize_rag(factory.config)
                else:
                    print("  ⚠ No hay carpetas RAG configuradas")
                    logger.warning("  ⚠ No hay carpetas RAG configuradas")
            else:
                print("ℹ RAG deshabilitado")
                logger.info("ℹ RAG deshabilitado")
            
            # 5. Mostrar herramientas cargadas
            from behemot_framework.tooling import get_tool_definitions
            tool_defs = get_tool_definitions()
            if tool_defs:
                logger.info(f"🔧 Herramientas disponibles ({len(tool_defs)}):")
                for tool in tool_defs:
                    logger.info(f"  → {tool['name']}: {tool.get('description', 'Sin descripción')[:60]}...")
            else:
                logger.warning("⚠ No hay herramientas cargadas")
            
            # 6. Estado de conectores - obtenido desde la configuración de la factory
            conectores = []
            if hasattr(factory, 'telegram_connector') and factory.telegram_connector:
                conectores.append("Telegram")
            if hasattr(factory, 'api_connector') and factory.api_connector:
                conectores.append("API REST")
            if hasattr(factory, 'whatsapp_connector') and factory.whatsapp_connector:
                conectores.append("WhatsApp")
            
            if conectores:
                logger.info(f"📡 Conectores activados: {', '.join(conectores)}")
            
            # 7. Estado de voz
            if factory.transcriptor:
                logger.info("🎤 Procesamiento de voz activado")
            
            logger.info("=" * 60)
            logger.info("✅ Aplicación iniciada correctamente")
            logger.info("=" * 60)
            
            # Mostrar link de Gradio si está habilitado
            if hasattr(factory, '_gradio_enabled') and factory._gradio_enabled:
                logger.info("")
                logger.info("🌐 Interfaz de prueba local disponible:")
                logger.info("   http://localhost:7860")
                logger.info("")
            
        # Configurar rutas básicas
        @fastapi_app.get("/")
        async def root():
            return {
                "name": "Behemot Framework",
                "version": self.config.get("VERSION", "1.0.0"),
                "description": "Framework modular para asistentes IA"
            }
            
        @fastapi_app.get("/health")
        async def health_check():
            return {"status": "ok"}
        


def create_behemot_app(
                        enable_telegram: bool = False,
                        enable_api: bool = False,
                        enable_whatsapp: bool = False,
                        enable_google_chat: bool = False, 
                        enable_voice: bool = False,  # Valor predeterminado es False
                        enable_test_local: bool = False,  # Nueva opción para interfaz Gradio
                        use_tools: List[str] = None,
                        config_path: Optional[str] = None
                    ) -> FastAPI:
    """
    Crea y configura la aplicación Behemot con los componentes solicitados.
    Args:
        enable_telegram: Activar conector de Telegram
        enable_api: Activar conector de API REST
        enable_whatsapp: Activar conector de WhatsApp (si está implementado)
        enable_google_chat: Activar conector de Google Chat
        enable_voice: Activar procesamiento de voz
        enable_test_local: Activar interfaz de prueba local con Gradio
        use_tools: Lista de nombres de herramientas a cargar ("all" para todas)
        config_path: Ruta al archivo de configuración personalizado
        
    Returns:
        FastAPI: Aplicación configurada con los endpoints necesarios
    """
    # Cargar configuración
    config = load_config(config_path)

    # Almacenar la ruta de configuración en la propia configuración para acceso posterior
    config["_config_path"] = config_path
    
    # Crear la app base
    app = FastAPI(title="Behemot Framework", description="Framework modular para asistentes IA")
    
    # Inicializar factory con la configuración
    factory = BehemotFactory(config)
    
    # Cargar herramientas solicitadas
    if use_tools:
        if "all" in use_tools:
            factory.load_all_tools()
        else:
            factory.load_tools(use_tools)
    
    # Configurar conectores solicitados
    if enable_telegram:
        factory.setup_telegram_connector(app)
        
    if enable_api:
        factory.setup_api_connector(app)
        
    if enable_whatsapp:
        factory.setup_whatsapp_connector(app)

    if enable_google_chat:
        factory.setup_google_chat_connector(app)
    
    if enable_test_local:
        factory.setup_test_local_interface()
    
    # Inicializar componentes comunes (logging, eventos de inicio, etc.)
    factory.initialize_app(app)
    
    return app
