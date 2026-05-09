"""
Ejemplo de asistente Behemot conectado a Google Chat.

Antes de ejecutar:
  1. En Google Cloud Console, crea una cuenta de servicio y descarga la clave JSON.
  2. Habilita la API de Google Chat para el proyecto.
  3. Crea un Chat App apuntando al endpoint del bot (HTTP).
  4. Define en .env los valores extraídos del JSON:
       GC_PROJECT_ID=...
       GC_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
       GC_CLIENT_EMAIL=mi-bot@mi-proyecto.iam.gserviceaccount.com
       GPT_API_KEY=sk-...
  5. Ejecuta:  python examples/google_chat_assistant.py
"""

import logging
import os
import uvicorn

from behemot_framework.factory import create_behemot_app

logging.basicConfig(level=logging.INFO)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config_google_chat.yaml")

app = create_behemot_app(
    enable_google_chat=True,
    config_path=CONFIG_PATH,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
