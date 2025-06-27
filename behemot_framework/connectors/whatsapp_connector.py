# app/connectors/whatsapp_connector.py
import requests
import os
import re
import tempfile
import logging
import json
import asyncio
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class WhatsAppConnector:
    def __init__(self, token: str, phone_number_id: str):
        """
        Inicializa el conector de WhatsApp Business API.
        
        Args:
            token: Token de acceso de la API de WhatsApp
            phone_number_id: ID del número de teléfono en WhatsApp Business
        """
        self.token = token
        self.phone_number_id = phone_number_id
        self.base_url = f"https://graph.facebook.com/v17.0/{phone_number_id}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        logger.info(f"Conector WhatsApp inicializado para phone_id: {phone_number_id}")

    def extraer_mensaje(self, update: dict) -> tuple:
        """
        Extrae el número de teléfono del remitente y el contenido del mensaje.
        
        Args:
            update: Objeto JSON recibido de la API de WhatsApp
            
        Returns:
            Tupla con (phone_number, mensaje)
        """
        try:
            # Estructura del webhook de WhatsApp
            entry = update.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            
            if "messages" not in value:
                return None, None
                
            message = value["messages"][0]
            
            # Obtener el número de teléfono del remitente
            sender = message.get("from")
            if not sender:
                return None, None
                
            # Determinar tipo de mensaje
            message_type = message.get("type", "unknown")
            
            if message_type == "text":
                # Mensaje de texto
                text_content = message.get("text", {}).get("body", "")
                return sender, {"type": "text", "content": text_content}
                
            elif message_type == "audio":
                # Mensaje de voz
                audio_id = message.get("audio", {}).get("id", "")
                if audio_id:
                    audio_path = self.descargar_archivo_media(audio_id)
                    return sender, {"type": "voice", "content": audio_path}
                    
            # No procesamos otros tipos por ahora
            return sender, None
            
        except Exception as e:
            logger.error(f"Error al extraer mensaje de WhatsApp: {str(e)}")
            return None, None

    def descargar_archivo_media(self, media_id: str) -> Optional[str]:
        """
        Descarga un archivo de medios (audio, imagen, etc.) desde WhatsApp.
        
        Args:
            media_id: ID del archivo multimedia
            
        Returns:
            Ruta local al archivo descargado o None si hay error
        """
        try:
            # 1. Obtener la URL del archivo multimedia
            media_url_endpoint = f"https://graph.facebook.com/v17.0/{media_id}"
            media_response = requests.get(
                media_url_endpoint, 
                headers={"Authorization": f"Bearer {self.token}"}
            )
            
            if not media_response.ok:
                logger.error(f"Error al obtener info de media: {media_response.text}")
                return None
                
            media_info = media_response.json()
            media_url = media_info.get("url")
            
            if not media_url:
                logger.error("URL de medios no encontrada")
                return None
                
            # 2. Descargar el archivo
            download_response = requests.get(
                media_url, 
                headers={"Authorization": f"Bearer {self.token}"},
                stream=True
            )
            
            if not download_response.ok:
                logger.error(f"Error al descargar media: {download_response.text}")
                return None
                
            # 3. Guardar en archivo temporal
            temp_dir = tempfile.gettempdir()
            local_path = os.path.join(temp_dir, f"whatsapp_media_{media_id}.ogg")
            
            with open(local_path, 'wb') as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            logger.info(f"Archivo descargado: {local_path}")
            return local_path
            
        except Exception as e:
            logger.error(f"Error al descargar archivo media: {str(e)}")
            return None

    def enviar_mensaje(self, to: str, texto: str) -> bool:
        """
        Envía un mensaje de texto a un número de WhatsApp.
        
        Args:
            to: Número de teléfono del destinatario
            texto: Contenido del mensaje
            
        Returns:
            True si el envío fue exitoso, False en caso contrario
        """
        if not to or not texto:
            logger.error("No se puede enviar mensaje: falta destinatario o texto")
            return False
        
        # Convertir formato Markdown a formato compatible con WhatsApp
        texto_formateado = format_markdown_for_whatsapp(texto)
        
        endpoint = f"{self.base_url}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "body": texto_formateado
            }
        }
        
        try:
            logger.info(f"Enviando mensaje a {to}")
            logger.debug(f"Payload: {json.dumps(payload)}")
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Mensaje enviado exitosamente a {to}: {response.status_code}")
                logger.debug(f"Respuesta completa: {response.text}")
                return True
            else:
                logger.error(f"Error {response.status_code} al enviar mensaje: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Excepción al enviar mensaje a {to}: {str(e)}", exc_info=True)
            return False
            


    def enviar_accion(self, to: str) -> bool:
        """
        Envía una indicación de que el bot está escribiendo.
        
        Args:
            to: Número de teléfono del destinatario
            
        Returns:
            True si el envío fue exitoso, False en caso contrario
        """
        # WhatsApp no tiene un equivalente directo a sendChatAction de Telegram
        # Por ahora no implementamos nada, pero se mantiene por compatibilidad
        return True
        
    async def procesar_respuesta(self, to: str, respuesta: str) -> None:
        """
        Procesa la respuesta del asistente y maneja casos especiales.
        
        Args:
            to: Número de teléfono del destinatario
            respuesta: Texto de respuesta
        """
        logger.info(f"Procesando respuesta para {to}: {respuesta[:50]}...")
        
        # Si la respuesta contiene un separador especial para múltiples mensajes
        if "\n---SPLIT_MESSAGE---\n" in respuesta:
            mensajes = respuesta.split("\n---SPLIT_MESSAGE---\n")
            logger.info(f"Enviando respuesta dividida en {len(mensajes)} mensajes")
            
            for i, mensaje in enumerate(mensajes):
                if mensaje.strip():
                    logger.info(f"Enviando parte {i+1}/{len(mensajes)}")
                    result = self.enviar_mensaje(to, mensaje.strip())
                    if not result:
                        logger.error(f"Fallo al enviar parte {i+1}/{len(mensajes)}")
                    # Pequeña pausa entre mensajes
                    await asyncio.sleep(1.0)  # Aumentado a 1 segundo para evitar límites de tasa
        else:
            # Respuesta normal
            logger.info("Enviando respuesta única")
            result = self.enviar_mensaje(to, respuesta)
            if not result:
                logger.error("Fallo al enviar respuesta única")
    
    def verificar_token(self, hub_mode: str, hub_verify_token: str, hub_challenge: str, verify_token: str) -> Optional[str]:
        """
        Verifica el token durante la configuración del webhook.
        
        Args:
            hub_mode: Modo de verificación
            hub_verify_token: Token a verificar
            hub_challenge: Challenge a devolver
            verify_token: Token correcto para la verificación
            
        Returns:
            Challenge si la verificación es exitosa, None si falla
        """
        logger.info(f"Verificando token: hub_mode={hub_mode}, token recibido='{hub_verify_token}', token esperado='{verify_token}'")
        
        if hub_mode == "subscribe" and hub_verify_token == verify_token:
            logger.info(f"Verificación de webhook de WhatsApp exitosa")
            return hub_challenge
        
        logger.warning(f"Verificación de webhook de WhatsApp fallida: token recibido='{hub_verify_token}', token esperado='{verify_token}'")
        return None
    


# Añadir al archivo app/connectors/whatsapp_connector.py


def format_markdown_for_whatsapp(text: str) -> str:
    """
    Convierte el formato Markdown a formato compatible con WhatsApp.
    
    Args:
        text: Texto en formato Markdown
        
    Returns:
        Texto formateado para WhatsApp
    """
    if not text:
        return text
        
    # Formateo WhatsApp:
    # Negrita: *texto*
    # Cursiva: _texto_
    # Tachado: ~texto~
    # Monoespaciado: ```texto```
    
    # Paso 1: Guardar bloques de código para procesarlos por separado
    code_blocks = []
    
    def save_code_block(match):
        code_blocks.append(match.group(1))
        return f"CODE_BLOCK_{len(code_blocks) - 1}_PLACEHOLDER"
    
    # Guardar bloques de código de triple backtick
    text = re.sub(r'```(?:\w+)?\n([\s\S]*?)\n```', save_code_block, text)
    
    # Paso 2: Convertir encabezados Markdown a formato WhatsApp
    # No hay equivalente directo para encabezados, así que los convertimos a negrita
    text = re.sub(r'^#\s+(.*?)$', r'*\1*', text, flags=re.MULTILINE)  # h1
    text = re.sub(r'^##\s+(.*?)$', r'*\1*', text, flags=re.MULTILINE)  # h2
    text = re.sub(r'^###\s+(.*?)$', r'*\1*', text, flags=re.MULTILINE)  # h3
    text = re.sub(r'^####\s+(.*?)$', r'*\1*', text, flags=re.MULTILINE)  # h4
    text = re.sub(r'^#####\s+(.*?)$', r'*\1*', text, flags=re.MULTILINE)  # h5
    text = re.sub(r'^######\s+(.*?)$', r'*\1*', text, flags=re.MULTILINE)  # h6
    
    # Paso 3: Convertir listas
    # Mantener las listas como están, pero asegurarse de que cada ítem está en una nueva línea
    text = re.sub(r'^-+\s+(.*?)$', r'• \1', text, flags=re.MULTILINE)  # Lista no ordenada
    text = re.sub(r'^\*\s+(.*?)$', r'• \1', text, flags=re.MULTILINE)  # Lista no ordenada (alt)
    text = re.sub(r'^(\d+)\.\s+(.*?)$', r'\1. \2', text, flags=re.MULTILINE)  # Lista ordenada
    
    # Paso 4: Formateo básico (negrita, cursiva, tachado)
    # WhatsApp ya usa *texto* para negrita y _texto_ para cursiva, que coincide con Markdown
    # Solo necesitamos convertir **texto** (Markdown) a *texto* (WhatsApp)
    
    # Manejar el caso de **texto** (negrita en Markdown)
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    
    # Restaurar bloques de código
    for i, block in enumerate(code_blocks):
        text = text.replace(f"CODE_BLOCK_{i}_PLACEHOLDER", f"```\n{block}\n```")
    
    return text
