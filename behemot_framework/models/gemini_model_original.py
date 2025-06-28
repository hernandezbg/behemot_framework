# models/gemini_model.py
import logging
import json
from typing import List, Dict, Any
import google.generativeai as genai
from google.generativeai.types import content_types
from .base_model import BaseModel
from behemot_framework.config import Config


logger = logging.getLogger(__name__)


class GeminiModel(BaseModel):
    """
    Implementación del modelo Gemini de Google para el framework Behemot.
    Soporta todas las capacidades incluyendo function calling.
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
        
        Args:
            conversation: Lista de mensajes de la conversación
            functions: Lista de definiciones de funciones disponibles
            
        Returns:
            El objeto de respuesta completo adaptado al formato esperado
        """
        try:
            # Convertir las funciones del formato OpenAI al formato Gemini
            gemini_tools = self._convert_functions_to_gemini_format(functions)
            
            # Crear el modelo con las funciones
            model_with_functions = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=self.generation_config,
                tools=gemini_tools
            )
            
            # Construir el historial de chat para Gemini
            chat = model_with_functions.start_chat(history=[])
            
            # Obtener el último mensaje del usuario
            last_user_message = None
            system_message = None
            
            for msg in conversation:
                if msg["role"] == "system":
                    system_message = msg["content"]
                elif msg["role"] == "user":
                    last_user_message = msg["content"]
            
            # Combinar system message con el último mensaje si existe
            if system_message and last_user_message:
                prompt = f"{system_message}\n\n{last_user_message}"
            else:
                prompt = last_user_message or ""
            
            # Generar respuesta
            response = chat.send_message(prompt)
            
            # Adaptar la respuesta al formato esperado por el framework
            return self._adapt_gemini_response(response, functions)
            
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
    
    def _convert_functions_to_gemini_format(self, openai_functions: List[Dict[str, Any]]) -> List[Any]:
        """
        Convierte las funciones del formato OpenAI al formato de Gemini.
        
        Args:
            openai_functions: Lista de funciones en formato OpenAI
            
        Returns:
            Lista de herramientas en formato Gemini
        """
        gemini_functions = []
        
        for func in openai_functions:
            # Extraer información de la función
            name = func["name"]
            description = func.get("description", "")
            parameters = func.get("parameters", {})
            
            # Crear la definición de función para Gemini
            # Usar un diccionario simple en lugar de clases específicas
            function_declaration = {
                "name": name,
                "description": description,
                "parameters": parameters
            }
            
            gemini_functions.append(function_declaration)
        
        # Retornar las funciones en el formato esperado por Gemini
        return [{"function_declarations": gemini_functions}]
    
    def _adapt_gemini_response(self, gemini_response, original_functions: List[Dict[str, Any]]) -> Any:
        """
        Adapta la respuesta de Gemini al formato esperado por el framework.
        
        Args:
            gemini_response: Respuesta de Gemini
            original_functions: Lista original de funciones para referencia
            
        Returns:
            Objeto adaptado al formato del framework
        """
        # Crear una respuesta compatible con el formato OpenAI
        class AdaptedResponse:
            def __init__(self, gemini_response, functions):
                self.gemini_response = gemini_response
                self.functions = functions
                self.choices = [self._create_choice()]
            
            def _create_choice(self):
                class Choice:
                    def __init__(self, gemini_response):
                        self.message = self._create_message(gemini_response)
                    
                    def _create_message(self, response):
                        class Message:
                            def __init__(self, response):
                                # Verificar si hay function calls
                                if hasattr(response, 'parts'):
                                    for part in response.parts:
                                        if hasattr(part, 'function_call'):
                                            # Es una llamada a función
                                            self.content = None
                                            self.function_call = {
                                                "name": part.function_call.name,
                                                "arguments": json.dumps(dict(part.function_call.args))
                                            }
                                            return
                                
                                # Es una respuesta de texto normal
                                self.content = response.text
                                self.function_call = None
                        
                        return Message(response)
                
                return Choice(self.gemini_response)
        
        return AdaptedResponse(gemini_response, original_functions)