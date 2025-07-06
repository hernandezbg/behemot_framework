# models/__init__.py
from .base_model import BaseModel
from .gpt_model import GPTModel
from .model_factory import ModelFactory

# Importar GeminiModel solo si el paquete está disponible
try:
    from .gemini_model import GeminiModel
    # Registrar automáticamente el modelo Gemini
    ModelFactory.register_model("gemini", GeminiModel)
    gemini_available = True
except ImportError:
    # Si google-generativeai no está instalado, continuar sin Gemini
    gemini_available = False

# Importar VertexModel solo si el paquete está disponible
try:
    from .vertex_model import VertexModel
    # Registrar automáticamente el modelo Vertex
    ModelFactory.register_model("vertex", VertexModel)
    vertex_available = True
except ImportError:
    # Si google-cloud-aiplatform no está instalado, continuar sin Vertex
    vertex_available = False

# Construir __all__ dinámicamente
__all__ = ['BaseModel', 'GPTModel', 'ModelFactory']
if gemini_available:
    __all__.append('GeminiModel')
if vertex_available:
    __all__.append('VertexModel')