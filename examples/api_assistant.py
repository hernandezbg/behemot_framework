"""
Ejemplo de asistente Behemot expuesto sólo como API REST.

Antes de ejecutar:
  1. Define en .env:
       GPT_API_KEY=sk-...
       API_KEYS=clave-cliente-1,clave-cliente-2
  2. Ejecuta:  python examples/api_assistant.py

Probar el endpoint:

  curl -X POST http://localhost:8000/api/chat \\
    -H "Content-Type: application/json" \\
    -H "X-API-Key: clave-cliente-1" \\
    -d '{"session_id": "user-42", "mensaje": "Hola, ¿qué puedes hacer?"}'

  # Sin la X-API-Key correcta el servidor responde 401.
  # Si superas API_RATE_LIMIT_PER_MINUTE responde 429.

Health check (sin auth):
  curl http://localhost:8000/health
"""

import logging
import os
import uvicorn

from behemot_framework.factory import create_behemot_app

logging.basicConfig(level=logging.INFO)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config_api.yaml")

app = create_behemot_app(
    enable_api=True,
    config_path=CONFIG_PATH,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
