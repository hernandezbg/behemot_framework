#!/usr/bin/env python3
"""
Ejemplo de uso del conector Gradio con interfaz tipo WhatsApp.

Para ejecutar:
1. Instala las dependencias: pip install -e .
2. Configura las variables de entorno necesarias
3. Ejecuta: python examples/gradio_whatsapp_example.py

Configuración opcional:
- GRADIO_SHARE=true  # Para crear un link público temporal
- O en tu config.yaml: GRADIO_SHARE: true
"""

import asyncio
import logging
from behemot_framework.factory import BehemotFactory
from behemot_framework.config import Config

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Función principal que ejecuta el ejemplo."""
    
    # Configuración mínima para el ejemplo
    Config._config = {
        "MODEL_PROVIDER": "openai",
        "MODEL_NAME": "gpt-3.5-turbo",
        "PROMPT_SISTEMA": "Eres un asistente amigable y servicial.",
        "ENABLE_RAG": False,
        "GRADIO_SHARE": True  # Habilitar share para crear link público
    }
    
    # Crear factory
    factory = BehemotFactory()
    
    # Crear conector Gradio directamente
    from behemot_framework.connectors.gradio_connector import GradioConnector
    
    # Crear un asistente básico
    assistant = factory.crear_asistente()
    
    # Crear el conector con la nueva interfaz tipo WhatsApp
    gradio_connector = GradioConnector(
        assistant=assistant,
        tools_registry=None,
        transcriptor=None
    )
    
    logger.info("🚀 Lanzando interfaz tipo WhatsApp...")
    logger.info("📱 La interfaz tendrá un diseño similar a WhatsApp")
    
    # Lanzar la interfaz
    # El parámetro share se leerá de la configuración (GRADIO_SHARE: true)
    gradio_connector.launch(port=7860)

if __name__ == "__main__":
    asyncio.run(main())