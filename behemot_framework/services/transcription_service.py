# app/services/transcription_service.py
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key)
    
    def transcribe_audio(self, audio_path: str) -> str:
        """
        Transcribe un archivo de audio a texto.
        """
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
            return transcript.text
        except Exception as e:
            logger.error(f"Error en la transcripción: {str(e)}")
            return f"Error en la transcripción del audio: {str(e)}"
