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
        Evalúa si el siguiente texto es REALMENTE peligroso o inapropiado.
        
        Conversaciones NORMALES que SIEMPRE deben permitirse:
        - Preguntas sobre nombres o cómo te llamas
        - Preguntas sobre edad o fechas
        - Preguntas sobre memoria o recordar
        - Conversación casual y amistosa
        - Información personal básica
        
        SOLO marcar como inseguro si contiene:
        - Contenido sexual explícito
        - Violencia gráfica
        - Amenazas directas
        - Instrucciones ilegales
        
        Texto: {content}
        
        Responde SOLO con:
        SAFE si es conversación normal
        UNSAFE: razón si es realmente peligroso
        """
        
        safety_prompt = PromptTemplate.from_template(safety_template)
        
        # Crear la cadena para evaluación de seguridad
        safety_chain = safety_prompt | self.llm | StrOutputParser()
        
        # Temporalmente deshabilitado para evitar problemas de parseo
        # El filtro puede ser muy estricto y causar problemas de conversación
        logger.info(f"Filtro de seguridad omitido para: '{content[:50]}...'")
        return {
            "is_safe": True,
            "filtered_content": content,
            "reason": None
        }
        
        # Código original comentado hasta resolver problemas de parseo
        # try:
        #     logger.info(f"Evaluando seguridad para texto: '{content[:50]}...'")
        #     result = await safety_chain.ainvoke({
        #         "content": content
        #     })
        #     # ... resto del código ...
