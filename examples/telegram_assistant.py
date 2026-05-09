"""
Ejemplo de asistente Behemot conectado a Telegram.

Antes de ejecutar:
  1. Crea el bot con @BotFather y obtén el token.
  2. Configura un dominio público (ngrok, Cloud Run, etc.) — Telegram requiere HTTPS.
  3. Define en .env:
       TELEGRAM_TOKEN=...
       TELEGRAM_WEBHOOK_URL=https://tu-dominio.com/webhook
       TELEGRAM_WEBHOOK_SECRET=<un_string_aleatorio>      # OPCIONAL pero recomendado
       GPT_API_KEY=sk-...
  4. Ejecuta:  python examples/telegram_assistant.py

Seguridad:
  - El framework valida `X-Telegram-Bot-Api-Secret-Token` en cada update.
    Si no defines TELEGRAM_WEBHOOK_SECRET se genera uno efímero (válido para
    una sola réplica). Para deploys en k8s/Cloud Run define el secreto
    explícitamente para que todas las réplicas validen contra el mismo valor.
"""

import logging
import os
import uvicorn

from behemot_framework.factory import create_behemot_app

logging.basicConfig(level=logging.INFO)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config_telegram.yaml")

app = create_behemot_app(
    enable_telegram=True,
    enable_voice=True,         # Transcripción de audios
    config_path=CONFIG_PATH,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
