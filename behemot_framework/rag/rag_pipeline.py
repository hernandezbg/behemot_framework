# app\rag\rag_pipeline.py

"""
Módulo principal para el pipeline RAG completo con Chroma
"""
from typing import List, Dict, Any, Optional, Union, Tuple
import logging
import os
import asyncio

from langchain.docstore.document import Document
from langchain.schema.embeddings import Embeddings
from langchain.schema.retriever import BaseRetriever
from langchain_community.vectorstores import Chroma
from langchain_core.language_models import BaseLanguageModel

from behemot_framework.rag.document_loader import DocumentLoader
from behemot_framework.rag.processors import DocumentProcessor
from behemot_framework.rag.embeddings import EmbeddingManager
from behemot_framework.rag.vector_store import VectorStoreManager
from behemot_framework.rag.retriever import RAGRetriever


logger = logging.getLogger(__name__)


class RAGPipeline:
    """Clase principal para gestionar el pipeline RAG completo"""
    
    def __init__(
        self,
        embedding_provider: str = "openai",
        embedding_model: str = "text-embedding-3-small",
        persist_directory: str = "chroma_db",
        collection_name: str = "default_collection",
        client_settings: Optional[Any] = None,
        storage_type: str = "chroma",
        redis_url: Optional[str] = None,
    ):
        """
        Inicializa el pipeline RAG
        
        Args:
            embedding_provider: Proveedor de embeddings ('openai', 'huggingface', 'google')
            embedding_model: Modelo de embeddings a usar
            persist_directory: Directorio para persistencia de Chroma
            collection_name: Nombre de la colección
            client_settings: Configuración opcional del cliente Chroma
            storage_type: Tipo de almacenamiento ('chroma' o 'redis')
            redis_url: URL de conexión a Redis (requerido si storage_type='redis')
        """
        self.embedding_provider = embedding_provider
        self.embedding_model = embedding_model
        self.persist_directory = persist_directory
        self.storage_type = storage_type
        self.redis_url = redis_url
        self.collection_name = collection_name
        self.client_settings = client_settings
        
        # Preparar parámetros según el proveedor
        embedding_params = {"provider": embedding_provider}
        
        if embedding_provider == "openai":
            embedding_params["model"] = embedding_model
        elif embedding_provider == "huggingface":
            embedding_params["model_name"] = embedding_model
        elif embedding_provider in ["google", "gemini"]:
            embedding_params["model"] = embedding_model
            
        self.embeddings = EmbeddingManager.get_embeddings(**embedding_params)
        
        self.vectorstore = None
        
        # Inicializar vectorstore según el tipo
        if self.storage_type == "redis":
            if self.redis_url:
                try:
                    self.vectorstore = VectorStoreManager.load_redis_index(
                        self.embeddings, 
                        self.redis_url,
                        collection_name
                    )
                    logger.info(f"Colección Redis '{collection_name}' cargada correctamente")
                except Exception as e:
                    logger.error(f"Error al cargar la colección Redis: {e}")
                    # Continuar sin vectorstore, se creará cuando sea necesario
            else:
                logger.warning("Redis URL no configurada, no se puede cargar el índice")
        else:  # chroma (default)
            if os.path.exists(persist_directory):
                try:
                    self.vectorstore = VectorStoreManager.load_chroma_index(
                        self.embeddings, 
                        persist_directory, 
                        collection_name,
                        client_settings=client_settings
                    )
                    logger.info(f"Colección '{collection_name}' cargada correctamente desde {persist_directory}")
                except Exception as e:
                    logger.error(f"Error al cargar la colección: {e}")
    
    def ingest_documents(
        self,
        sources: Union[str, List[str]],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        splitter_type: str = "recursive",
    ) -> Chroma:
        """
        Ingiere documentos en el pipeline RAG
        
        Args:
            sources: Ruta(s) al documento o documentos
            chunk_size: Tamaño de los chunks
            chunk_overlap: Superposición entre chunks
            splitter_type: Tipo de divisor ('token', 'recursive', 'character')
            
        Returns:
            Vectorstore Chroma con los documentos ingeridos
        """
        logger.info(f"Iniciando ingestión de documentos desde {sources}")
        
        # Asegurar que sources sea una lista
        if isinstance(sources, str):
            sources = [sources]
        
        # Cargar documentos
        all_documents = []
        for source in sources:
            try:
                docs = DocumentLoader.load_document(source)
                all_documents.extend(docs)
                logger.info(f"Cargados {len(docs)} documentos desde {source}")
            except Exception as e:
                logger.error(f"Error al cargar {source}: {e}")
        
        if not all_documents:
            logger.warning("No se pudieron cargar documentos")
            if self.vectorstore:
                return self.vectorstore
            else:
                # Crear un vectorstore vacío
                return Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embeddings,
                    collection_name=self.collection_name,
                )
        
        # Procesar y dividir documentos
        chunks = DocumentProcessor.process_documents(
            all_documents,
            splitter_type=splitter_type,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        
        logger.info(f"Documentos procesados en {len(chunks)} chunks")
        
        # Crear o actualizar vectorstore según el tipo
        if self.storage_type == "redis":
            if self.vectorstore is None:
                self.vectorstore = VectorStoreManager.create_redis_index(
                    chunks, 
                    self.embeddings, 
                    self.redis_url,
                    self.collection_name
                )
            else:
                self.vectorstore = VectorStoreManager.add_documents_to_redis(
                    self.vectorstore, chunks
                )
        else:  # chroma (default)
            if self.vectorstore is None:
                self.vectorstore = VectorStoreManager.create_chroma_index(
                    chunks, 
                    self.embeddings, 
                    self.persist_directory,
                    self.collection_name
                )
            else:
                self.vectorstore = VectorStoreManager.add_documents(
                    self.vectorstore, chunks
                )
        
        return self.vectorstore
    
    async def aingest_documents(
        self,
        sources: Union[str, List[str]],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        splitter_type: str = "recursive",
    ) -> Chroma:
        """
        Versión asíncrona de ingest_documents
        """
        # Esta es una implementación sencilla que ejecuta la versión síncrona
        # En una implementación más avanzada, cada parte sería realmente asíncrona
        return await asyncio.to_thread(
            self.ingest_documents,
            sources,
            chunk_size,
            chunk_overlap,
            splitter_type,
        )
    
    def get_retriever(
        self,
        search_type: str = "similarity",
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> BaseRetriever:
        """
        Obtiene un retriever para el vectorstore actual
        
        Args:
            search_type: Tipo de búsqueda ('similarity', 'mmr')
            search_kwargs: Parámetros adicionales para la búsqueda
            
        Returns:
            Retriever configurado
        """
        if self.vectorstore is None:
            raise ValueError("No hay vectorstore inicializado, ingiere documentos primero")
            
        return RAGRetriever.get_vectorstore_retriever(
            self.vectorstore,
            search_type=search_type,
            search_kwargs=search_kwargs,
        )
    
    def get_compression_retriever(
        self,
        llm: BaseLanguageModel,
        search_type: str = "similarity",
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> BaseRetriever:
        """
        Obtiene un retriever con compresión para el vectorstore actual
        
        Args:
            llm: Modelo de lenguaje para la compresión
            search_type: Tipo de búsqueda ('similarity', 'mmr')
            search_kwargs: Parámetros adicionales para la búsqueda
            
        Returns:
            Retriever con compresión configurado
        """
        base_retriever = self.get_retriever(search_type, search_kwargs)
        
        return RAGRetriever.get_compression_retriever(base_retriever, llm)
    
    def query_documents(
        self,
        query: str,
        k: int = 4,
        retriever: Optional[BaseRetriever] = None,
    ) -> List[Document]:
        """
        Consulta documentos usando el vectorstore o un retriever específico
        
        Args:
            query: Consulta para la búsqueda
            k: Número de resultados a devolver
            retriever: Retriever opcional (si None, usa búsqueda directa)
            
        Returns:
            Lista de documentos relevantes
        """
        if retriever:
            return RAGRetriever.retrieve_documents(retriever, query)
        
        if self.vectorstore is None:
            raise ValueError("No hay vectorstore inicializado, ingiere documentos primero")
            
        return VectorStoreManager.similarity_search(self.vectorstore, query, k=k)
    
    async def aquery_documents(
        self,
        query: str,
        k: int = 4,
        retriever: Optional[BaseRetriever] = None,
    ) -> List[Document]:
        """
        Consulta documentos de forma asíncrona
        
        Args:
            query: Consulta para la búsqueda
            k: Número de resultados a devolver
            retriever: Retriever opcional (si None, usa búsqueda directa)
            
        Returns:
            Lista de documentos relevantes
        """
        if retriever:
            return await RAGRetriever.aretrieve_documents(retriever, query)
        
        # Para búsqueda directa, ejecutamos la versión síncrona en un thread
        return await asyncio.to_thread(self.query_documents, query, k)
    
    def get_formatted_context(self, query: str, k: int = 4) -> str:
        """
        Obtiene contexto formateado para una consulta
        
        Args:
            query: Consulta para la búsqueda
            k: Número de resultados a devolver
            
        Returns:
            Texto formateado con los documentos relevantes
        """
        docs = self.query_documents(query, k)
        return RAGRetriever.format_retrieved_documents(docs)
    
    def delete_collection() -> None:
        """
        Elimina la colección actual
        """
        VectorStoreManager.delete_collection(self.persist_directory, self.collection_name)
        self.vectorstore = None
