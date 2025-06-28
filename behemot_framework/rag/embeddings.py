# app\rag\embeddings.py


"""
Módulo para manejar modelos de embeddings
"""
from typing import Dict, Any, Optional
import logging
import os

from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

# Importar embeddings de Google si están disponibles
try:
    import google.generativeai as genai
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    GOOGLE_EMBEDDINGS_AVAILABLE = True
except ImportError:
    GOOGLE_EMBEDDINGS_AVAILABLE = False


logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Clase para gestionar diferentes modelos de embeddings"""

    # app/rag/embeddings.py
    @staticmethod
    def get_openai_embeddings(
        model: str = "text-embedding-3-small",
        dimensions: Optional[int] = None,
        **kwargs
    ) -> OpenAIEmbeddings:
        """
        Obtiene un modelo de embeddings de OpenAI
        
        Args:
            model: Nombre del modelo de embeddings
            dimensions: Dimensiones del vector (solo para modelos que lo soportan)
            **kwargs: Parámetros adicionales para el modelo
            
        Returns:
            Modelo de embeddings OpenAI
        """
        logger.info(f"Inicializando embeddings de OpenAI: {model}")
        
        # Usar la misma API key que está configurada para GPT
        from behemot_framework.config import GPT_API_KEY
        
        embedding_params = {
            "model": model,  # Usar model en lugar de model_name
            "openai_api_key": GPT_API_KEY,
        }
        
        # Añadir otros parámetros excepto model_name
        for key, value in kwargs.items():
            if key != "model_name":
                embedding_params[key] = value
                
        if dimensions is not None:
            embedding_params["dimensions"] = dimensions
            
        return OpenAIEmbeddings(**embedding_params)

    @staticmethod
    def get_huggingface_embeddings(
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs: Optional[Dict[str, Any]] = None,
        encode_kwargs: Optional[Dict[str, Any]] = None,
    ) -> HuggingFaceEmbeddings:
        """
        Obtiene un modelo de embeddings de HuggingFace
        
        Args:
            model_name: Nombre del modelo HuggingFace
            model_kwargs: Parámetros para la carga del modelo
            encode_kwargs: Parámetros para la codificación
            
        Returns:
            Modelo de embeddings HuggingFace
        """
        logger.info(f"Inicializando embeddings de HuggingFace: {model_name}")
        
        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs=model_kwargs or {"device": "cpu"},
            encode_kwargs=encode_kwargs or {"normalize_embeddings": True},
        )

    @staticmethod
    def get_google_embeddings(
        model: str = "models/embedding-001",
        **kwargs
    ) -> Any:
        """
        Obtiene un modelo de embeddings de Google (Gemini)
        
        Args:
            model: Nombre del modelo de embeddings de Google
            **kwargs: Parámetros adicionales para el modelo
            
        Returns:
            Modelo de embeddings Google
        """
        if not GOOGLE_EMBEDDINGS_AVAILABLE:
            raise ImportError(
                "google-generativeai y langchain-google-genai no están instalados. "
                "Ejecuta: pip install google-generativeai langchain-google-genai"
            )
        
        logger.info(f"Inicializando embeddings de Google: {model}")
        
        # Obtener API key de Gemini desde la configuración
        from behemot_framework.config import Config
        config = Config.get_config()
        api_key = config.get("GEMINI_API_KEY")
        
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY no está configurada. "
                "Agrega tu API key de Google AI en el archivo .env"
            )
        
        # Configurar la API key globalmente
        genai.configure(api_key=api_key)
        
        embedding_params = {
            "model": model,
            "google_api_key": api_key,
        }
        
        # Añadir parámetros adicionales
        embedding_params.update(kwargs)
            
        return GoogleGenerativeAIEmbeddings(**embedding_params)

    @classmethod
    def get_embeddings(cls, provider: str = "openai", **kwargs) -> Any:
        """
        Obtiene un modelo de embeddings basado en el proveedor
        
        Args:
            provider: Proveedor de embeddings ('openai', 'huggingface', 'google')
            **kwargs: Parámetros específicos del proveedor
            
        Returns:
            Modelo de embeddings
        """
        provider = provider.lower()
        
        if provider == "openai":
            return cls.get_openai_embeddings(**kwargs)
        elif provider == "huggingface":
            return cls.get_huggingface_embeddings(**kwargs)
        elif provider in ["google", "gemini"]:
            return cls.get_google_embeddings(**kwargs)
        else:
            available_providers = ["openai", "huggingface", "google"]
            logger.warning(
                f"Proveedor de embeddings '{provider}' no soportado. "
                f"Proveedores disponibles: {available_providers}. Usando openai."
            )
            return cls.get_openai_embeddings(**kwargs)