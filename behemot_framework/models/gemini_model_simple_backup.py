# models/gemini_model.py
import logging
import json
from typing import List, Dict, Any
import google.generativeai as genai
from .base_model import BaseModel
from behemot_framework.config import Config


logger = logging.getLogger(__name__)


class GeminiModel(BaseModel):
    """
    Implementación del modelo Gemini de Google para el framework Behemot.
    Versión simplificada sin function calling hasta resolver compatibilidad.
    """
    
    def __init__(self, api_key: str):
        """
        Inicializa el modelo Gemini con la API key proporcionada.
        
        Args:
            api_key: La clave API de Google AI
        """
        self.api_key = api_key
        genai.configure(api_key=self.api_key)
        
        # Cargar configuración
        self.config = Config.get_config()
        self.model_name = self.config.get("MODEL_NAME", "gemini-1.5-pro")
        self.temperature = float(self.config.get("MODEL_TEMPERATURE", 0.7))
        self.max_tokens = int(self.config.get("MODEL_MAX_TOKENS", 2048))
        
        # Configuración de generación
        self.generation_config = genai.GenerationConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )
        
        # Inicializar el modelo
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config
        )
        
        logger.info(f"Modelo Gemini inicializado: {self.model_name}")
    
    def generar_respuesta(self, mensaje_usuario: str, prompt_sistema: str) -> str:
        """
        Genera una respuesta simple sin contexto de conversación.
        
        Args:
            mensaje_usuario: El mensaje del usuario
            prompt_sistema: El prompt del sistema que define el comportamiento
            
        Returns:
            La respuesta generada como string
        """
        try:
            # Combinar prompt del sistema con el mensaje del usuario
            prompt_completo = f"{prompt_sistema}\n\nUsuario: {mensaje_usuario}\nAsistente:"
            
            response = self.model.generate_content(prompt_completo)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Error en Gemini API: {str(e)}")
            return f"Error en la API de Gemini: {str(e)}"
    
    def generar_respuesta_con_functions(self, conversation: List[Dict[str, str]], functions: List[Dict[str, Any]]) -> Any:
        """
        Genera una respuesta con soporte para function calling.
        Por ahora, simula el comportamiento sin usar funciones nativas de Gemini.
        
        Args:
            conversation: Lista de mensajes de la conversación
            functions: Lista de definiciones de funciones disponibles
            
        Returns:
            El objeto de respuesta completo adaptado al formato esperado
        """
        try:
            # Por ahora, ignoramos las funciones y generamos una respuesta normal
            # Esto es temporal hasta resolver la compatibilidad con function calling
            
            # Construir el prompt desde la conversación
            prompt_parts = []
            system_message = None
            
            for msg in conversation:
                role = msg["role"]
                content = msg["content"]
                
                if role == "system":
                    system_message = content
                elif role == "user":
                    prompt_parts.append(f"Usuario: {content}")
                elif role == "assistant":
                    prompt_parts.append(f"Asistente: {content}")
            
            # Combinar todo el contexto
            if system_message:
                full_prompt = f"{system_message}\n\n" + "\n".join(prompt_parts)
            else:
                full_prompt = "\n".join(prompt_parts)
            
            full_prompt += "\nAsistente:"
            
            # Generar respuesta
            response = self.model.generate_content(full_prompt)
            
            # Adaptar la respuesta al formato esperado por el framework
            return self._create_mock_response(response.text.strip())
            
        except Exception as e:
            logger.error(f"Error en function calling con Gemini: {str(e)}")
            raise
    
    def generar_respuesta_desde_contexto(self, conversation: List[Dict[str, str]]) -> str:
        """
        Genera una respuesta basada en el contexto completo de la conversación.
        
        Args:
            conversation: Lista completa de mensajes de la conversación
            
        Returns:
            La respuesta generada como string
        """
        try:
            # Construir el prompt completo desde la conversación
            prompt_parts = []
            
            for msg in conversation:
                role = msg["role"]
                content = msg["content"]
                
                if role == "system":
                    prompt_parts.append(f"Sistema: {content}")
                elif role == "user":
                    prompt_parts.append(f"Usuario: {content}")
                elif role == "assistant":
                    prompt_parts.append(f"Asistente: {content}")
                elif role == "function":
                    # Manejar resultados de funciones
                    function_name = msg.get("name", "función")
                    prompt_parts.append(f"Resultado de {function_name}: {content}")
            
            # Agregar indicador para la respuesta del asistente
            prompt_parts.append("Asistente:")
            
            full_prompt = "\n\n".join(prompt_parts)
            
            response = self.model.generate_content(full_prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Error generando respuesta desde contexto: {str(e)}")
            return f"Error en la API de Gemini: {str(e)}"
    
    def _create_mock_response(self, text_content: str) -> Any:
        """
        Crea una respuesta mock compatible con el formato OpenAI.
        
        Args:
            text_content: El contenido de texto de la respuesta
            
        Returns:
            Objeto mock que simula la estructura de respuesta de OpenAI
        """
        class MockChoice:
            def __init__(self, content):
                self.message = MockMessage(content)
        
        class MockMessage:
            def __init__(self, content):
                self.content = content
                self.function_call = None
        
        class MockResponse:
            def __init__(self, content):
                self.choices = [MockChoice(content)]
        
        return MockResponse(text_content)