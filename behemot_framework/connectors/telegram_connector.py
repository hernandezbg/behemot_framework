# app/connectors/telegram_connector.py (actualizado)
import requests
import os
import tempfile

class TelegramConnector:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.file_url = f"https://api.telegram.org/file/bot{token}"

    def extraer_mensaje(self, update: dict) -> tuple:
        """
        Extrae el chat_id y el contenido del mensaje (texto o audio) de la actualización recibida.
        """
        try:
            chat_id = update["message"]["chat"]["id"]
            
            # Comprobar si es un mensaje de texto
            if "text" in update["message"]:
                return chat_id, {"type": "text", "content": update["message"]["text"]}
            
            # Comprobar si es un mensaje de voz
            elif "voice" in update["message"]:
                file_id = update["message"]["voice"]["file_id"]
                audio_path = self.descargar_archivo(file_id, "voice")
                return chat_id, {"type": "voice", "content": audio_path}
            
            # Comprobar si es un mensaje con foto
            elif "photo" in update["message"]:
                # Telegram envía múltiples tamaños, tomar el más grande (último)
                photo = update["message"]["photo"][-1]
                file_id = photo["file_id"]
                caption = update["message"].get("caption", "")
                image_path = self.descargar_archivo(file_id, "image")
                if image_path:
                    return chat_id, {
                        "type": "image", 
                        "content": image_path,
                        "caption": caption
                    }
            
            # Ningún tipo reconocido
            return chat_id, None
        except KeyError:
            return None, None

    def descargar_archivo(self, file_id: str, file_type: str = "voice") -> str:
        """
        Descarga un archivo de Telegram usando su file_id.
        Retorna la ruta local donde se guardó el archivo.
        
        Args:
            file_id: ID del archivo en Telegram
            file_type: Tipo de archivo ("voice", "image", etc.)
        """
        try:
            # Obtener información del archivo
            get_file_url = f"{self.base_url}/getFile"
            response = requests.get(get_file_url, params={"file_id": file_id})
            file_info = response.json()
            
            if not file_info.get("ok"):
                return None
            
            file_path = file_info["result"]["file_path"]
            download_url = f"{self.file_url}/{file_path}"
            
            # Determinar extensión según el tipo
            if file_type == "voice":
                extension = ".ogg"
            elif file_type == "image":
                # Mantener la extensión original si está disponible
                extension = os.path.splitext(file_path)[1] or ".jpg"
            else:
                extension = ".bin"
            
            # Descargar el archivo
            temp_dir = tempfile.gettempdir()
            local_path = os.path.join(temp_dir, f"telegram_{file_type}_{file_id}{extension}")
            
            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(local_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            return local_path
        except Exception as e:
            print(f"Error descargando archivo de Telegram: {e}")
            return None
    
    def descargar_archivo_voz(self, file_id: str) -> str:
        """
        Método mantenido por compatibilidad. Usa descargar_archivo internamente.
        """
        return self.descargar_archivo(file_id, "voice")

    def enviar_mensaje(self, chat_id: int, texto: str) -> None:
        if chat_id is None or texto is None:
            return
        endpoint = f"{self.base_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": texto}
        try:
            requests.post(endpoint, json=payload)
        except Exception as e:
            print(f"Error al enviar mensaje: {e}")


    def enviar_accion(self, chat_id: int, accion: str = "typing") -> None:
        """
        Envía una indicación de que el bot está realizando una acción.
        Las acciones posibles son: typing, upload_photo, record_video, upload_video,
        record_audio, upload_audio, upload_document, find_location, record_video_note, upload_video_note
        """
        if chat_id is None:
            return
        endpoint = f"{self.base_url}/sendChatAction"
        payload = {"chat_id": chat_id, "action": accion}
        try:
            requests.post(endpoint, json=payload)
        except Exception as e:
            print(f"Error al enviar acción: {e}")

    
    #Método para manejar múltiples mensajes
    async def procesar_respuesta(self, chat_id: int, respuesta: str) -> None:
        """
        Procesa la respuesta del asistente y maneja casos especiales.
        """
        # Si la respuesta contiene un separador especial para múltiples mensajes
        if "\n---SPLIT_MESSAGE---\n" in respuesta:
            mensajes = respuesta.split("\n---SPLIT_MESSAGE---\n")
            for mensaje in mensajes:
                if mensaje.strip():
                    self.enviar_mensaje(chat_id, mensaje.strip())
                    # Pequeña pausa entre mensajes
                    import asyncio
                    await asyncio.sleep(0.5)
        else:
            # Respuesta normal
            self.enviar_mensaje(chat_id, respuesta)
