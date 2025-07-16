# app\rag\vector_store.py

"""
Módulo para gestionar bases de datos vectoriales con Chroma
"""
from typing import List, Dict, Any, Optional, Union
import logging
import os

from langchain.docstore.document import Document
from langchain.schema.embeddings import Embeddings

# Intentar importar la versión nueva de Chroma primero
try:
    from langchain_chroma import Chroma
except ImportError:
    # Si no está disponible, usar la versión legacy con warning suprimido
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        from langchain_community.vectorstores import Chroma

# Importar Redis vector store
try:
    from langchain_community.vectorstores import Redis as RedisVectorStore
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis vector store no disponible. Instale redis-py para usar Redis como almacenamiento de vectores.")


logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Clase para gestionar bases de datos vectoriales con Chroma"""

    @staticmethod
    def create_chroma_index(
        documents: List[Document],
        embeddings: Embeddings,
        persist_directory: Optional[str] = None,
        collection_name: str = "default_collection",
        client_settings: Optional[Any] = None,
    ) -> Chroma:
        """
        Crea un índice Chroma a partir de documentos
        
        Args:
            documents: Lista de documentos a indexar
            embeddings: Modelo de embeddings a usar
            persist_directory: Directorio para persistencia (None para en memoria)
            collection_name: Nombre de la colección
            client_settings: Configuración opcional del cliente Chroma
            
        Returns:
            Instancia de Chroma con los documentos indexados
        """
        logger.info(f"Creando índice Chroma con {len(documents)} documentos en colección '{collection_name}'")
        
        import chromadb
        from chromadb.config import Settings

        # Crear cliente con la nueva configuración recomendada
        # Deshabilitar telemetría anónima
        if client_settings is None:
            client_settings = Settings(anonymized_telemetry=False)

        if persist_directory:
            client = chromadb.PersistentClient(
                path=persist_directory,
                settings=client_settings
            )
        else:
            client = chromadb.Client(settings=client_settings)
        
        # Crear instancia de Chroma con el nuevo cliente
        vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            collection_name=collection_name,
            client=client
        )
        
        logger.info(f"Índice Chroma creado exitosamente para colección '{collection_name}'")
        return vectorstore

    @staticmethod
    def load_chroma_index(
        embeddings: Embeddings, 
        persist_directory: str,
        collection_name: str = "default_collection",
        client_settings: Optional[Any] = None,
    ) -> Chroma:
        """
        Carga un índice Chroma desde disco
        
        Args:
            embeddings: Modelo de embeddings a usar
            persist_directory: Directorio donde está persistido
            collection_name: Nombre de la colección
            client_settings: Configuración opcional del cliente Chroma
            
        Returns:
            Instancia de Chroma cargada
        """
        logger.info(f"Cargando índice Chroma desde {persist_directory}, colección '{collection_name}'")
        
        if not os.path.exists(persist_directory):
            raise FileNotFoundError(f"No se encontró directorio de persistencia en {persist_directory}")
        
        try:
            # Usar la forma recomendada para crear el cliente Chroma
            import chromadb
            from chromadb.config import Settings

            # Deshabilitar telemetría anónima
            if client_settings is None:
                client_settings = Settings(anonymized_telemetry=False)

            # Crear argumentos para Chroma
            chroma_args = {
                "persist_directory": persist_directory,
                "embedding_function": embeddings,
                "collection_name": collection_name,
                "client_settings": client_settings
            }
            
            # Importar directamente de langchain_chroma si está disponible
            try:
                from langchain_chroma import Chroma as ChromaNew
                logger.info("Usando langchain_chroma.Chroma")
                return ChromaNew(**chroma_args)
            except ImportError:
                # Fallback a la versión anterior
                logger.info("Usando langchain_community.vectorstores.Chroma")
                from langchain_community.vectorstores import Chroma
                return Chroma(**chroma_args)
                
        except Exception as e:
            logger.error(f"Error al cargar Chroma: {e}")
            raise

    @staticmethod
    def add_documents(
        vectorstore: Chroma,
        documents: List[Document],
    ) -> Chroma:
        """
        Añade documentos a un índice existente
        
        Args:
            vectorstore: Índice Chroma existente
            documents: Nuevos documentos a añadir
            
        Returns:
            Instancia de Chroma actualizada
        """
        logger.info(f"Añadiendo {len(documents)} documentos al índice Chroma")
        
        vectorstore.add_documents(documents)
        
        # Persistir si hay directorio de persistencia configurado
        if vectorstore._persist_directory:
            logger.info(f"Índice Chroma actualizado persistido en {vectorstore._persist_directory}")
            
        return vectorstore

    @staticmethod
    def similarity_search(
        vectorstore: Chroma,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Realiza una búsqueda por similitud
        
        Args:
            vectorstore: Índice Chroma
            query: Consulta para la búsqueda
            k: Número de resultados a devolver
            filter: Filtros adicionales
            
        Returns:
            Lista de documentos similares
        """
        logger.info(f"Realizando búsqueda por similitud: {query}")
        
        return vectorstore.similarity_search(query, k=k, filter=filter)

    @staticmethod
    def similarity_search_with_score(
        vectorstore: Chroma,
        query: str,
        k: int = 4,
    ) -> List[tuple[Document, float]]:
        """
        Realiza una búsqueda por similitud con puntuación
        
        Args:
            vectorstore: Índice Chroma
            query: Consulta para la búsqueda
            k: Número de resultados a devolver
            
        Returns:
            Lista de tuplas (documento, puntuación)
        """
        logger.info(f"Realizando búsqueda por similitud con puntuación: {query}")
        
        return vectorstore.similarity_search_with_score(query, k=k)
        
    @staticmethod
    def delete_collection(
        persist_directory: str,
        collection_name: str = "default_collection",
    ) -> None:
        """
        Elimina una colección existente
        
        Args:
            persist_directory: Directorio donde está persistido
            collection_name: Nombre de la colección a eliminar
        """
        import chromadb
        
        logger.info(f"Eliminando colección '{collection_name}' en {persist_directory}")
        
        client = chromadb.PersistentClient(path=persist_directory)
        try:
            client.delete_collection(name=collection_name)
            logger.info(f"Colección '{collection_name}' eliminada correctamente")
        except ValueError as e:
            logger.warning(f"No se pudo eliminar la colección: {e}")

    # Métodos para Redis Vector Store
    @staticmethod
    def create_redis_index(
        documents: List[Document],
        embeddings: Embeddings,
        redis_url: str,
        index_name: str = "default_index",
        **kwargs
    ) -> 'RedisVectorStore':
        """
        Crea un índice Redis a partir de documentos
        
        Args:
            documents: Lista de documentos a indexar
            embeddings: Modelo de embeddings a usar
            redis_url: URL de conexión a Redis
            index_name: Nombre del índice
            **kwargs: Argumentos adicionales para Redis
            
        Returns:
            Instancia de RedisVectorStore con los documentos indexados
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis vector store no disponible. Instale redis-py")
            
        logger.info(f"Creando índice Redis '{index_name}' con {len(documents)} documentos")
        
        try:
            # Crear índice Redis desde documentos
            vectorstore = RedisVectorStore.from_documents(
                documents=documents,
                embedding=embeddings,
                redis_url=redis_url,
                index_name=index_name,
                **kwargs
            )
            
            logger.info(f"Índice Redis '{index_name}' creado exitosamente")
            return vectorstore
            
        except Exception as e:
            logger.error(f"Error al crear índice Redis: {e}")
            raise

    @staticmethod
    def load_redis_index(
        embeddings: Embeddings,
        redis_url: str,
        index_name: str = "default_index",
        **kwargs
    ) -> 'RedisVectorStore':
        """
        Carga un índice Redis existente
        
        Args:
            embeddings: Modelo de embeddings a usar
            redis_url: URL de conexión a Redis
            index_name: Nombre del índice
            **kwargs: Argumentos adicionales para Redis
            
        Returns:
            Instancia de RedisVectorStore
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis vector store no disponible. Instale redis-py")
            
        logger.info(f"Cargando índice Redis '{index_name}'")
        
        try:
            vectorstore = RedisVectorStore(
                redis_url=redis_url,
                index_name=index_name,
                embedding=embeddings,
                **kwargs
            )
            
            logger.info(f"Índice Redis '{index_name}' cargado exitosamente")
            return vectorstore
            
        except Exception as e:
            logger.error(f"Error al cargar índice Redis: {e}")
            raise

    @staticmethod
    def add_documents_to_redis(
        vectorstore: 'RedisVectorStore',
        documents: List[Document]
    ) -> 'RedisVectorStore':
        """
        Añade documentos a un índice Redis existente
        
        Args:
            vectorstore: Índice Redis existente
            documents: Nuevos documentos a añadir
            
        Returns:
            Instancia de RedisVectorStore actualizada
        """
        logger.info(f"Añadiendo {len(documents)} documentos al índice Redis")
        
        vectorstore.add_documents(documents)
        logger.info("Documentos añadidos al índice Redis exitosamente")
        
        return vectorstore
