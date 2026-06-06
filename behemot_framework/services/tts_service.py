# app/services/tts_service.py
import os
import logging
import tempfile
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


class TTSService:
    """
    Servicio de síntesis de voz (TTS) con soporte para múltiples providers.

    Providers soportados:
      - "openai"      → openai.audio.speech.create (tts-1, tts-1-hd)
      - "elevenlabs"  → ElevenLabs API (requiere pip install elevenlabs)

    Si las credenciales no están configuradas el servicio queda deshabilitado:
    arranca sin error y solo reporta fallo cuando se intenta sintetizar.
    """

    def __init__(
        self,
        provider: str = "openai",
        # OpenAI
        api_key: Optional[str] = None,
        model: str = "tts-1",
        voice: str = "alloy",
        # ElevenLabs
        elevenlabs_api_key: Optional[str] = None,
        elevenlabs_voice_id: str = "Rachel",
        elevenlabs_model: str = "eleven_multilingual_v2",
    ):
        self.provider = provider.lower()
        self._client = None

        if self.provider == "elevenlabs":
            if elevenlabs_api_key:
                try:
                    from elevenlabs.client import ElevenLabs
                    self._client = ElevenLabs(api_key=elevenlabs_api_key)
                    self._el_voice_id = elevenlabs_voice_id
                    self._el_model = elevenlabs_model
                    logger.info("TTSService: provider ElevenLabs inicializado.")
                except ImportError:
                    logger.error(
                        "TTSService: 'elevenlabs' no está instalado. "
                        "Ejecutá: pip install behemot-framework[voice-elevenlabs]"
                    )
            else:
                logger.warning(
                    "TTSService: ELEVENLABS_API_KEY no configurada — TTS desactivado."
                )

        else:  # openai (default)
            self.model = model
            self.voice = voice
            if api_key:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key)
                logger.info("TTSService: provider OpenAI inicializado.")
            else:
                logger.warning(
                    "TTSService: GPT_API_KEY no configurada — TTS desactivado."
                )

    def synthesize(self, text: str) -> Optional[str]:
        """
        Sintetiza texto a audio MP3 y devuelve la ruta del archivo temporal.
        Devuelve None si ocurre cualquier error.
        """
        if self._client is None:
            logger.error(f"TTS no disponible: provider '{self.provider}' sin credenciales.")
            return None

        temp_path = os.path.join(tempfile.gettempdir(), f"tts_{uuid.uuid4().hex}.mp3")

        try:
            if self.provider == "elevenlabs":
                audio_iter = self._client.text_to_speech.convert(
                    voice_id=self._el_voice_id,
                    text=text,
                    model_id=self._el_model,
                    output_format="mp3_44100_128",
                )
                with open(temp_path, "wb") as f:
                    for chunk in audio_iter:
                        f.write(chunk)

            else:  # openai
                response = self._client.audio.speech.create(
                    model=self.model,
                    voice=self.voice,
                    input=text,
                )
                response.stream_to_file(temp_path)

            logger.info(f"Audio TTS generado ({self.provider}): {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"Error en síntesis TTS ({self.provider}): {str(e)}")
            return None
