# app/connectors/google_chat_connector.py
import logging
import os
from typing import Optional, Dict, Any, Tuple
from behemot_framework.utils.markdown_converter import markdown_to_google_chat

logger = logging.getLogger(__name__)

class GoogleChatConnector:
    def __init__(self):
        """
        Inicializa el conector de Google Chat usando variables GC_*
        """
        # Verificar que tenemos las variables mínimas necesarias
        required_vars = ["GC_PROJECT_ID", "GC_PRIVATE_KEY", "GC_CLIENT_EMAIL"]
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        
        if missing_vars:
            error_msg = f"Faltan variables de entorno para Google Chat: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Capturar las variables de entorno
        self.project_id = os.environ.get("GC_PROJECT_ID")
        self.client_email = os.environ.get("GC_CLIENT_EMAIL")
        
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            # Construir diccionario de credenciales usando solo variables GC_*
            credentials_dict = {
                "type": "service_account",
                "project_id": self.project_id,
                "private_key_id": os.environ.get("GC_PRIVATE_KEY_ID", ""),
                "private_key": os.environ.get("GC_PRIVATE_KEY", "").replace("\\n", "\n"),
                "client_email": self.client_email,
                "client_id": os.environ.get("GC_CLIENT_ID", ""),
                "auth_uri": os.environ.get("GC_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
                "token_uri": os.environ.get("GC_TOKEN_URI", "https://oauth2.googleapis.com/token"),
                "auth_provider_x509_cert_url": os.environ.get("GC_AUTH_PROVIDER_CERT_URL", 
                                              "https://www.googleapis.com/oauth2/v1/certs"),
                "client_x509_cert_url": os.environ.get("GC_CLIENT_CERT_URL", "")
            }
            
            # Crear credenciales desde el diccionario
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=['https://www.googleapis.com/auth/chat.bot']
            )
            
            # Construir el servicio de Chat
            self.service = build('chat', 'v1', credentials=credentials)
            logger.info(f"Conector de Google Chat inicializado para proyecto: {self.project_id}")
            
        except Exception as e:
            logger.error(f"Error al inicializar conector de Google Chat: {str(e)}")
            raise
    
    def extraer_mensaje(self, update: dict) -> tuple:
        """
        Extrae el espacio de chat y el contenido del mensaje.
        
        Args:
            update: Objeto JSON recibido de la API de Google Chat
            
        Returns:
            Tupla con (chat_id, mensaje)
        """
        try:
            # Estructura del mensaje de Google Chat
            space_name = update.get("space", {}).get("name")
            message = update.get("message", {})
            
            if not space_name or not message:
                return None, None
            
            # Para Google Chat, usar solo space_name para mantener contexto consistente
            # Los threads individuales causan pérdida de contexto entre mensajes
            thread_name = message.get("thread", {}).get("name", "")
            chat_id = space_name  # Usar solo space para mantener contexto entre mensajes
            
            # Primero verificar si hay texto
            if message.get("text"):
                return chat_id, {"type": "text", "content": message.get("text")}
            
            # Si no hay texto, verificar si hay adjuntos (audio)
            attachments = message.get("attachment", [])
            if attachments:
                for attachment in attachments:
                    # Verificar si es un archivo de audio
                    content_type = attachment.get("contentType", "")
                    if content_type.startswith("audio/"):
                        # Obtenemos la URL de descarga directa
                        download_uri = attachment.get("downloadUri")
                        if download_uri:
                            # Si tenemos el servicio de transcripción activado
                            if hasattr(self, 'transcriptor') and self.transcriptor:
                                # Aquí podrías descargar y transcribir el audio
                                # Pero para empezar, solo indicamos que es un audio y pasamos la URL
                                return chat_id, {
                                    "type": "audio_url", 
                                    "content": download_uri,
                                    "content_name": attachment.get("contentName", "audio.m4a")
                                }
                            else:
                                # Si no tenemos transcripción, al menos informamos que es un audio
                                return chat_id, {
                                    "type": "unsupported_audio",
                                    "content": "Mensaje de audio no soportado"
                                }
            
            # Si llegamos aquí, no pudimos manejar el mensaje
            logger.warning(f"Tipo de mensaje no soportado: {message}")
            return chat_id, None
                
        except Exception as e:
            logger.error(f"Error al extraer mensaje de Google Chat: {str(e)}")
            return None, None
    
    def enviar_mensaje(self, space_name: str, texto: str, thread_name: str = None) -> bool:
        """
        Envía un mensaje a un espacio de Google Chat.
        
        Args:
            space_name: Nombre del espacio de chat
            texto: Contenido del mensaje
            thread_name: Nombre del hilo (opcional)
            
        Returns:
            True si el envío fue exitoso, False en caso contrario
        """
        if not space_name or not texto:
            logger.error("No se puede enviar mensaje: falta espacio o texto")
            return False
        
        try:
            # Log del texto original
            logger.info(f"📝 Texto original (primeros 100 chars): {texto[:100]}...")
            
            # Convertir Markdown a formato Google Chat
            texto_formateado = markdown_to_google_chat(texto)
            
            # Log del texto convertido
            logger.info(f"✨ Texto formateado (primeros 100 chars): {texto_formateado[:100]}...")
            
            # Crear el cuerpo del mensaje
            body = {
                "text": texto_formateado
            }
            
            # Si hay un hilo específico, añadirlo al cuerpo
            if thread_name:
                body["thread"] = {"name": thread_name}
            
            # Enviar el mensaje
            response = self.service.spaces().messages().create(
                parent=space_name,
                body=body
            ).execute()
            
            logger.info(f"Mensaje enviado a {space_name}")
            return True
        except Exception as e:
            logger.error(f"Error al enviar mensaje a Google Chat: {str(e)}")
            return False
    
    async def procesar_respuesta(self, chat_id: str, respuesta: str) -> None:
        """
        Procesa la respuesta del asistente para Google Chat.
        
        Args:
            chat_id: ID del chat (ahora solo space_name para mantener contexto)
            respuesta: Texto de respuesta
        """
        # chat_id ahora es solo space_name
        space_name = chat_id
        thread_name = None  # No usar thread específico para mantener contexto
        
        # Si la respuesta contiene un separador especial para múltiples mensajes
        if "\n---SPLIT_MESSAGE---\n" in respuesta:
            mensajes = respuesta.split("\n---SPLIT_MESSAGE---\n")
            for mensaje in mensajes:
                if mensaje.strip():
                    self.enviar_mensaje(space_name, mensaje.strip(), thread_name)
                    # Pequeña pausa entre mensajes
                    import asyncio
                    await asyncio.sleep(1.0)
        else:
            # Respuesta normal
            self.enviar_mensaje(space_name, respuesta, thread_name)
