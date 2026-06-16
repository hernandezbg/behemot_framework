# app/connectors/whatsapp_connector.py
import requests
import os
import re
import tempfile
import logging
import json
import asyncio
import uuid
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
        # TTS: inyectados por factory tras la construcción
        self.tts_service = None
        self.response_mode = "text"  # "text" | "audio" | "both"
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
                    
            elif message_type == "image":
                # Mensaje con imagen
                image_id = message.get("image", {}).get("id", "")
                caption = message.get("image", {}).get("caption", "")
                if image_id:
                    image_path = self.descargar_archivo_media(image_id, "image")
                    if image_path:
                        return sender, {
                            "type": "image",
                            "content": image_path,
                            "caption": caption
                        }

            elif message_type == "location":
                location = message.get("location", {})
                lat = location.get("latitude")
                lon = location.get("longitude")
                if lat is not None and lon is not None:
                    parts = [f"El usuario compartió su ubicación: latitud {lat}, longitud {lon}"]
                    if location.get("name"):
                        parts.append(f"Nombre: {location['name']}")
                    if location.get("address"):
                        parts.append(f"Dirección: {location['address']}")
                    return sender, {
                        "type": "location",
                        "content": ". ".join(parts),
                        "latitude": lat,
                        "longitude": lon,
                        "name": location.get("name", ""),
                        "address": location.get("address", ""),
                    }

            # No procesamos otros tipos por ahora
            return sender, None
            
        except Exception as e:
            logger.error(f"Error al extraer mensaje de WhatsApp: {str(e)}")
            return None, None

    def descargar_archivo_media(self, media_id: str, media_type: str = "audio") -> Optional[str]:
        """
        Descarga un archivo de medios (audio, imagen, etc.) desde WhatsApp.
        
        Args:
            media_id: ID del archivo multimedia
            media_type: Tipo de media ("audio", "image", etc.)
            
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
                
            # 3. Determinar extensión según el tipo de media
            if media_type == "image":
                # WhatsApp típicamente envía imágenes como JPEG
                extension = ".jpg"
            elif media_type == "audio":
                extension = ".ogg"
            else:
                extension = ".bin"
            
            # 4. Guardar en archivo temporal. Nombre generado con uuid4 para
            # neutralizar cualquier intento de path traversal vía media_id si
            # la validación de firma fallara o el atacante controlara el
            # contenido del webhook.
            temp_dir = tempfile.gettempdir()
            safe_ext = extension if extension.startswith(".") and extension.replace(".", "").isalnum() else ".bin"
            local_path = os.path.join(temp_dir, f"whatsapp_media_{uuid.uuid4().hex}{safe_ext}")
            
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
        
    def _subir_media(self, audio_path: str) -> Optional[str]:
        """
        Sube un archivo de audio a la API de WhatsApp y devuelve el media_id.
        """
        try:
            url = f"https://graph.facebook.com/v17.0/{self.phone_number_id}/media"
            headers = {"Authorization": f"Bearer {self.token}"}
            with open(audio_path, "rb") as f:
                files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
                data = {"messaging_product": "whatsapp", "type": "audio"}
                response = requests.post(url, headers=headers, files=files, data=data)
            if response.ok:
                media_id = response.json().get("id")
                logger.info(f"Audio subido a WhatsApp, media_id: {media_id}")
                return media_id
            logger.error(f"Error subiendo audio a WhatsApp: {response.text}")
            return None
        except Exception as e:
            logger.error(f"Excepción al subir audio a WhatsApp: {str(e)}")
            return None

    def obtener_url_media(self, media_id: str) -> Optional[str]:
        """Retorna la URL de descarga autenticada de un media de WhatsApp sin descargarlo."""
        try:
            resp = requests.get(
                f"https://graph.facebook.com/v17.0/{media_id}",
                headers={"Authorization": f"Bearer {self.token}"},
            )
            if resp.ok:
                return resp.json().get("url")
            logger.error("Error obteniendo URL de media %s: %s", media_id, resp.text)
            return None
        except Exception as e:
            logger.error("Excepción obteniendo URL de media: %s", e)
            return None

    def enviar_audio_por_url(self, to: str, media_url: str) -> bool:
        """Envía audio a WhatsApp usando una URL pública directa (ej. GCS)."""
        endpoint = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "audio",
            "audio": {"link": media_url},
        }
        try:
            resp = requests.post(endpoint, headers=self.headers, json=payload)
            if resp.ok:
                logger.info("Audio por URL enviado a %s", to)
                return True
            logger.error("Error enviando audio por URL a %s: %s", to, resp.text)
            return False
        except Exception as e:
            logger.error("Excepción enviando audio por URL a %s: %s", to, e)
            return False

    def enviar_imagen_por_url(self, to: str, media_url: str, caption: str = "") -> bool:
        """Envía una imagen a WhatsApp usando una URL pública (ej. GCS)."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {"link": media_url, "caption": caption},
        }
        try:
            resp = requests.post(f"{self.base_url}/messages", headers=self.headers, json=payload)
            if resp.ok:
                logger.info("Imagen por URL enviada a %s", to)
                return True
            logger.error("Error enviando imagen por URL a %s: %s", to, resp.text)
            return False
        except Exception as e:
            logger.error("Excepción enviando imagen por URL a %s: %s", to, e)
            return False

    def enviar_carrusel_template(
        self,
        to: str,
        template_name: str,
        cards: list,
        language: str = "es",
    ) -> bool:
        """
        Envía un carrusel horizontal de productos vía template aprobado en Meta Business Manager.

        Cada dict en `cards` debe tener:
          - imagen_url  (str)        : URL pública de la imagen del header
          - variables   (list[str])  : variables del body en el mismo orden que el template
          - botones     (list[dict]) : hasta 2 botones, cada uno con:
              {"tipo": "quick_reply", "payload": "PAYLOAD_VALUE"}
              {"tipo": "url",         "url":     "https://..."}

        Requiere un template de tipo 'carousel' aprobado en Meta Business Manager.
        Máximo 10 cards por mensaje (límite de WhatsApp).
        """
        if not cards:
            logger.warning("enviar_carrusel_template: se llamó sin cards, noop")
            return False

        api_cards = []
        for idx, card in enumerate(cards[:10]):
            components = []

            imagen_url = card.get("imagen_url", "")
            if imagen_url:
                components.append({
                    "type": "header",
                    "parameters": [{"type": "image", "image": {"link": imagen_url}}],
                })

            variables = card.get("variables", [])
            if variables:
                components.append({
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(v)} for v in variables],
                })

            for btn_idx, btn in enumerate(card.get("botones", [])[:2]):
                tipo = btn.get("tipo", "quick_reply")
                btn_component: Dict[str, Any] = {
                    "type": "button",
                    "index": btn_idx,
                }
                if tipo == "url":
                    btn_component["sub_type"] = "url"
                    btn_component["parameters"] = [{"type": "text", "text": btn.get("url", "")}]
                else:
                    btn_component["sub_type"] = "quick_reply"
                    btn_component["parameters"] = [
                        {"type": "payload", "payload": btn.get("payload", f"CARD_{idx}_BTN_{btn_idx}")}
                    ]
                components.append(btn_component)

            api_cards.append({"card_index": idx, "components": components})

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": [{"type": "carousel", "cards": api_cards}],
            },
        }
        try:
            resp = requests.post(f"{self.base_url}/messages", headers=self.headers, json=payload)
            if resp.ok:
                logger.info("Carrusel enviado a %s (template=%s, cards=%d)", to, template_name, len(api_cards))
                return True
            logger.error("Error enviando carrusel a %s: %s %s", to, resp.status_code, resp.text)
            return False
        except Exception as e:
            logger.error("Excepción enviando carrusel a %s: %s", to, e)
            return False

    def _enviar_audio(self, to: str, media_id: str) -> bool:
        """
        Envía un mensaje de audio usando un media_id previamente subido.
        """
        endpoint = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "audio",
            "audio": {"id": media_id},
        }
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload)
            if response.ok:
                logger.info(f"Mensaje de audio enviado a {to}")
                return True
            logger.error(f"Error enviando audio a {to}: {response.text}")
            return False
        except Exception as e:
            logger.error(f"Excepción al enviar audio a {to}: {str(e)}")
            return False

    async def _enviar_respuesta_audio(self, to: str, texto: str) -> None:
        """
        Genera audio TTS, lo sube a WhatsApp y lo envía. Libera el temporal al terminar.
        Las llamadas a OpenAI y a la API de Meta son síncronas y se ejecutan en un
        thread separado para no bloquear el event loop de FastAPI.
        """
        if self.tts_service is None:
            logger.warning("TTS no configurado; enviando texto como fallback.")
            self.enviar_mensaje(to, texto)
            return

        audio_path = await asyncio.to_thread(self.tts_service.synthesize, texto)
        if not audio_path:
            logger.warning("TTS falló; enviando texto como fallback.")
            self.enviar_mensaje(to, texto)
            return

        try:
            media_id = await asyncio.to_thread(self._subir_media, audio_path)
            if media_id:
                await asyncio.to_thread(self._enviar_audio, to, media_id)
            else:
                logger.warning("No se obtuvo media_id; enviando texto como fallback.")
                self.enviar_mensaje(to, texto)
        finally:
            try:
                os.remove(audio_path)
            except OSError:
                pass

    async def procesar_respuesta(self, to: str, respuesta: str, input_type: str = "text") -> None:
        """
        Procesa la respuesta del asistente.

        El comportamiento depende de self.response_mode:
          - "text"     → solo mensaje de texto (comportamiento original)
          - "audio"    → solo mensaje de audio (TTS)
          - "both"     → primero texto, luego audio
          - "adaptive" → audio si el usuario envió audio, texto en cualquier otro caso
        """
        logger.info(f"Procesando respuesta para {to}: {respuesta[:50]}...")

        if self.response_mode == "adaptive":
            use_text  = input_type != "voice"
            use_audio = input_type == "voice"
        else:
            use_text  = self.response_mode in ("text", "both")
            use_audio = self.response_mode in ("audio", "both")

        # Soporte para respuestas multi-parte
        partes = (
            [m.strip() for m in respuesta.split("\n---SPLIT_MESSAGE---\n") if m.strip()]
            if "\n---SPLIT_MESSAGE---\n" in respuesta
            else [respuesta]
        )

        for i, parte in enumerate(partes):
            if use_text:
                result = self.enviar_mensaje(to, parte)
                if not result:
                    logger.error(f"Fallo al enviar texto parte {i+1}/{len(partes)}")
            if use_audio:
                await self._enviar_respuesta_audio(to, parte)
            if len(partes) > 1:
                await asyncio.sleep(1.0)
    
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
        # Nunca loguear los tokens en claro — solo el modo y resultado de la verificación
        logger.info(f"Verificando token de webhook WhatsApp (mode={hub_mode})")

        if hub_mode == "subscribe" and hub_verify_token == verify_token:
            logger.info("Verificación de webhook de WhatsApp exitosa")
            return hub_challenge

        logger.warning("Verificación de webhook de WhatsApp fallida")
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
