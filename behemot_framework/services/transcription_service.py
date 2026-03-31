# app/services/transcription_service.py
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(self, api_key: str, language: str = None):
        self.api_key = api_key
        self.language = language
        self.client = OpenAI(api_key=self.api_key)

    def transcribe_audio(self, audio_path: str) -> str:
        """
        Transcribe un archivo de audio a texto.
        """
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
