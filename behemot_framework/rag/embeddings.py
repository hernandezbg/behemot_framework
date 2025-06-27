# app\rag\embeddings.py


"""
Módulo para manejar modelos de embeddings
"""
from typing import Dict, Any, Optional
import logging
import os

from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings


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

    @classmethod
    def get_embeddings(cls, provider: str = "openai", **kwargs) -> Any:
        """
        Obtiene un modelo de embeddings basado en el proveedor
        
        Args:
            provider: Proveedor de embeddings ('openai', 'huggingface')
            **kwargs: Parámetros específicos del proveedor
            
        Returns:
            Modelo de embeddings
        """
        if provider == "openai":
            return cls.get_openai_embeddings(**kwargs)
        elif provider == "huggingface":
            return cls.get_huggingface_embeddings(**kwargs)
        else:
            logger.warning(f"Proveedor de embeddings desconocido: {provider}, usando openai")
            return cls.get_openai_embeddings(**kwargs)