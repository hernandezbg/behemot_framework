# models/vertex_model.py
import logging
import json
from typing import List, Dict, Any, Optional
from .base_model import BaseModel
from behemot_framework.config import Config

logger = logging.getLogger(__name__)

class VertexModel(BaseModel):
    """
    Implementación del modelo Vertex AI de Google Cloud para el framework Behemot.
    Utiliza la API de Vertex AI que requiere Service Account de GCP.
    """
    
    def __init__(self, api_key: str):
        """
        Inicializa el modelo Vertex AI con configuración de GCP.
        
        Args:
            api_key: No se usa directamente, se usan las credenciales de GCP
        """
        try:
            # Importar las librerías de Vertex AI
            from google.cloud import aiplatform
            from vertexai.generative_models import GenerativeModel, GenerationConfig
            
            # Cargar configuración
            self.config = Config.get_config()
            
            # Configuración de Vertex AI
            self.project_id = self.config.get("VERTEX_PROJECT_ID")
            self.location = self.config.get("VERTEX_LOCATION", "us-central1")
            self.model_name = self.config.get("MODEL_NAME", "gemini-1.5-pro")
            
            if not self.project_id:
                raise ValueError("VERTEX_PROJECT_ID es requerido para usar Vertex AI")
            
            # Inicializar Vertex AI
            aiplatform.init(project=self.project_id, location=self.location)
            
            # Configuración de generación
            self.temperature = float(self.config.get("MODEL_TEMPERATURE", 0.7))
            self.max_tokens = int(self.config.get("MODEL_MAX_TOKENS", 2048))
            
            self.generation_config = GenerationConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            )
            
            # Inicializar el modelo generativo
            self.model = GenerativeModel(
                model_name=self.model_name,
                generation_config=self.generation_config
            )
            
            logger.info(f"Modelo Vertex AI inicializado: {self.model_name} en {self.project_id}/{self.location}")
            
        except ImportError as e:
            logger.error(f"Error importando librerías de Vertex AI: {e}")
            raise ImportError("Para usar Vertex AI, instala: pip install google-cloud-aiplatform")
        except Exception as e:
            logger.error(f"Error inicializando Vertex AI: {e}")
            raise
    
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
            logger.error(f"Error en Vertex AI: {str(e)}")
            return f"Error en la API de Vertex AI: {str(e)}"
    
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
            # Vertex AI maneja function calling de manera similar a Gemini
            # Usar prompt engineering para mejor compatibilidad
            logger.info("🔧 Vertex AI: Usando prompt engineering para function calling")
            
            # Construir el prompt desde la conversación
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
            
            # Agregar instrucciones para function calling
            if functions:
                tools_descriptions = []
                for func in functions:
                    name = func["name"]
                    desc = func.get("description", "")
                    tools_descriptions.append(f"- {name}: {desc}")
                
                tools_text = "\n".join(tools_descriptions)
                prompt_parts.append(f"\nHerramientas disponibles:\n{tools_text}")
                prompt_parts.append("\nSi necesitas información que no tienes, responde EXACTAMENTE en este formato:")
                prompt_parts.append("USAR_HERRAMIENTA: nombre_herramienta")
                prompt_parts.append("ARGUMENTOS: {{\"parametro\": \"valor\"}}")
            
            prompt_parts.append("\nAsistente:")
            
            full_prompt = "\n".join(prompt_parts)
            
            # Generar respuesta
            response = self.model.generate_content(full_prompt)
            
            # Procesar respuesta con prompt engineering
            return self._process_prompt_engineered_response(response.text.strip(), functions)
            
        except Exception as e:
            logger.error(f"Error en function calling con Vertex AI: {str(e)}")
            # Si falla, intentar sin herramientas
            return self._fallback_without_tools(conversation)
    
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
            return f"Error en la API de Vertex AI: {str(e)}"
    
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
    
    def _fallback_without_tools(self, conversation: List[Dict[str, str]]) -> Any:
        """
        Fallback que genera respuesta sin herramientas cuando hay error.
        """
        try:
            # Generar respuesta normal
            text_response = self.generar_respuesta_desde_contexto(conversation)
            return self._create_mock_response(text_response)
        except Exception as e:
            logger.error(f"Error en fallback: {str(e)}")
            return self._create_mock_response("Error al generar respuesta.")
    
    def _process_prompt_engineered_response(self, response_text: str, functions: List[Dict[str, Any]]) -> Any:
        """
        Procesa una respuesta que usa prompt engineering en lugar de function calling nativo.
        
        Args:
            response_text: Texto de respuesta de Vertex AI
            functions: Lista de funciones disponibles
            
        Returns:
            Respuesta procesada en formato esperado
        """
        try:
            # Buscar patrones de herramientas en la respuesta
            if "USAR_HERRAMIENTA:" in response_text:
                lines = response_text.split('\n')
                tool_name = None
                arguments = "{}"
                
                for line in lines:
                    if line.startswith("USAR_HERRAMIENTA:"):
                        tool_name = line.replace("USAR_HERRAMIENTA:", "").strip()
                    elif line.startswith("ARGUMENTOS:"):
                        arguments = line.replace("ARGUMENTOS:", "").strip()
                
                if tool_name:
                    logger.info(f"🔧 Vertex AI detectó uso de herramienta: {tool_name}")
                    # Crear un mock function call response
                    class MockFunctionCall:
                        def __init__(self, name, args):
                            self.name = name
                            self.arguments = args
                    
                    mock_call = MockFunctionCall(tool_name, arguments)
                    return self._create_function_call_response(mock_call, None)
            
            # Si no se detectó herramienta, respuesta normal
            return self._create_mock_response(response_text)
            
        except Exception as e:
            logger.error(f"Error procesando respuesta con prompt engineering: {e}")
            return self._create_mock_response(response_text)
    
    def _create_function_call_response(self, function_call, response_text: str) -> Any:
        """
        Crea una respuesta de function call compatible con el formato OpenAI.
        
        Args:
            function_call: El function call mock
            response_text: Texto de respuesta si existe
            
        Returns:
            Objeto compatible con el formato OpenAI
        """
        class MockChoice:
            def __init__(self, function_call):
                self.message = MockMessage(function_call)
        
        class MockMessage:
            def __init__(self, function_call):
                self.content = None
                self.function_call = function_call
        
        class MockResponse:
            def __init__(self, function_call):
                self.choices = [MockChoice(function_call)]
        
        return MockResponse(function_call)