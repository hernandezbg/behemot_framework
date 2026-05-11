# app/services/transcription_service.py
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


class TranscriptionService:
    """
    Servicio de transcripción basado en Whisper (OpenAI).

    Si no se proporciona `api_key` el servicio queda en modo "deshabilitado":
    el framework arranca sin error y solo se reporta un fallo cuando alguien
    envía un audio real. Esto evita que `enable_voice=True` rompa el deploy
    cuando se usan modelos no-OpenAI (Vertex, Gemini, Anthropic) sin
    GPT_API_KEY configurada.
    """

    def __init__(self, api_key: str = None, language: str = None):
        self.api_key = api_key
        self.language = language
        if api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            logger.warning(
                "TranscriptionService: GPT_API_KEY no configurada — la "
                "transcripción de audio queda DESACTIVADA. Define GPT_API_KEY "
                "o ejecuta con enable_voice=False."
            )

    def transcribe_audio(self, audio_path: str) -> str:
        """
        Transcribe un archivo de audio a texto.
        """
        if self.client is None:
            msg = (
                "Transcripción no disponible: GPT_API_KEY no configurada. "
                "Define la variable de entorno o desactiva enable_voice."
            )
            logger.error(msg)
            return msg
        try:
            with open(audio_path, "rb") as audio_file:
                params = {
                    "model": "whisper-1",
                    "file": audio_file
                }
                if self.language:
                    params["language"] = self.language
                transcript = self.client.audio.transcriptions.create(**params)
            return transcript.text
        except Exception as e:
            logger.error(f"Error en la transcripción: {str(e)}")
            return f"Error en la transcripción del audio: {str(e)}"
