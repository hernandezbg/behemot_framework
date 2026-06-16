# app/factory.py
import asyncio
import importlib
import inspect
import json
import os
import logging
import pkgutil
import hmac
import hashlib
import re
import secrets
from typing import List, Dict, Any, Optional, Callable
from fastapi import FastAPI, Request, HTTPException

from behemot_framework.config import Config, load_config
from behemot_framework.models import ModelFactory
from behemot_framework.assistants.assistant import Assistant
from behemot_framework.connectors.telegram_connector import TelegramConnector
from behemot_framework.connectors.api_connector import ApiConnector
from behemot_framework.services.transcription_service import TranscriptionService
from behemot_framework.services.tts_service import TTSService

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
            self.transcriptor = TranscriptionService(
                api_key=config.get("GPT_API_KEY"),
                language=config.get("TRANSCRIPTION_LANGUAGE")
            )
            self.tts_service = TTSService(
                provider=config.get("TTS_PROVIDER", "openai"),
                api_key=config.get("GPT_API_KEY"),
                model=config.get("TTS_MODEL", "tts-1"),
                voice=config.get("TTS_VOICE", "alloy"),
                elevenlabs_api_key=config.get("ELEVENLABS_API_KEY"),
                elevenlabs_voice_id=config.get("ELEVENLABS_VOICE_ID", "Rachel"),
                elevenlabs_model=config.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
            )
        else:
            self.transcriptor = None
            self.tts_service = None
            
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
        self.telegram_connector.tts_service = self.tts_service
        self.telegram_connector.response_mode = self.config.get("TELEGRAM_RESPONSE_MODE", "text")

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

        # Resolver el secret_token para validar requests entrantes.
        # Si no está configurado, generamos uno efímero — funciona en single-instance
        # pero para multi-réplica el operador debe definir TELEGRAM_WEBHOOK_SECRET.
        webhook_secret = self.config.get("TELEGRAM_WEBHOOK_SECRET", "")
        if not webhook_secret:
            webhook_secret = secrets.token_urlsafe(32)
            logger.warning(
                "TELEGRAM_WEBHOOK_SECRET no configurado — generado uno efímero. "
                "En deploys multi-réplica define TELEGRAM_WEBHOOK_SECRET en config."
            )
        # Guardarlo en self para que el handler tenga acceso vía closure
        self._telegram_webhook_secret = webhook_secret

        # Configurar webhook si está definido
        if telegram_webhook_url:
            from behemot_framework.startup import set_telegram_webhook
            logger.info(f"Configurando webhook de Telegram: {telegram_webhook_url}")
            # Pasar el secret_token a Telegram para que firme cada update
            set_telegram_webhook(token, telegram_webhook_url, secret_token=webhook_secret)

        @fastapi_app.post("/webhook")
        async def procesar_mensaje_telegram(request: Request):
            # Validar X-Telegram-Bot-Api-Secret-Token: rechazar updates no firmados
            # por nuestro secret. Sin esta validación, cualquier atacante con la URL
            # del webhook puede suplantar mensajes de cualquier usuario.
            received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if not hmac.compare_digest(received_secret, self._telegram_webhook_secret):
                logger.warning("Webhook Telegram rechazado: secret_token inválido o ausente")
                raise HTTPException(status_code=401, detail="Invalid webhook signature")

            update = await request.json()
            chat_id, mensaje = self.telegram_connector.extraer_mensaje(update)
            
            if mensaje is None:
                return {"status": "ok"}
            
            # Registrar usuario en el tracker
            try:
                from behemot_framework.users import get_user_tracker
                user_tracker = get_user_tracker()
                
                # Extraer metadata completa del usuario desde el update
                user_metadata = {}
                if "message" in update and "from" in update["message"]:
                    from_user = update["message"]["from"]
                    chat_info = update["message"]["chat"]
                    
                    user_metadata = {
                        "telegram_user_id": from_user.get("id"),
                        "username": from_user.get("username"),
                        "first_name": from_user.get("first_name"),
                        "last_name": from_user.get("last_name"),
                        "language_code": from_user.get("language_code"),
                        "is_bot": from_user.get("is_bot", False),
                        "is_premium": from_user.get("is_premium", False),
                        "chat_type": chat_info.get("type"),  # private, group, supergroup, channel
                        "chat_title": chat_info.get("title") if chat_info.get("type") != "private" else None,
                        "phone_number": None,  # Telegram no expone esto normalmente
                        "display_name": f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip(),
                        "username_handle": f"@{from_user.get('username')}" if from_user.get('username') else None
                    }
                
                user_tracker.register_user(str(chat_id), "telegram", user_metadata)
                user_tracker.update_last_seen(str(chat_id))
            except Exception as e:
                logger.warning(f"Error registrando usuario Telegram {chat_id}: {e}")
            
            # Indicar que el bot está "escribiendo"
            self.telegram_connector.enviar_accion(chat_id, "typing")
            
            texto = None
            imagen_path = None
            
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
            elif mensaje["type"] == "image":
                # Manejar mensaje con imagen
                imagen_path = mensaje["content"]
                caption = mensaje.get("caption", "")
                texto = caption if caption else "¿Qué puedes decirme sobre esta imagen?"
                logging.info(f"Imagen recibida del chat {chat_id}: {imagen_path}, caption: '{caption}'")
            else:
                return {"status": "ok"}
            
            if texto:
                # --- Handoff check ---
                from behemot_framework.services.handoff_service import (
                    is_enabled as _hoff_on, is_in_handoff, forward_message,
                    is_trigger, start_handoff, build_history,
                )
                if _hoff_on():
                    _uid = str(chat_id)
                    if is_in_handoff(_uid):
                        await asyncio.to_thread(forward_message, _uid, texto)
                        return {"status": "ok"}
                    _triggers = self.config.get("HANDOFF_TRIGGERS", [])
                    if _triggers and is_trigger(texto, _triggers):
                        _cb = self.config.get("HANDOFF_CALLBACK_URL", "").rstrip("/")
                        if not _cb:
                            logger.error("HANDOFF_CALLBACK_URL no configurado — no se puede iniciar handoff")
                        else:
                            await asyncio.to_thread(
                                start_handoff, "telegram", _uid, _uid,
                                f"{_cb}/handoff/webhook", build_history(_uid),
                            )
                        _msg = self.config.get("HANDOFF_START_MESSAGE",
                                               "Te estamos conectando con un asesor, en breve te atienden.")
                        self.telegram_connector.enviar_mensaje(chat_id, _msg)
                        return {"status": "ok"}
                # --- End handoff check ---

                self.telegram_connector.enviar_accion(chat_id, "typing")
                respuesta = await self.asistente.generar_respuesta(str(chat_id), texto, imagen_path)
                # Verificar si el conector tiene método procesar_respuesta
                if hasattr(self.telegram_connector, 'procesar_respuesta'):
                    await self.telegram_connector.procesar_respuesta(chat_id, respuesta, mensaje["type"])
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

        # Configuración de auth + rate limiting + límites de tamaño.
        api_auth_mode = (self.config.get("API_AUTH_MODE", "none") or "none").lower()
        api_keys = [k.strip() for k in (self.config.get("API_KEYS") or []) if k and k.strip()]
        rate_limit_per_minute = int(self.config.get("API_RATE_LIMIT_PER_MINUTE", 60) or 0)
        max_request_size = int(self.config.get("API_MAX_REQUEST_SIZE", 10 * 1024 * 1024))
        max_audio_size = int(self.config.get("API_MAX_AUDIO_SIZE", 25 * 1024 * 1024))

        if api_auth_mode == "api_key" and not api_keys:
            logger.warning(
                "API_AUTH_MODE='api_key' pero API_KEYS está vacía — la API "
                "rechazará todas las requests hasta que se configuren claves."
            )
        if api_auth_mode == "none":
            logger.warning(
                "API_AUTH_MODE='none' — /api/chat queda accesible sin auth. "
                "Solo recomendado detrás de un gateway/firewall."
            )

        # Rate limiting in-memory por IP (sin nuevas dependencias). Para deploys
        # multi-réplica considera mover este contador a Redis.
        from collections import defaultdict, deque
        import time as _time
        _request_log: Dict[str, deque] = defaultdict(deque)

        def _enforce_rate_limit(client_ip: str) -> bool:
            if rate_limit_per_minute <= 0:
                return True
            now = _time.monotonic()
            window_start = now - 60.0
            dq = _request_log[client_ip]
            while dq and dq[0] < window_start:
                dq.popleft()
            if len(dq) >= rate_limit_per_minute:
                return False
            dq.append(now)
            return True

        def _enforce_api_auth(request: Request) -> None:
            if api_auth_mode != "api_key":
                return
            received = request.headers.get("X-API-Key", "")
            if not received or not api_keys:
                raise HTTPException(status_code=401, detail="Missing API key")
            for valid_key in api_keys:
                if hmac.compare_digest(received, valid_key):
                    return
            raise HTTPException(status_code=401, detail="Invalid API key")

        @fastapi_app.post("/api/chat")
        async def process_api_message(request: Request):
            """Endpoint para recibir mensajes de texto o audio de cualquier cliente via API."""
            # 1. Auth — antes que cualquier otro procesamiento.
            _enforce_api_auth(request)

            # 2. Rate limit por IP del cliente.
            client_ip = request.client.host if request.client else "unknown"
            if not _enforce_rate_limit(client_ip):
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

            # 3. Validar tamaño del body via Content-Length (early reject).
            content_length_header = request.headers.get("Content-Length")
            if content_length_header:
                try:
                    declared_size = int(content_length_header)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid Content-Length")
                ctype_check = request.headers.get("Content-Type", "")
                size_cap = max_audio_size if "multipart/form-data" in ctype_check else max_request_size
                if declared_size > size_cap:
                    raise HTTPException(status_code=413, detail="Payload too large")

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
                    
                    # Guardar el archivo temporalmente. Limitamos el tamaño
                    # efectivo aunque el Content-Length declarado sea menor al cap
                    # (defensa contra clientes que mienten en el header).
                    import time
                    import os
                    audio_content = await audio_file.read()
                    if len(audio_content) > max_audio_size:
                        raise HTTPException(status_code=413, detail="Audio too large")
                    safe_session = re.sub(r"[^A-Za-z0-9_\-]", "_", str(session_id))[:40]
                    temp_path = f"temp_audio_{safe_session}_{int(time.time())}.ogg"
                    with open(temp_path, "wb") as f:
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
                
                # Registrar usuario en el tracker
                try:
                    from behemot_framework.users import get_user_tracker
                    user_tracker = get_user_tracker()
                    
                    # Extraer metadata básica para API REST
                    user_metadata = {
                        "session_id": session_id,
                        "user_agent": request.headers.get("User-Agent"),
                        "ip_address": request.client.host if hasattr(request, 'client') and request.client else None,
                        "platform_info": "api_rest",
                        "phone_number": None,
                        "display_name": session_id,
                        "chat_type": "api",
                        "referer": request.headers.get("Referer"),
                        "content_type": request.headers.get("Content-Type")
                    }
                    
                    user_tracker.register_user(str(session_id), "api", user_metadata)
                    user_tracker.update_last_seen(str(session_id))
                except Exception as e:
                    logger.warning(f"Error registrando usuario API {session_id}: {e}")
                
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
        
        logger.info(f"Configurando WhatsApp con phone_id={phone_number_id} (verify_token configurado={'sí' if verify_token else 'no'})")
        logger.info(f"URL de webhook para WhatsApp: {whatsapp_webhook_url}")
        
        if not api_token or not phone_number_id:
            logger.error("No se encontró WHATSAPP_TOKEN o WHATSAPP_PHONE_ID en la configuración")
            return
            
        if not WHATSAPP_AVAILABLE:
            logger.error("Conector de WhatsApp no disponible. Módulo no encontrado.")
            return
            
        # Inicializar el conector con el token de API y el phone ID
        self.whatsapp_connector = WhatsAppConnector(api_token, phone_number_id)
        self.whatsapp_connector.tts_service = self.tts_service
        self.whatsapp_connector.response_mode = self.config.get("WHATSAPP_RESPONSE_MODE", "text")

        # App Secret de Meta para validar la firma HMAC-SHA256 de cada POST.
        # Sin esto cualquiera con la URL del webhook puede inyectar mensajes
        # forjados como cualquier número.
        whatsapp_app_secret = self.config.get("WHATSAPP_APP_SECRET", "")
        if not whatsapp_app_secret:
            logger.warning(
                "WHATSAPP_APP_SECRET no configurado: el webhook ACEPTARÁ cualquier "
                "POST sin validar firma. Configurar el App Secret de Meta es "
                "obligatorio en producción."
            )
        self._whatsapp_app_secret = whatsapp_app_secret

        @fastapi_app.get("/whatsapp-webhook")
        async def verify_whatsapp_webhook(
            hub_mode: str = Query(None, alias="hub.mode"),
            hub_verify_token: str = Query(None, alias="hub.verify_token"),
            hub_challenge: str = Query(None, alias="hub.challenge")
        ):
            """Endpoint para verificar el webhook de WhatsApp."""
            logger.info(f"Recibida solicitud de verificación de webhook WhatsApp (mode={hub_mode})")
            
            # Verificar el token con el token de verificación configurado
            if not verify_token:
                logger.error("No se ha configurado WHATSAPP_VERIFY_TOKEN")
                return PlainTextResponse("Token de verificación no configurado", status_code=400)
                
            if hub_mode == "subscribe" and hub_verify_token == verify_token:
                logger.info("Verificación de webhook WhatsApp exitosa")
                return PlainTextResponse(hub_challenge)
            else:
                logger.warning("Verificación de webhook WhatsApp fallida (token no coincide o mode inválido)")
                return PlainTextResponse("Verificación fallida", status_code=403)
        
        @fastapi_app.post("/whatsapp-webhook")
        async def procesar_mensaje_whatsapp(request: Request):
            """Endpoint para recibir mensajes de WhatsApp."""
            try:
                # Leer el body CRUDO antes de parsear: la firma HMAC se calcula
                # sobre los bytes exactos enviados por Meta, no sobre el JSON
                # reserializado.
                raw_body = await request.body()

                # Validar firma X-Hub-Signature-256 si hay App Secret configurado.
                # Si no hay secret, dejamos pasar (con warning emitido en setup) para
                # facilitar entornos de desarrollo, pero el plan de seguridad exige
                # configurarlo en producción.
                if self._whatsapp_app_secret:
                    received_sig = request.headers.get("X-Hub-Signature-256", "")
                    if not received_sig.startswith("sha256="):
                        logger.warning("Webhook WhatsApp rechazado: header X-Hub-Signature-256 ausente o malformado")
                        raise HTTPException(status_code=401, detail="Missing signature")

                    expected_sig = "sha256=" + hmac.new(
                        self._whatsapp_app_secret.encode("utf-8"),
                        raw_body,
                        hashlib.sha256,
                    ).hexdigest()

                    if not hmac.compare_digest(received_sig, expected_sig):
                        logger.warning("Webhook WhatsApp rechazado: firma HMAC inválida")
                        raise HTTPException(status_code=401, detail="Invalid signature")

                # Solo después de validar parseamos el JSON
                import json as _json
                update = _json.loads(raw_body) if raw_body else {}
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
                
                # Registrar usuario en el tracker
                try:
                    from behemot_framework.users import get_user_tracker
                    user_tracker = get_user_tracker()
                    
                    # Extraer metadata completa del usuario WhatsApp
                    user_metadata = {
                        "phone_number": phone_number,
                        "wa_id": phone_number.replace('+', '').replace('-', ''),
                        "profile_name": None,
                        "display_name": phone_number,
                        "phone_formatted": phone_number,
                        "country_code": phone_number[:3] if phone_number.startswith('+') else None,
                        "is_business": False,
                        "chat_type": "private"
                    }
                    
                    # Intentar extraer información adicional del contacto
                    if "contacts" in value and value["contacts"]:
                        contact = value["contacts"][0]
                        profile = contact.get("profile", {})
                        
                        user_metadata.update({
                            "wa_id": contact.get("wa_id", user_metadata["wa_id"]),
                            "profile_name": profile.get("name"),
                            "display_name": profile.get("name") or phone_number
                        })
                    
                    user_tracker.register_user(str(phone_number), "whatsapp", user_metadata)
                    user_tracker.update_last_seen(str(phone_number))
                except Exception as e:
                    logger.warning(f"Error registrando usuario WhatsApp {phone_number}: {e}")
                
                logger.info(f"Mensaje recibido de {phone_number}: tipo={mensaje['type']}")

                _pre_transcribed = None  # reutilizado si el audio se transcribe durante el trigger check

                # --- Handoff intercept temprano (antes de transcripción) ---
                # Intercepta tanto texto como audio; el bloque inferior sólo
                # se ejecuta si NO estamos en handoff.
                from behemot_framework.services.handoff_service import (
                    is_enabled as _hoff_on, is_in_handoff, forward_message as _fwd_msg,
                    is_trigger, start_handoff, build_history,
                )
                if _hoff_on():
                    _uid = str(phone_number)
                    if is_in_handoff(_uid):
                        if mensaje["type"] == "text":
                            await asyncio.to_thread(_fwd_msg, _uid, mensaje["content"])
                        elif mensaje["type"] == "voice":
                            _raw_msgs = value.get("messages", [{}])
                            _audio_id = _raw_msgs[0].get("audio", {}).get("id", "") if _raw_msgs else ""
                            _media_url = None
                            if _audio_id:
                                _media_url = await asyncio.to_thread(
                                    self.whatsapp_connector.obtener_url_media, _audio_id
                                )
                            await asyncio.to_thread(
                                _fwd_msg, _uid, "[mensaje de voz]", "audio", _media_url
                            )
                            _lpath = mensaje.get("content", "")
                            if _lpath and os.path.isfile(_lpath):
                                try:
                                    os.remove(_lpath)
                                except OSError:
                                    pass
                        elif mensaje["type"] == "image":
                            _raw_msgs = value.get("messages", [{}])
                            _image_id = _raw_msgs[0].get("image", {}).get("id", "") if _raw_msgs else ""
                            _caption = _raw_msgs[0].get("image", {}).get("caption", "") if _raw_msgs else ""
                            _media_url = None
                            if _image_id:
                                _media_url = await asyncio.to_thread(
                                    self.whatsapp_connector.obtener_url_media, _image_id
                                )
                            await asyncio.to_thread(
                                _fwd_msg, _uid, _caption or "[imagen]", "image", _media_url
                            )
                            _lpath = mensaje.get("content", "")
                            if _lpath and os.path.isfile(_lpath):
                                try:
                                    os.remove(_lpath)
                                except OSError:
                                    pass
                        return {"status": "ok"}
                    _triggers = self.config.get("HANDOFF_TRIGGERS", [])
                    if _triggers:
                        _trigger_text = None
                        if mensaje["type"] == "text":
                            _trigger_text = mensaje["content"]
                        elif mensaje["type"] == "voice" and self.transcriptor:
                            _audio_path = mensaje.get("content", "")
                            if _audio_path:
                                _pre_transcribed = await asyncio.to_thread(
                                    self.transcriptor.transcribe_audio, _audio_path
                                )
                                _trigger_text = _pre_transcribed
                                logger.info("Audio transcrito para verificar trigger: %s...", (_trigger_text or "")[:50])
                        if _trigger_text and is_trigger(_trigger_text, _triggers):
                            _cb = self.config.get("HANDOFF_CALLBACK_URL", "").rstrip("/")
                            if not _cb:
                                logger.error("HANDOFF_CALLBACK_URL no configurado — no se puede iniciar handoff")
                            else:
                                _wa_name = ""
                                if "contacts" in value and value["contacts"]:
                                    _wa_name = value["contacts"][0].get("profile", {}).get("name", "") or ""
                                _display = f"{_wa_name} ({_uid})" if _wa_name else _uid
                                _history = build_history(_uid)
                                _history.append({"role": "user", "content": _trigger_text})
                                await asyncio.to_thread(
                                    start_handoff, "whatsapp", _uid, _display,
                                    f"{_cb}/handoff/webhook", _history,
                                )
                            # Limpiar temp si se transcribió el audio
                            if _pre_transcribed and mensaje.get("content") and os.path.isfile(mensaje["content"]):
                                try:
                                    os.remove(mensaje["content"])
                                except OSError:
                                    pass
                            _msg = self.config.get("HANDOFF_START_MESSAGE",
                                                   "Te estamos conectando con un asesor, en breve te atienden.")
                            self.whatsapp_connector.enviar_mensaje(phone_number, _msg)
                            return {"status": "ok"}
                # --- Fin handoff intercept ---

                texto = None
                imagen_path = None

                if mensaje["type"] == "text":
                    texto = mensaje["content"]
                    logger.info(f"Mensaje de texto: {texto[:50]}...")
                elif mensaje["type"] == "voice" and self.transcriptor:
                    audio_path = mensaje["content"]
                    if _pre_transcribed is not None:
                        texto = _pre_transcribed
                    else:
                        logger.info(f"Transcribiendo audio de {phone_number}")
                        texto = self.transcriptor.transcribe_audio(audio_path)
                        logger.info(f"Audio transcrito: {texto[:50]}...")
                    try:
                        os.remove(audio_path)
                        logger.debug(f"Archivo temporal eliminado: {audio_path}")
                    except Exception as e:
                        logger.warning(f"No se pudo eliminar archivo temporal: {e}")
                elif mensaje["type"] == "image":
                    # Manejar mensaje con imagen
                    imagen_path = mensaje["content"]
                    caption = mensaje.get("caption", "")
                    texto = caption if caption else "¿Qué puedes decirme sobre esta imagen?"
                    logger.info(f"Imagen recibida de {phone_number}: {imagen_path}, caption: '{caption}'")
                elif mensaje["type"] == "location":
                    lat = mensaje["latitude"]
                    lon = mensaje["longitude"]
                    name = mensaje.get("name", "")
                    address = mensaje.get("address", "")
                    texto = mensaje["content"]
                    logger.info(f"Ubicación recibida de {phone_number}: lat={lat}, lon={lon}")
                else:
                    logger.debug(f"Tipo de mensaje no soportado: {mensaje['type']}")
                    return {"status": "ok"}
                
                if texto:
                    # Generar respuesta del asistente
                    logger.info(f"Generando respuesta para {phone_number}")
                    respuesta = await self.asistente.generar_respuesta(
                        str(phone_number), texto, imagen_path,
                        session_context={
                            "phone_number": str(phone_number),
                            "whatsapp_connector": self.whatsapp_connector,
                        },
                    )

                    # Enviar respuesta
                    logger.info(f"Enviando respuesta a {phone_number}")
                    await self.whatsapp_connector.procesar_respuesta(phone_number, respuesta, mensaje["type"])
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
                    
                    # Registrar usuario en el tracker
                    try:
                        from behemot_framework.users import get_user_tracker
                        user_tracker = get_user_tracker()
                        
                        # Extraer metadata del usuario Google Chat
                        user_metadata = {
                            "space_name": chat_id,
                            "space_type": None,
                            "user_name": None,
                            "display_name": None,
                            "email": None,
                            "domain": None,
                            "chat_type": "space",
                            "phone_number": None
                        }
                        
                        # Intentar extraer información del usuario y espacio
                        if "message" in update and "sender" in update["message"]:
                            sender = update["message"]["sender"]
                            user_metadata.update({
                                "user_name": sender.get("name"),
                                "display_name": sender.get("displayName"),
                                "email": sender.get("email"),
                                "domain": sender.get("domainId")
                            })
                        
                        if "space" in update:
                            space = update["space"]
                            user_metadata.update({
                                "space_type": space.get("type"),  # ROOM, DM
                                "space_display_name": space.get("displayName")
                            })
                        
                        user_tracker.register_user(str(chat_id), "google_chat", user_metadata)
                        user_tracker.update_last_seen(str(chat_id))
                    except Exception as e:
                        logger.warning(f"Error registrando usuario Google Chat {chat_id}: {e}")
                    
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
        # Evitar múltiples inicializaciones
        if hasattr(self, '_gradio_initialized') and self._gradio_initialized:
            return
            
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
                    time.sleep(3)
                    
                    # Lanzar la interfaz Gradio
                    gradio_connector.launch(port=7860)
                    
                except Exception as e:
                    logger.error(f"Error al lanzar interfaz Gradio: {e}", exc_info=True)
            
            # Lanzar Gradio en un hilo separado para no bloquear FastAPI
            gradio_thread = threading.Thread(target=launch_gradio, daemon=True)
            gradio_thread.start()
            
            # Marcar que Gradio está habilitado y configurado
            self._gradio_enabled = True
            self._gradio_initialized = True
            
            logger.info("✅ Interfaz de prueba local configurada")
            
        except ImportError:
            logger.error("❌ No se pudo importar Gradio. Instala con: pip install gradio")
        except Exception as e:
            logger.error(f"❌ Error al configurar interfaz de prueba local: {e}", exc_info=True)

    def setup_handoff_webhook(self, fastapi_app: FastAPI) -> None:
        """
        Registra el endpoint POST /handoff/webhook que recibe eventos de behemot.net:
        - agent.message   → reenviar al usuario por su canal
        - handoff.assigned → notificar al usuario que el asesor tomó la conversación
        - handoff.closed  → limpiar flag y reanudar el bot
        """
        from behemot_framework.services.handoff_service import (
            verify_signature, get_user_id_by_session, clear_handoff,
        )

        @fastapi_app.post("/handoff/webhook")
        async def handoff_webhook(request: Request):
            body = await request.body()
            logger.info(
                "handoff webhook recv: len=%d content-type=%s body=%r",
                len(body),
                request.headers.get("Content-Type", ""),
                body[:300],
            )
            sig  = request.headers.get("X-Behemot-Signature", "")
            secret = self.config.get("HANDOFF_WEBHOOK_SECRET", "")

            if not verify_signature(body, sig, secret):
                raise HTTPException(status_code=401, detail="Firma inválida")

            try:
                event = json.loads(body)
            except Exception as exc:
                detail = f"Body no es JSON válido (len={len(body)}, err={exc!r})"
                logger.error("handoff webhook json parse error: %s — body=%r", exc, body[:300])
                raise HTTPException(status_code=400, detail=detail)

            event_type = event.get("event")
            session_id = event.get("session_id", "")
            user_id    = get_user_id_by_session(session_id)

            if not user_id:
                logger.warning("handoff webhook: session_id %s no encontrado en Redis", session_id)
                return {"status": "ok"}

            from behemot_framework.services.handoff_service import get_handoff_data
            data    = get_handoff_data(user_id)
            channel = data.get("channel", "") if data else ""

            def _send(text: str):
                if channel == "whatsapp" and self.whatsapp_connector:
                    self.whatsapp_connector.enviar_mensaje(user_id, text)
                elif channel == "telegram" and self.telegram_connector:
                    self.telegram_connector.enviar_mensaje(user_id, text)
                else:
                    logger.warning("handoff webhook: no hay conector para canal '%s'", channel)

            if event_type == "agent.message":
                content    = event.get("content", "")
                msg_type   = event.get("type", "text")
                media_url  = event.get("media_url", "")
                agent_name = event.get("agent_name", "Asesor")
                logger.info("Handoff agent.message type=%s → %s (%s)", msg_type, user_id, channel)
                if msg_type == "audio" and media_url:
                    if channel == "whatsapp" and self.whatsapp_connector:
                        self.whatsapp_connector.enviar_audio_por_url(user_id, media_url)
                    else:
                        _send(content)
                elif msg_type == "image" and media_url:
                    if channel == "whatsapp" and self.whatsapp_connector:
                        self.whatsapp_connector.enviar_imagen_por_url(user_id, media_url, content)
                    else:
                        _send(content or "[imagen]")
                else:
                    _send(content)

            elif event_type == "handoff.assigned":
                agent_name = event.get("agent_name", "un asesor")
                msg = self.config.get(
                    "HANDOFF_ASSIGNED_MESSAGE",
                    f"Ya te atiende {agent_name}.",
                )
                logger.info("Handoff assigned → %s, asesor: %s", user_id, agent_name)
                _send(msg)

            elif event_type == "handoff.closed":
                logger.info("Handoff closed → %s, retomando bot", user_id)
                clear_handoff(user_id)
                msg = self.config.get(
                    "HANDOFF_CLOSED_MESSAGE",
                    "El asesor cerró la conversación. Seguís con el asistente.",
                )
                _send(msg)

            else:
                logger.debug("handoff webhook: evento desconocido '%s'", event_type)

            return {"status": "ok"}

        logger.info("Endpoint /handoff/webhook registrado")

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
        
        # Inicializar user tracker con Redis si está disponible
        try:
            from behemot_framework.users import get_user_tracker
            from behemot_framework.context import redis_client
            from behemot_framework.commandos.admin_commands import get_admin_commands
            
            user_tracker = get_user_tracker(redis_client)
            admin_commands = get_admin_commands(factory)
            logger.info("✅ Sistema de usuarios y comandos admin inicializado")
        except Exception as e:
            logger.warning(f"⚠️ Error inicializando sistema de usuarios: {e}")

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
                auto_rag_enabled = factory.config.get("AUTO_RAG", False)
                print(f"  → Proveedor de embeddings: {rag_provider}")
                print(f"  → Modelo de embeddings: {rag_model}")
                print(f"  → AUTO_RAG: {'✅ Habilitado' if auto_rag_enabled else '❌ Deshabilitado'}")
                logger.info(f"  → Proveedor de embeddings: {rag_provider}")
                logger.info(f"  → Modelo de embeddings: {rag_model}")
                logger.info(f"  → AUTO_RAG: {'Habilitado' if auto_rag_enabled else 'Deshabilitado'}")
                
                if auto_rag_enabled:
                    max_results = factory.config.get("RAG_MAX_RESULTS", 3)
                    threshold = factory.config.get("RAG_SIMILARITY_THRESHOLD", 0.6)
                    print(f"  → Máx. resultados: {max_results}, Umbral: {threshold}")
                    logger.info(f"  → AUTO_RAG configurado: max_results={max_results}, threshold={threshold}")
                
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
                logger.info("🎤 Procesamiento de voz activado (STT: Whisper)")
            if factory.tts_service:
                logger.info("🔊 Síntesis de voz activada (TTS: OpenAI)")
            
            logger.info("=" * 60)
            logger.info("✅ Aplicación iniciada correctamente")
            logger.info("=" * 60)
            
            # Mostrar link de Gradio si está habilitado
            if hasattr(factory, '_gradio_enabled') and factory._gradio_enabled:
                logger.info("")
                logger.info("🌐 Interfaz de prueba local disponible:")
                logger.info("   http://localhost:7860 (o puerto disponible)")
                logger.info("")
            
        # Webhook de retorno desde behemot.net (handoff)
        if self.config.get("HANDOFF_API_KEY"):
            self.setup_handoff_webhook(fastapi_app)

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
        use_tools: Lista de nombres de módulos de herramientas a cargar ("all" para todas).
                   Cada nombre corresponde al archivo en el directorio tools/ sin extensión
                   (ej: use_tools=["propiedades_cercanas"] carga tools/propiedades_cercanas.py),
                   NO al nombre de la función decorada con @tool dentro del archivo.
        config_path: Ruta al archivo de configuración personalizado
        
    Returns:
        FastAPI: Aplicación configurada con los endpoints necesarios
    """
    # Cargar configuración
    config = load_config(config_path)

    # Almacenar la ruta de configuración en la propia configuración para acceso posterior
    config["_config_path"] = config_path

    # Las flags explícitas pasadas a create_behemot_app() tienen prioridad
    # sobre el YAML: si el usuario llama con enable_voice=True/False, ese
    # valor sobrescribe ENABLE_VOICE del config. Esto evita la sorpresa de
    # que la flag de Python sea ignorada por un default heredado.
    config["ENABLE_VOICE"] = bool(enable_voice)

    # Handoff: inicializar si las claves están configuradas
    _hoff_key = config.get("HANDOFF_API_KEY", "")
    _hoff_url = config.get("HANDOFF_WEBHOOK_URL", "")
    if _hoff_key and _hoff_url:
        from behemot_framework.services.handoff_service import init_handoff
        init_handoff(api_key=_hoff_key, webhook_url=_hoff_url)

    # Observabilidad: inicializar Langfuse si las claves están configuradas
    _lf_secret = config.get("LANGFUSE_SECRET_KEY", "")
    _lf_public = config.get("LANGFUSE_PUBLIC_KEY", "")
    if _lf_secret and _lf_public:
        from behemot_framework.services.observability import init_observability
        init_observability(
            secret_key=_lf_secret,
            public_key=_lf_public,
            host=config.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )

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
