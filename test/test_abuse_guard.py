"""Verifica el control de abuso: reglas, webhooks y corte del filtro de seguridad."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from behemot_framework.security.abuse_guard import DEFAULT_BLOCK_MESSAGE, AbuseGuard

try:
    import fakeredis
except ImportError:
    fakeredis = None


class GuardRulesMixin:
    """Mismas reglas sobre cualquier almacenamiento."""

    def make_guard(self, **kwargs):
        raise NotImplementedError

    def send(self, guard, times, text=None, user="549"):
        return [guard.check("whatsapp", user, text) for _ in range(times)]

    def test_uso_normal_no_se_bloquea(self):
        guard = self.make_guard()
        results = [guard.check("whatsapp", "549", f"mensaje {i}") for i in range(30)]
        self.assertTrue(all(r.allowed for r in results))

    def test_limite_por_minuto_con_un_solo_aviso(self):
        guard = self.make_guard(rate_limit_per_minute=5, repeat_max=0)
        results = [guard.check("whatsapp", "549", f"m{i}") for i in range(9)]
        self.assertEqual([r.allowed for r in results], [True] * 5 + [False] * 4)
        notices = [r.notice for r in results if r.notice]
        self.assertEqual(notices, [DEFAULT_BLOCK_MESSAGE])

    def test_repeticiones_consecutivas(self):
        guard = self.make_guard()
        results = self.send(guard, 5, "hola")
        self.assertEqual([r.allowed for r in results], [True, True, True, False, False])
        self.assertEqual(results[3].reason, "mensaje repetido")

    def test_repeticion_ignora_mayusculas_y_espacios(self):
        guard = self.make_guard(repeat_max=1)
        self.assertTrue(guard.check("whatsapp", "549", "Hola  Mundo").allowed)
        self.assertFalse(guard.check("whatsapp", "549", " hola mundo ").allowed)

    def test_texto_distinto_reinicia_repeticiones(self):
        guard = self.make_guard()
        for text in ["si", "si", "si", "otra cosa", "si", "si", "si"]:
            self.assertTrue(guard.check("whatsapp", "549", text).allowed, text)

    def test_audio_sin_texto_no_cuenta_como_repeticion(self):
        guard = self.make_guard()
        self.assertTrue(all(r.allowed for r in self.send(guard, 10, None)))

    def test_rafaga_cuenta_una_sola_infraccion(self):
        guard = self.make_guard(rate_limit_per_minute=1, repeat_max=0, max_strikes=2)
        results = [guard.check("whatsapp", "549", f"m{i}") for i in range(20)]
        self.assertTrue(all(r.reason == "límite de mensajes" for r in results[1:]))

    def test_infracciones_activan_bloqueo_temporal(self):
        guard = self.make_guard(insult_words=["boludo"], max_strikes=2)
        guard.check("whatsapp", "549", "sos un boludo")
        guard.check("whatsapp", "549", "boludo")
        decision = guard.check("whatsapp", "549", "mensaje normal")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "bloqueo temporal")
        self.assertIsNone(decision.notice)

    def test_un_usuario_no_afecta_a_otro(self):
        guard = self.make_guard(rate_limit_per_minute=1, repeat_max=0)
        guard.check("whatsapp", "1", "a")
        self.assertFalse(guard.check("whatsapp", "1", "b").allowed)
        self.assertTrue(guard.check("whatsapp", "2", "c").allowed)

    def test_handoff_exento_salvo_lista_negra(self):
        guard = self.make_guard(rate_limit_per_minute=1, blacklist=["999"])
        for i in range(5):
            self.assertTrue(guard.check("whatsapp", "549", f"m{i}", exempt=True).allowed)
        self.assertFalse(guard.check("whatsapp", "999", "hola", exempt=True).allowed)


class MemoryGuardTest(GuardRulesMixin, unittest.TestCase):
    def make_guard(self, **kwargs):
        return AbuseGuard(**kwargs)

    def test_lista_negra_sin_aviso_y_acepta_prefijo_mas(self):
        guard = AbuseGuard.from_config({"ABUSE_BLACKLIST": "+549, 111"})
        decision = guard.check("whatsapp", "549", "hola")
        self.assertFalse(decision.allowed)
        self.assertIsNone(decision.notice)

    def test_insultos_desactivados_por_defecto(self):
        guard = AbuseGuard.from_config({})
        self.assertTrue(guard.check("whatsapp", "549", "sos un boludo").allowed)

    def test_insultos_ignoran_acentos_y_no_cortan_palabras(self):
        guard = AbuseGuard(insult_words=["inútil", "ano"])
        self.assertFalse(guard.check("whatsapp", "1", "sos un INUTIL").allowed)
        self.assertTrue(guard.check("whatsapp", "2", "cuánto sale por año, hermano").allowed)

    def test_config_desde_entorno_o_yaml(self):
        guard = AbuseGuard.from_config({"ABUSE_RATE_LIMIT_PER_MINUTE": "7", "ABUSE_INSULT_WORDS": ["a"]})
        self.assertEqual(guard.rate_limit_per_minute, 7)
        self.assertFalse(AbuseGuard.from_config({"ABUSE_GUARD_ENABLED": "false"}).enabled)
        self.assertFalse(AbuseGuard.from_config({"ABUSE_GUARD_ENABLED": False}).enabled)

    def test_desactivado_permite_todo(self):
        guard = AbuseGuard(enabled=False, blacklist=["549"])
        self.assertTrue(guard.check("whatsapp", "549", "hola").allowed)

    def test_comandos_exentos(self):
        guard = AbuseGuard()
        self.assertTrue(all(r.allowed for r in self.send(guard, 10, "&status")))

    def test_error_de_almacenamiento_permite_el_mensaje(self):
        client = MagicMock()
        client.get.side_effect = ConnectionError("redis caído")
        self.assertTrue(AbuseGuard(redis_client=client).check("whatsapp", "549", "hola").allowed)

    def test_el_bloqueo_vence(self):
        guard = AbuseGuard(insult_words=["x"], max_strikes=1, block_seconds=100)
        guard.check("whatsapp", "549", "x")
        self.assertFalse(guard.check("whatsapp", "549", "hola").allowed)
        with patch("behemot_framework.security.abuse_guard.time.monotonic", return_value=1e12):
            self.assertTrue(guard.check("whatsapp", "549", "hola").allowed)


@unittest.skipIf(fakeredis is None, "fakeredis no instalado")
class RedisGuardTest(GuardRulesMixin, unittest.TestCase):
    def make_guard(self, **kwargs):
        client = fakeredis.FakeStrictRedis(decode_responses=True)
        client.flushall()
        return AbuseGuard(redis_client=client, **kwargs)

    def test_todas_las_claves_vencen(self):
        client = fakeredis.FakeStrictRedis(decode_responses=True)
        client.flushall()
        guard = AbuseGuard(redis_client=client, insult_words=["x"], max_strikes=1)
        guard.check("whatsapp", "549", "x")
        keys = client.keys("abuse:*")
        self.assertTrue(keys)
        self.assertTrue(all(client.ttl(key) > 0 for key in keys), keys)


class SafetyFilterTest(unittest.TestCase):
    def test_mensaje_inseguro_no_llega_al_modelo(self):
        from behemot_framework.assistants.assistant import Assistant

        assistant = Assistant.__new__(Assistant)
        assistant.modelo = MagicMock()
        assistant.safety_filter = MagicMock()
        assistant.safety_filter.filter_content = AsyncMock(return_value={
            "is_safe": False, "filtered_content": "Lo siento", "reason": "test",
        })

        with patch("behemot_framework.assistants.assistant.get_conversation") as get_conversation:
            result = asyncio.run(assistant._run_turn("549", "algo inseguro"))

        self.assertEqual(result, "Lo siento")
        get_conversation.assert_not_called()
        self.assertEqual(assistant.modelo.mock_calls, [])


class WebhookTest(unittest.TestCase):
    """Conecta el control a los webhooks reales, con el modelo y Meta simulados."""

    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from behemot_framework.factory import BehemotFactory

        factory = BehemotFactory.__new__(BehemotFactory)
        factory.config = {"WHATSAPP_TOKEN": "t", "WHATSAPP_PHONE_ID": "1", "API_AUTH_MODE": "none"}
        factory.abuse_guard = AbuseGuard(rate_limit_per_minute=2, repeat_max=0)
        factory.tts_service = None
        factory.transcriptor = MagicMock()
        factory.transcriptor.transcribe_audio.return_value = "audio"
        factory.asistente = MagicMock()
        factory.asistente.generar_respuesta = AsyncMock(return_value="respuesta")
        self.factory = factory

        tracker = patch("behemot_framework.users.get_user_tracker")
        tracker.start()
        self.addCleanup(tracker.stop)

        app = FastAPI()
        factory.setup_whatsapp_connector(app)
        factory.setup_api_connector(app)
        self.client = TestClient(app)
        factory.whatsapp_connector.enviar_mensaje = MagicMock(return_value=True)

    def post_whatsapp(self, message):
        body = {"entry": [{"changes": [{"value": {"messages": [message]}}]}]}
        return self.client.post("/whatsapp-webhook", content=json.dumps(body))

    def test_whatsapp_corta_antes_del_modelo_y_avisa_una_vez(self):
        for i in range(6):
            response = self.post_whatsapp({"from": "549", "type": "text", "text": {"body": f"m{i}"}})
            self.assertEqual(response.status_code, 200)

        self.assertEqual(self.factory.asistente.generar_respuesta.await_count, 2)
        sent = [c.args[1] for c in self.factory.whatsapp_connector.enviar_mensaje.call_args_list]
        self.assertEqual(sent.count(DEFAULT_BLOCK_MESSAGE), 1)

    def test_whatsapp_audio_bloqueado_no_se_transcribe_y_borra_el_temporal(self):
        handle, path = tempfile.mkstemp(suffix=".ogg")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        self.factory.whatsapp_connector.descargar_archivo_media = MagicMock(return_value=path)
        self.factory.abuse_guard = AbuseGuard(blacklist=["549"])

        self.post_whatsapp({"from": "549", "type": "audio", "audio": {"id": "a"}})

        self.factory.transcriptor.transcribe_audio.assert_not_called()
        self.assertFalse(os.path.exists(path))
        self.factory.whatsapp_connector.enviar_mensaje.assert_not_called()

    def test_api_responde_429(self):
        statuses = [
            self.client.post("/api/chat", json={"session_id": "s", "message": f"m{i}"}).status_code
            for i in range(3)
        ]
        self.assertEqual(statuses, [200, 200, 429])
        self.assertEqual(self.factory.asistente.generar_respuesta.await_count, 2)


if __name__ == "__main__":
    unittest.main()
