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
            
            # Agregar instrucción sobre herramientas
            prompt_parts.append("\nInstrucciones: Si necesitas información que no tienes, DEBES usar las herramientas disponibles. Usa search_documents para buscar información en documentos.")
            prompt_parts.append("\nAsistente:")
            
            full_prompt = "\n".join(prompt_parts)
            
            # Generar respuesta con herramientas
            response = model_with_functions.generate_content(full_prompt)
            
            # Verificar si hay function calls en la respuesta
            if hasattr(response, 'parts'):
                for part in response.parts:
                    if hasattr(part, 'function_call'):
                        # Adaptar la respuesta al formato esperado por el framework
                        return self._create_function_call_response(part.function_call, response.text)
            
            # Si no hay function calls, crear respuesta normal
            return self._create_mock_response(response.text.strip())
            
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
            
            # Intentar crear herramientas usando la API nueva
            try:
                tools = []
                for func_decl in function_declarations:
                    tool = genai.Tool(function_declarations=[
                        genai.FunctionDeclaration(**func_decl)
                    ])
                    tools.append(tool)
                logger.info(f"✓ Herramientas Gemini creadas exitosamente: {[f['name'] for f in function_declarations]}")
                return tools
            except Exception as e:
                logger.warning(f"No se pudo usar genai.Tool, usando formato de diccionario: {e}")
                # Fallback a formato de diccionario - también aplicar limpieza aquí
                cleaned_declarations = []
                for func_decl in function_declarations:
                    cleaned_func = {
                        "name": func_decl["name"],
                        "description": func_decl["description"],
                        "parameters": self._clean_schema_for_gemini(func_decl["parameters"])
                    }
                    cleaned_declarations.append(cleaned_func)
                return [{"function_declarations": cleaned_declarations}]
                
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
                self.arguments = json.dumps(dict(gemini_function_call.args))
        
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
        
        return cleaned