# app/security/langchain_safety.py
from langchain_openai import OpenAI, ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
# Actualizar importación de pydantic (corregir advertencia de deprecación)
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

class LangChainSafetyFilter:
    """
    Filtro de seguridad utilizando componentes de LangChain
    """
    
    def __init__(self, api_key, safety_level="medium"):
        self.api_key = api_key
        self.safety_level = safety_level
        self.llm = ChatOpenAI(
            api_key=api_key, 
            model="gpt-3.5-turbo",
            temperature=0,
            max_tokens=150
        )
        
        # Configura la sensibilidad según el nivel de seguridad
        self.setup_safety_settings()
    
    def setup_safety_settings(self):
        """Configura los ajustes de seguridad según el nivel seleccionado"""
        sensitivity = {
            "low": "Solo bloquear contenido extremadamente explícito o peligroso",
            "medium": "Bloquear contenido realmente inapropiado, pero permitir conversaciones normales",
            "high": "Aplicar filtros estrictos, bloquear cualquier contenido cuestionable o sensible"
        }
        
        self.sensitivity = sensitivity.get(self.safety_level, sensitivity["medium"])
    
    async def filter_content(self, content):
        """
        Filtra el contenido utilizando LangChain
        
        Args:
            content (str): El contenido a verificar
            
        Returns:
            dict: Resultados del filtrado con claves 'is_safe', 'filtered_content' y 'reason'
        """
        # Prompt diseñado para evaluación de seguridad
        safety_template = """
        Tu trabajo es evaluar si el siguiente texto contiene contenido realmente inapropiado o peligroso.
        
        Nivel de sensibilidad: {sensitivity}
        
        IMPORTANTE: Las siguientes son conversaciones NORMALES y NO deben ser bloqueadas:
        - Preguntas sobre nombres, edad, fechas de nacimiento
        - Preguntas sobre memoria o recordar información 
        - Conversaciones casuales y amistosas
        - Intercambio de información personal básica en contexto de conversación
        
        SOLO bloquear si contiene:
        - Contenido sexual explícito
        - Violencia gráfica
        - Discurso de odio real
        - Instrucciones para actividades ilegales
        - Amenazas reales
        
        Texto a evaluar:
        ---
        {content}
        ---
        
        ¿Este contenido es realmente inapropiado y debe ser bloqueado?
        
        Responde con un JSON que tenga las siguientes claves:
        - is_safe: (true/false)
        - filtered_content: (versión filtrada del texto o null si es seguro)
        - reason: (razón por la que se consideró inseguro o null si es seguro)
        """
        
        safety_prompt = PromptTemplate.from_template(safety_template)
        
        # Crear la cadena para evaluación de seguridad
        safety_chain = safety_prompt | self.llm | StrOutputParser()
        
        try:
            logger.info(f"Evaluando seguridad para texto: '{content[:50]}...'")
            result = await safety_chain.ainvoke({
                "sensitivity": self.sensitivity,
                "content": content
            })
            
            # Parsear el resultado (debería ser un JSON)
            import json
            try:
                parsed_result = json.loads(result)
                logger.info(f"Resultado del filtro: is_safe={parsed_result['is_safe']}")
                if not parsed_result['is_safe']:
                    logger.warning(f"Contenido bloqueado. Razón: {parsed_result['reason']}")
                    # Asegurar que filtered_content siempre sea un string válido
                    if not parsed_result.get('filtered_content') or parsed_result['filtered_content'] is None:
                        parsed_result['filtered_content'] = "Lo siento, no puedo procesar este mensaje. Por favor, intenta con otro."
                return parsed_result
            except json.JSONDecodeError:
                logger.error(f"Error al parsear resultado del filtro: {result}")
                return {
                    "is_safe": True,
                    "filtered_content": content,
                    "reason": None
                }
                
        except Exception as e:
            logger.error(f"Error en filtro de seguridad: {str(e)}")
            # En caso de error, permitimos el contenido
            return {
                "is_safe": True,
                "filtered_content": content,
                "reason": None
            }
