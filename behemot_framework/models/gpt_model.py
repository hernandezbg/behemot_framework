# app/models/gpt_model.py
import logging
import base64
from typing import Optional
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
    
    def soporta_vision(self) -> bool:
        """
        GPT-4o y GPT-4-vision-preview soportan procesamiento de imágenes.
        """
        vision_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-vision-preview", "gpt-4-turbo"]
        return any(model in self.model_name for model in vision_models)
    
    def _encode_image(self, image_path: str) -> str:
        """
        Codifica una imagen en base64 para enviarla a OpenAI.
        
        Args:
            image_path: Ruta al archivo de imagen
            
        Returns:
            Imagen codificada en base64
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def _create_image_message(self, text: str, image_path: Optional[str] = None) -> dict:
        """
        Crea un mensaje que puede incluir texto e imagen.
        
        Args:
            text: Texto del mensaje
            image_path: Ruta opcional a la imagen
            
        Returns:
            Mensaje formateado para OpenAI
        """
        if image_path and self.soporta_vision():
            try:
                base64_image = self._encode_image(image_path)
                return {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": text
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            except Exception as e:
                logger.error(f"Error procesando imagen {image_path}: {e}")
                # Si falla la imagen, enviar solo texto
                return {"role": "user", "content": text}
        else:
            return {"role": "user", "content": text}

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

    def generar_respuesta(self, mensaje_usuario: str, prompt_sistema: str, imagen_path: Optional[str] = None) -> str:
        messages = [
            {"role": "system", "content": prompt_sistema},
            self._create_image_message(mensaje_usuario, imagen_path)
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

