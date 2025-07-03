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
        
        # Si está deshabilitado, no inicializar LLM
        if safety_level.lower() == "off":
            self.llm = None
            self.sensitivity = None
            logger.info("🔓 Filtro de seguridad DESHABILITADO (SAFETY_LEVEL: off)")
        else:
            self.llm = ChatOpenAI(
                api_key=api_key, 
                model="gpt-3.5-turbo",
                temperature=0,
                max_tokens=150
            )
            
            # Configura la sensibilidad según el nivel de seguridad
            self.setup_safety_settings()
            logger.info(f"🛡️ Filtro de seguridad ACTIVADO (nivel: {safety_level})")
    
    def setup_safety_settings(self):
        """Configura los ajustes de seguridad según el nivel seleccionado"""
        sensitivity = {
            "low": "Muy permisivo - Solo bloquear contenido extremadamente peligroso como violencia gráfica o pornografía explícita",
            "medium": "Equilibrado - Bloquear contenido inapropiado real, pero permitir conversaciones normales sobre nombres, edad, etc.",
            "high": "Estricto - Bloquear contenido cuestionable, pero siempre permitir preguntas educativas y conversación casual"
        }
        
        self.sensitivity = sensitivity.get(self.safety_level.lower(), sensitivity["medium"])
    
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
Eres un filtro de seguridad para un chatbot. Tu trabajo es identificar contenido REALMENTE peligroso.

NIVEL DE SENSIBILIDAD: {sensitivity}

IMPORTANTE - Estas son conversaciones NORMALES que SIEMPRE debes permitir:
• Preguntas sobre nombres, edad, fechas de nacimiento
• Preguntas sobre memoria o información pasada  
• Conversaciones casuales y amistosas
• Intercambio de información personal básica
• Preguntas generales y educativas

SOLO marcar como UNSAFE si contiene:
• Contenido sexual explícito o pornográfico
• Violencia gráfica o amenazas reales
• Discurso de odio extremo
• Instrucciones para actividades ilegales
• Intención clara de causar daño

Texto a evaluar: "{content}"

Responde EXACTAMENTE con una de estas opciones:
SAFE
UNSAFE: [razón específica]
        """
        
        safety_prompt = PromptTemplate.from_template(safety_template)
        
        # Crear la cadena para evaluación de seguridad
        safety_chain = safety_prompt | self.llm | StrOutputParser()
        
        # Si el filtro está deshabilitado, permitir todo
        if self.safety_level.lower() == "off" or self.llm is None:
            logger.debug(f"Filtro de seguridad omitido (deshabilitado) para: '{content[:50]}...'")
            return {
                "is_safe": True,
                "filtered_content": content,
                "reason": None
            }
        
        try:
            logger.info(f"🔍 Evaluando seguridad (nivel {self.safety_level}) para: '{content[:50]}...'")
            result = await safety_chain.ainvoke({
                "content": content,
                "sensitivity": self.sensitivity
            })
            
            # Parsear respuesta simplificada
            result = result.strip()
            
            if result.upper().startswith("SAFE"):
                logger.info(f"✅ Contenido aprobado por filtro de seguridad")
                return {
                    "is_safe": True,
                    "filtered_content": content,
                    "reason": None
                }
            elif result.upper().startswith("UNSAFE"):
                reason = result.replace("UNSAFE:", "").strip()
                if not reason:
                    reason = "Contenido considerado inapropiado"
                logger.warning(f"🚫 Contenido bloqueado por filtro de seguridad. Razón: {reason}")
                return {
                    "is_safe": False,
                    "filtered_content": "Lo siento, no puedo procesar este mensaje. Por favor, intenta con otro.",
                    "reason": reason
                }
            else:
                # Si no reconoce el formato, permitir el contenido (fail-safe)
                logger.warning(f"⚠️ Formato no reconocido del filtro, permitiendo contenido: {result}")
                return {
                    "is_safe": True,
                    "filtered_content": content,
                    "reason": None
                }
                
        except Exception as e:
            logger.error(f"❌ Error en filtro de seguridad: {str(e)}")
            # En caso de error, permitimos el contenido (fail-safe)
            return {
                "is_safe": True,
                "filtered_content": content,
                "reason": None
            }
