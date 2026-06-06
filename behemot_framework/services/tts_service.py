# app/services/tts_service.py
import os
import logging
import tempfile
import uuid

logger = logging.getLogger(__name__)


class TTSService:
    """
    Servicio de síntesis de voz (TTS) basado en OpenAI.

    Si no se proporciona `api_key` el servicio queda en modo "deshabilitado":
    el framework arranca sin error y solo reporta fallo si se intenta
    sintetizar texto real.
    """

    def __init__(self, api_key: str = None, model: str = "tts-1", voice: str = "alloy"):
        self.model = model
        self.voice = voice
        if api_key:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None
            logger.warning(
                "TTSService: GPT_API_KEY no configurada — la síntesis de voz "
                "queda DESACTIVADA. Define GPT_API_KEY para habilitar respuestas en audio."
            )

    def synthesize(self, text: str) -> str | None:
        """
        Sintetiza texto a audio MP3 y devuelve la ruta del archivo temporal.
        Devuelve None si ocurre cualquier error.
        """
        if self.client is None:
            logger.error("TTS no disponible: GPT_API_KEY no configurada.")
            return None
        try:
            temp_path = os.path.join(tempfile.gettempdir(), f"tts_{uuid.uuid4().hex}.mp3")
            response = self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
            )
            response.stream_to_file(temp_path)
            logger.info(f"Audio TTS generado: {temp_path}")
            return temp_path
        except Exception as e:
            logger.error(f"Error en síntesis TTS: {str(e)}")
            return None
