"""
Ejemplo MÍNIMO de un asistente Behemot.

Levanta un servidor con:
  - API REST en  POST  http://localhost:8000/api/chat
  - Interfaz Gradio en   http://localhost:7860  (para probar el bot visualmente)

Requisitos:
  pip install -e .
  export GPT_API_KEY=sk-...

Ejecutar:
  python examples/minimal_assistant.py
"""

import logging
import uvicorn

from behemot_framework.factory import create_behemot_app

logging.basicConfig(level=logging.INFO)

# Resolver la ruta del YAML relativa al propio archivo, así el ejemplo se
# puede ejecutar desde cualquier CWD sin romper.
import os
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config_minimal.yaml")

app = create_behemot_app(
    enable_api=True,
    enable_test_local=True,    # Gradio para probar en el navegador
    config_path=CONFIG_PATH,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
