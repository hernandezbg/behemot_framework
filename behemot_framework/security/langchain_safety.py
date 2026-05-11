# app/security/langchain_safety.py
import logging
from pydantic import BaseModel, Field

# Las dependencias de langchain se importan de forma perezosa cuando se crea
# realmente un filtro con nivel != "off". Esto permite que el paquete core
# (incluido este módulo) se importe sin tener langchain instalado: los usuarios
# que quieran el filtro deben instalar `behemot-framework[rag]`.

logger = logging.getLogger(__name__)


class LangChainSafetyFilter:
    """
    Filtro de seguridad utilizando componentes de LangChain.

    Requiere las extras [rag] de behemot-framework para estar activado. Si
    SAFETY_LEVEL = "off" se puede instanciar sin langchain.
    """

    def __init__(self, api_key, safety_level="medium"):
        self.api_key = api_key
        self.safety_level = safety_level

        if safety_level.lower() == "off":
            self.llm = None
            self.sensitivity = None
            logger.info("🔓 Filtro de seguridad DESHABILITADO (SAFETY_LEVEL: off)")
            return

        # Lazy import: solo necesitamos langchain cuando el filtro está activo.
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            logger.warning(
                "⚠️  SAFETY_LEVEL='%s' pero langchain-openai no está instalado. "
                "Instala 'behemot-framework[rag]' o define SAFETY_LEVEL=off. "
                "Filtro de seguridad DESACTIVADO. (%s)",
                safety_level, e,
            )
            self.llm = None
            self.sensitivity = None
            return

        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-3.5-turbo",
            temperature=0,
            max_tokens=150,
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
        
        # Si el filtro está deshabilitado, permitir todo (sin importar langchain)
        if self.safety_level.lower() == "off" or self.llm is None:
            logger.debug(f"Filtro de seguridad omitido (deshabilitado) para: '{content[:50]}...'")
            return {
                "is_safe": True,
                "filtered_content": content,
                "reason": None
            }
        
        try:
            # Lazy import: solo cuando realmente invocamos el filtro
            from langchain_core.prompts import PromptTemplate
            from langchain_core.output_parsers import StrOutputParser

            safety_prompt = PromptTemplate.from_template(safety_template)
            safety_chain = safety_prompt | self.llm | StrOutputParser()

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
                # Formato no reconocido: tratar como UNSAFE (fail-closed).
                # Permitir contenido ante un fallo del filtro convertía cualquier
                # timeout/respuesta corrupta en un bypass silencioso.
                logger.warning(
                    f"⚠️ Formato no reconocido del filtro, bloqueando por defecto: {result}"
                )
                return {
                    "is_safe": False,
                    "filtered_content": "Lo siento, no puedo procesar este mensaje en este momento. Inténtalo de nuevo.",
                    "reason": "Formato de respuesta del filtro no reconocido (fail-closed)"
                }

        except Exception as e:
            # Fail-closed ante error: si el filtro no responde, no asumimos
            # que el contenido es seguro. El operador debe monitorizar estos
            # warnings — un atacante puede causarlos provocando timeouts.
            logger.error(f"❌ Error en filtro de seguridad (fail-closed): {str(e)}")
            return {
                "is_safe": False,
                "filtered_content": "Lo siento, no puedo procesar este mensaje en este momento. Inténtalo de nuevo.",
                "reason": f"Filtro de seguridad no disponible: {type(e).__name__}"
            }
