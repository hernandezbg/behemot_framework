# app\rag\retriever.py

"""
Módulo para implementar retrievers para el sistema RAG
"""
from typing import List, Dict, Any, Optional, Union
import logging

from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain_community.vectorstores import Chroma
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel


logger = logging.getLogger(__name__)


class RAGRetriever:
    """Clase para manejar la recuperación de documentos para RAG"""

    @staticmethod
    def get_vectorstore_retriever(
        vectorstore: Chroma,
        search_type: str = "similarity",
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> BaseRetriever:
        """
        Obtiene un retriever básico desde un vectorstore
        
        Args:
            vectorstore: Base de datos vectorial
            search_type: Tipo de búsqueda ('similarity', 'mmr')
            search_kwargs: Parámetros adicionales para la búsqueda
            
        Returns:
            Retriever configurado
        """
        logger.info(f"Configurando retriever para vectorstore con búsqueda: {search_type}")
        
        return vectorstore.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs or {"k": 4},
        )

    @staticmethod
    def get_compression_retriever(
        base_retriever: BaseRetriever,
        llm: BaseLanguageModel,
    ) -> ContextualCompressionRetriever:
        """
        Crea un retriever con compresión contextual
        
        Args:
            base_retriever: Retriever base a mejorar
            llm: Modelo de lenguaje para la compresión
            
        Returns:
            Retriever con compresión
        """
        logger.info("Configurando retriever con compresión contextual")
        
        compressor = LLMChainExtractor.from_llm(llm)
        
        return ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=base_retriever,
        )

    @staticmethod
    async def aretrieve_documents(
        retriever: BaseRetriever,
        query: str,
    ) -> List[Document]:
        """
        Recupera documentos de forma asíncrona
        
        Args:
            retriever: Retriever a usar
            query: Consulta para la búsqueda
            
        Returns:
            Lista de documentos recuperados
        """
        logger.info(f"Recuperando documentos para: {query}")
        
        return await retriever.aretrieve(query)

    @staticmethod
    def retrieve_documents(
        retriever: BaseRetriever,
        query: str,
    ) -> List[Document]:
        """
        Recupera documentos de forma síncrona
        
        Args:
            retriever: Retriever a usar
            query: Consulta para la búsqueda
            
        Returns:
            Lista de documentos recuperados
        """
        logger.info(f"Recuperando documentos para: {query}")
        
        return retriever.get_relevant_documents(query)

    @staticmethod
    def format_retrieved_documents(documents: List[Document]) -> str:
        """
        Formatea documentos recuperados para usarlos como contexto
        
        Args:
            documents: Lista de documentos recuperados
            
        Returns:
            Texto formateado con el contenido de los documentos
        """
        if not documents:
            return "No se encontraron documentos relevantes."
            
        context_text = "\n\n".join(
            f"--- Documento {i+1} ---\n{doc.page_content}"
            for i, doc in enumerate(documents)
        )
        
        return context_text
