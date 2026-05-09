"""
Ejemplo de asistente Behemot conectado a WhatsApp Business (Meta Cloud API).

Antes de ejecutar:
  1. Crea una app en https://developers.facebook.com/ con producto "WhatsApp".
  2. Obtén Token, Phone Number ID y App Secret.
  3. Configura el webhook apuntando a https://tu-dominio.com/whatsapp-webhook
     con tu WHATSAPP_VERIFY_TOKEN.
  4. Define en .env:
       WHATSAPP_TOKEN=...
       WHATSAPP_PHONE_ID=...
       WHATSAPP_VERIFY_TOKEN=...
       WHATSAPP_APP_SECRET=...                 # ⚠️ obligatorio en producción
       WHATSAPP_WEBHOOK_URL=https://tu-dominio.com/whatsapp-webhook
       GPT_API_KEY=sk-...
  5. Ejecuta:  python examples/whatsapp_assistant.py

Seguridad:
  - El framework valida `X-Hub-Signature-256` (HMAC-SHA256) en cada POST
    contra WHATSAPP_APP_SECRET. Sin esa variable, el webhook acepta cualquier
    POST y un atacante puede forjar mensajes como cualquier número.
"""

import logging
import os
import uvicorn

from behemot_framework.factory import create_behemot_app

logging.basicConfig(level=logging.INFO)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config_whatsapp.yaml")

app = create_behemot_app(
    enable_whatsapp=True,
    enable_voice=True,
    config_path=CONFIG_PATH,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
