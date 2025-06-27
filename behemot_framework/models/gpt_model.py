# app/models/gpt_model.py
import logging
from openai import OpenAI
from .base_model import BaseModel
from behemot_framework.config import load_config
from behemot_framework.config import Config

logger = logging.getLogger(__name__)

class GPTModel(BaseModel):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key)
        logger.info("API key cargada: %s", self.api_key)

        # Cargar la configuración para obtener los parámetros del modelo
        self.config = Config.get_config()  # Cambiado de load_config() a Config.get_config()
        self.model_name = self.config.get("MODEL_NAME", "gpt-4o-mini")
        self.temperature = float(self.config.get("MODEL_TEMPERATURE", 0.7))
        self.max_tokens = int(self.config.get("MODEL_MAX_TOKENS", 150))
        
        logger.info("Configuración del modelo cargada: modelo=%s, temperature=%s, max_tokens=%s", 
                    self.model_name, self.temperature, self.max_tokens)

    def generar_respuesta_con_functions(self, conversation: list, functions: list) -> any:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,  # Usar el modelo configurado en lugar del hardcodeado
                messages=conversation,
                functions=functions,
                function_call="auto",
                max_tokens=self.max_tokens,  # Usar el valor de la configuración
                temperature=self.temperature,  # Usar el valor de la configuración
                n=1
            )
            logger.info("Response completa: %s", response)
            return response
        except Exception as e:
            logger.error("Error en function calling: %s", str(e))
            raise

    def generar_respuesta_desde_contexto(self, conversation: list) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,  # Usar el modelo configurado
                messages=conversation,
                max_tokens=self.max_tokens,  # Usar el valor de la configuración
                temperature=self.temperature,  # Usar el valor de la configuración
                n=1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error en la API de OpenAI: {str(e)}"

    def generar_respuesta(self, mensaje_usuario: str, prompt_sistema: str) -> str:
        messages = [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": mensaje_usuario}
        ]
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,  # Usar el modelo configurado
                messages=messages,
                max_tokens=self.max_tokens,  # Usar el valor de la configuración
                temperature=self.temperature,  # Usar el valor de la configuración
                n=1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error en la API de OpenAI: {str(e)}"

