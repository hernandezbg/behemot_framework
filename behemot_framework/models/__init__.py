# models/__init__.py
from .base_model import BaseModel
from .gpt_model import GPTModel
from .model_factory import ModelFactory

# Importar GeminiModel solo si el paquete está disponible
try:
    from .gemini_model import GeminiModel
    # Registrar automáticamente el modelo Gemini
    ModelFactory.register_model("gemini", GeminiModel)
    __all__ = ['BaseModel', 'GPTModel', 'GeminiModel', 'ModelFactory']
except ImportError:
    # Si google-generativeai no está instalado, continuar sin Gemini
    __all__ = ['BaseModel', 'GPTModel', 'ModelFactory']