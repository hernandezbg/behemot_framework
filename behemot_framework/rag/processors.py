# app\rag\processors.py
"""
Módulo para procesar documentos y dividirlos en chunks
"""
from typing import List, Dict, Any, Optional
import logging

from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
    CharacterTextSplitter,
)
from langchain.docstore.document import Document


logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Clase para procesar y dividir documentos en chunks"""

    @staticmethod
    def split_documents_by_tokens(
        documents: List[Document],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        model_name: str = "gpt-3.5-turbo",
    ) -> List[Document]:
        """
        Divide documentos en chunks basados en tokens
        
        Args:
            documents: Lista de documentos a dividir
            chunk_size: Tamaño máximo de cada chunk en tokens
            chunk_overlap: Superposición entre chunks en tokens
            model_name: Nombre del modelo para tokenización
            
        Returns:
            Lista de documentos divididos
        """
        logger.info(f"Dividiendo {len(documents)} documentos por tokens")
        text_splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            model_name=model_name,
        )
        return text_splitter.split_documents(documents)

    @staticmethod
    def split_documents_recursive(
        documents: List[Document],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
    ) -> List[Document]:
        """
        Divide documentos usando separadores recursivos
        
        Args:
            documents: Lista de documentos a dividir
            chunk_size: Tamaño máximo de cada chunk en caracteres
            chunk_overlap: Superposición entre chunks en caracteres
            separators: Lista de separadores a usar (por defecto: ["\n\n", "\n", " ", ""])
            
        Returns:
            Lista de documentos divididos
        """
        logger.info(f"Dividiendo {len(documents)} documentos recursivamente")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators or ["\n\n", "\n", " ", ""],
        )
        return text_splitter.split_documents(documents)

    @staticmethod
    def split_documents_by_character(
        documents: List[Document],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separator: str = "\n",
    ) -> List[Document]:
        """
        Divide documentos usando un separador específico
        
        Args:
            documents: Lista de documentos a dividir
            chunk_size: Tamaño máximo de cada chunk en caracteres
            chunk_overlap: Superposición entre chunks en caracteres
            separator: Separador a usar para dividir el texto
            
        Returns:
            Lista de documentos divididos
        """
        logger.info(f"Dividiendo {len(documents)} documentos por caracter con separador: '{separator}'")
        text_splitter = CharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separator=separator,
        )
        return text_splitter.split_documents(documents)

    @classmethod
    def process_documents(
        cls,
        documents: List[Document],
        splitter_type: str = "recursive",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        **kwargs,
    ) -> List[Document]:
        """
        Procesa y divide documentos usando el método especificado
        """
        if not documents:
            logger.warning("No se proporcionaron documentos para procesar")
            return []
            
        logger.info(f"Procesando {len(documents)} documentos con método: {splitter_type}")
        
        if splitter_type == "token":
            return cls.split_documents_by_tokens(
                documents, chunk_size, chunk_overlap, **kwargs
            )
        elif splitter_type == "recursive":
            # Extraer separators de kwargs si existe, sino pasa None
            separators = kwargs.get("separators", None)
            return cls.split_documents_recursive(
                documents, chunk_size, chunk_overlap, separators
            )
        elif splitter_type == "character":
            separator = kwargs.get("separator", "\n")
            return cls.split_documents_by_character(
                documents, chunk_size, chunk_overlap, separator
            )
        else:
            logger.warning(f"Tipo de divisor desconocido: {splitter_type}, usando recursive")
            return cls.split_documents_recursive(documents, chunk_size, chunk_overlap)
