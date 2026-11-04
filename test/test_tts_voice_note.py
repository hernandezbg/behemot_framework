"""Verifica que las respuestas TTS salgan como nota de voz (OGG/Opus)."""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from behemot_framework.connectors.telegram_connector import TelegramConnector
from behemot_framework.connectors.whatsapp_connector import WhatsAppConnector
from behemot_framework.services.tts_service import TTS_AUDIO_MIMETYPE, TTSService

OPUS_MIMETYPE = "audio/ogg; codecs=opus"


class SynthesizeTest(unittest.TestCase):
    def _cleanup(self, path):
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

    def test_openai_pide_opus_y_devuelve_ogg(self):
        service = TTSService(provider="openai")
        service._client = MagicMock()

        path = service.synthesize("hola")

        self.assertTrue(path.endswith(".ogg"))
        kwargs = service._client.audio.speech.create.call_args.kwargs
        self.assertEqual(kwargs["response_format"], "opus")

    def test_elevenlabs_pide_opus_y_devuelve_ogg(self):
        fake_module = MagicMock()
        fake_module.ElevenLabs.return_value.text_to_speech.convert.return_value = [b"OggS"]
        with patch.dict(sys.modules, {"elevenlabs": MagicMock(), "elevenlabs.client": fake_module}):
            service = TTSService(provider="elevenlabs", elevenlabs_api_key="k")

        path = service.synthesize("hola")
        self._cleanup(path)

        self.assertTrue(path.endswith(".ogg"))
        kwargs = service._client.text_to_speech.convert.call_args.kwargs
        self.assertTrue(kwargs["output_format"].startswith("opus_"))


class ConnectorsTest(unittest.TestCase):
    def setUp(self):
        handle, self.audio_path = tempfile.mkstemp(suffix=".ogg")
        os.close(handle)
        self.addCleanup(os.remove, self.audio_path)

    def test_whatsapp_sube_con_mimetype_opus(self):
        connector = WhatsAppConnector("token", "123")
        with patch("behemot_framework.connectors.whatsapp_connector.requests.post") as post:
            connector._subir_media(self.audio_path)
        self.assertEqual(post.call_args.kwargs["files"]["file"][2], OPUS_MIMETYPE)

    def test_whatsapp_envia_con_flag_voice(self):
        connector = WhatsAppConnector("token", "123")
        with patch("behemot_framework.connectors.whatsapp_connector.requests.post") as post:
            connector._enviar_audio("549", "media-id")
        self.assertEqual(post.call_args.kwargs["json"]["audio"], {"id": "media-id", "voice": True})

    def test_telegram_declara_mimetype_opus(self):
        connector = TelegramConnector("token")
        with patch("behemot_framework.connectors.telegram_connector.requests.post") as post:
            connector.enviar_voz(1, self.audio_path)
        self.assertEqual(post.call_args.kwargs["files"]["voice"][2], TTS_AUDIO_MIMETYPE)


if __name__ == "__main__":
    unittest.main()
