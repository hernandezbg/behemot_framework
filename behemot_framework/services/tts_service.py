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
        # ElevenLabs voice_settings (None = usar defaults de la API)
        elevenlabs_stability: Optional[float] = None,
        elevenlabs_similarity_boost: Optional[float] = None,
        elevenlabs_style: Optional[float] = None,
        elevenlabs_speaker_boost: Optional[bool] = None,
        elevenlabs_language_code: Optional[str] = None,
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
                    self._el_stability = elevenlabs_stability
                    self._el_similarity_boost = elevenlabs_similarity_boost
                    self._el_style = elevenlabs_style
                    self._el_speaker_boost = elevenlabs_speaker_boost
                    self._el_language_code = elevenlabs_language_code
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
                el_kwargs = {
                    "voice_id": self._el_voice_id,
                    "text": text,
                    "model_id": self._el_model,
                    "output_format": "mp3_44100_128",
                }
                voice_settings = {}
                if self._el_stability is not None:
                    voice_settings["stability"] = self._el_stability
                if self._el_similarity_boost is not None:
                    voice_settings["similarity_boost"] = self._el_similarity_boost
                if self._el_style is not None:
                    voice_settings["style"] = self._el_style
                if self._el_speaker_boost is not None:
                    voice_settings["use_speaker_boost"] = self._el_speaker_boost
                if voice_settings:
                    el_kwargs["voice_settings"] = voice_settings
                if self._el_language_code:
                    el_kwargs["language_code"] = self._el_language_code
                audio_iter = self._client.text_to_speech.convert(**el_kwargs)
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
