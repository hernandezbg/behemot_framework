# models/gemini_model.py
import logging
import json
from typing import List, Dict, Any, Optional
from PIL import Image
import google.generativeai as genai
from .base_model import BaseModel
from behemot_framework.config import Config


logger = logging.getLogger(__name__)


class GeminiModel(BaseModel):
    """
    Implementación del modelo Gemini de Google para el framework Behemot.
    Versión con function calling real implementado.
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
        
        # Inicializar el modelo base
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config
        )
        
        logger.info(f"Modelo Gemini inicializado: {self.model_name}")
    
    def soporta_vision(self) -> bool:
        """
        Gemini 1.5 Pro y Flash soportan procesamiento de imágenes nativamente.
        """
        vision_models = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro-vision"]
        return any(model in self.model_name for model in vision_models)
    
    def _create_content_with_image(self, texto: str, imagen_path: Optional[str] = None) -> list:
        """
        Crea contenido que puede incluir texto e imagen para Gemini.
        
        Args:
            texto: Texto del mensaje
            imagen_path: Ruta opcional a la imagen
            
        Returns:
            Lista de contenido para Gemini
        """
        content_parts = [texto]
        
        if imagen_path and self.soporta_vision():
            try:
                # Cargar imagen usando PIL
                img = Image.open(imagen_path)
                content_parts.append(img)
                logger.info(f"Imagen agregada al contenido: {imagen_path}")
            except Exception as e:
                logger.error(f"Error cargando imagen {imagen_path}: {e}")
                # Si falla la imagen, continuar solo con texto
        
        return content_parts
    
    def generar_respuesta(self, mensaje_usuario: str, prompt_sistema: str, imagen_path: Optional[str] = None) -> str:
        """
        Genera una respuesta simple sin contexto de conversación.
        
        Args:
            mensaje_usuario: El mensaje del usuario
            prompt_sistema: El prompt del sistema que define el comportamiento
            imagen_path: Ruta opcional a una imagen para procesamiento multimodal
            
        Returns:
            La respuesta generada como string
        """
        try:
            # Combinar prompt del sistema con el mensaje del usuario
            prompt_completo = f"{prompt_sistema}\n\nUsuario: {mensaje_usuario}\nAsistente:"
            
            # Crear contenido que puede incluir imagen
            content_parts = self._create_content_with_image(prompt_completo, imagen_path)
            
            response = self.model.generate_content(content_parts)
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
            # Por ahora, usar solo prompt engineering hasta resolver los problemas de esquemas
            logger.info("🔧 Usando SOLO prompt engineering (evitando errores de esquemas)")
            model_with_functions = self.model
            use_native_functions = False
            
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
            
            # Agregar instrucciones diferentes según el modo
            if use_native_functions:
                prompt_parts.append("\nInstrucciones: Si necesitas información que no tienes, DEBES usar las herramientas disponibles. Usa search_documents para buscar información en documentos.")
            else:
                # Prompt engineering para simular function calling
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
            response = model_with_functions.generate_content(full_prompt)
            
            if use_native_functions:
                # Verificar si hay function calls en la respuesta nativa
                if hasattr(response, 'parts'):
                    for part in response.parts:
                        if hasattr(part, 'function_call'):
                            # Adaptar la respuesta al formato esperado por el framework
                            return self._create_function_call_response(part.function_call, response.text)
                
                # Si no hay function calls, crear respuesta normal
                return self._create_mock_response(response.text.strip())
            else:
                # Procesar respuesta con prompt engineering
                return self._process_prompt_engineered_response(response.text.strip(), functions)
            
        except Exception as e:
            logger.error(f"Error en function calling con Gemini: {str(e)}")
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
            return f"Error en la API de Gemini: {str(e)}"
    
    def _convert_functions_to_gemini_format(self, openai_functions: List[Dict[str, Any]]) -> List[Any]:
        """
        Convierte las funciones del formato OpenAI al formato de Gemini.
        
        Args:
            openai_functions: Lista de funciones en formato OpenAI
            
        Returns:
            Lista de herramientas en formato Gemini
        """
        try:
            logger.info(f"🚀 INICIO - Convirtiendo {len(openai_functions)} funciones a formato Gemini")
            function_declarations = []
            
            for func in openai_functions:
                # Extraer información de la función
                name = func["name"]
                description = func.get("description", "")
                parameters = func.get("parameters", {})
                
                # Limpiar parámetros para Gemini - remover campos incompatibles
                logger.info(f"🔍 Parámetros originales para {name}: {parameters}")
                cleaned_parameters = self._clean_schema_for_gemini(parameters)
                logger.info(f"✅ Parámetros limpiados para {name}: {cleaned_parameters}")
                
                # Crear la definición de función para Gemini usando diccionarios
                function_declaration = {
                    "name": name,
                    "description": description,
                    "parameters": cleaned_parameters
                }
                
                function_declarations.append(function_declaration)
            
            # Saltar la API nueva directamente y usar formato de diccionario limpio
            logger.info("🔧 Usando formato de diccionario para herramientas Gemini (evitando genai.Tool)")
            return [{"function_declarations": function_declarations}]
                
        except Exception as e:
            logger.error(f"Error convirtiendo funciones a formato Gemini: {str(e)}")
            return []
    
    def _create_function_call_response(self, function_call, response_text: str) -> Any:
        """
        Crea una respuesta de function call compatible con el formato OpenAI.
        
        Args:
            function_call: El function call de Gemini
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
                self.function_call = MockFunctionCall(function_call)
        
        class MockFunctionCall:
            def __init__(self, gemini_function_call):
                self.name = gemini_function_call.name
                # Manejar tanto objetos con 'args' como con 'arguments'
                if hasattr(gemini_function_call, 'args'):
                    self.arguments = json.dumps(dict(gemini_function_call.args))
                elif hasattr(gemini_function_call, 'arguments'):
                    self.arguments = gemini_function_call.arguments
                else:
                    self.arguments = "{}"
        
        class MockResponse:
            def __init__(self, function_call):
                self.choices = [MockChoice(function_call)]
        
        return MockResponse(function_call)
    
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
    
    def _clean_schema_for_gemini(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Limpia un esquema JSON de OpenAI para que sea compatible con Gemini.
        Remueve campos que Gemini no reconoce.
        
        Args:
            schema: Esquema en formato OpenAI
            
        Returns:
            Esquema limpio compatible con Gemini
        """
        if not isinstance(schema, dict):
            return schema
            
        logger.info(f"🧹 Limpiando esquema para Gemini: {schema}")
            
        # Campos incompatibles con Gemini que deben ser removidos
        incompatible_fields = {
            "additionalProperties",
            "$schema", 
            "definitions",
            "anyOf",
            "oneOf",
            "allOf",
            "not",
            "if", "then", "else",
            "dependentRequired",
            "dependentSchemas",
            "unevaluatedProperties",
            "unevaluatedItems",
            "contentEncoding",
            "contentMediaType",
            "examples",
            "default",  # Gemini puede tener problemas con defaults en algunos casos
            "const",
            "contains",
            "maxContains",
            "minContains",
            "uniqueItems",
            "multipleOf"
        }
        
        cleaned = {}
        
        for key, value in schema.items():
            # Saltar campos incompatibles
            if key in incompatible_fields:
                logger.info(f"🔧 Removiendo campo incompatible con Gemini: {key}")
                continue
                
            # Limpiar recursivamente objetos anidados
            if isinstance(value, dict):
                if key == "properties":
                    # Limpiar cada propiedad
                    cleaned_properties = {}
                    for prop_name, prop_schema in value.items():
                        cleaned_properties[prop_name] = self._clean_schema_for_gemini(prop_schema)
                    cleaned[key] = cleaned_properties
                else:
                    cleaned[key] = self._clean_schema_for_gemini(value)
            elif isinstance(value, list):
                # Limpiar elementos de array
                if key == "items" and len(value) > 0 and isinstance(value[0], dict):
                    cleaned[key] = self._clean_schema_for_gemini(value[0])
                else:
                    cleaned[key] = value
            else:
                cleaned[key] = value
        
        logger.info(f"✨ Esquema limpiado resultado: {cleaned}")
        return cleaned
    
    def _process_prompt_engineered_response(self, response_text: str, functions: List[Dict[str, Any]]) -> Any:
        """
        Procesa una respuesta que usa prompt engineering en lugar de function calling nativo.
        
        Args:
            response_text: Texto de respuesta de Gemini
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
                    logger.info(f"🔧 Prompt engineering detectó uso de herramienta: {tool_name}")
                    # Crear un mock function call response
                    class MockFunctionCall:
                        def __init__(self, name, args):
                            self.name = name
                            self.arguments = args
                            # No necesita 'args' attribute para prompt engineering
                    
                    mock_call = MockFunctionCall(tool_name, arguments)
                    return self._create_function_call_response(mock_call, None)
            
            # Si no se detectó herramienta, respuesta normal
            return self._create_mock_response(response_text)
            
        except Exception as e:
            logger.error(f"Error procesando respuesta con prompt engineering: {e}")
            return self._create_mock_response(response_text)