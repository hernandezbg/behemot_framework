# app\rag\vector_store.py

"""
Módulo para gestionar bases de datos vectoriales con Chroma
"""
from typing import List, Dict, Any, Optional, Union
import logging
import os
import time
import hashlib
import tempfile
from pathlib import Path
import platform

# Importar fcntl solo en sistemas Unix/Linux
if platform.system() != 'Windows':
    import fcntl
else:
    fcntl = None

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings


logger = logging.getLogger(__name__)


# Intentar importar la versión nueva de Chroma primero
try:
    from langchain_chroma import Chroma
except ImportError:
    # Fallback a la versión legacy en langchain-community si está disponible.
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            from langchain_community.vectorstores import Chroma
    except ImportError:
        Chroma = None  # type: ignore[assignment]
        logger.debug("Chroma no disponible (ni langchain-chroma ni langchain-community).")

# Importar Redis vector store (opcional)
try:
    from langchain_community.vectorstores import Redis as RedisVectorStore
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.debug("Redis vector store no disponible. Instala langchain-community para usar Redis.")


class ChromaClientManager:
    """Manager para gestionar clientes ChromaDB y evitar conflictos entre procesos"""
    
    _clients = {}  # Cache de clientes por configuración
    
    @classmethod
    def get_client(cls, persist_directory: str = None, client_settings: Optional[Any] = None):
        """Obtiene o crea un cliente ChromaDB reutilizable con protección multiproceso"""
        import chromadb
        from chromadb.config import Settings
        
        # Crear clave única para el cliente
        key = f"{persist_directory}_{hash(str(client_settings))}"
        
        # Verificar si ya tenemos el cliente en memoria
        if key in cls._clients:
            return cls._clients[key]
        
        # File lock para evitar conflictos entre procesos worker
        lock_file_path = None
        lock_file = None
        
        try:
            if persist_directory:
                # Usar file locking para persistencia solo en sistemas Unix/Linux
                if fcntl is not None:
                    lock_file_path = Path(tempfile.gettempdir()) / f"chroma_lock_{hashlib.md5(persist_directory.encode()).hexdigest()}.lock"
                    lock_file = open(lock_file_path, 'w')
                    
                    # Intentar obtener el lock con timeout
                    timeout = 30  # 30 segundos timeout
                    start_time = time.time()
                    while True:
                        try:
                            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                            break
                        except IOError:
                            if time.time() - start_time > timeout:
                                logger.error(f"❌ Timeout obteniendo lock para ChromaDB: {persist_directory}")
                                raise TimeoutError(f"No se pudo obtener lock para ChromaDB después de {timeout}s")
                            time.sleep(0.1)
                            
                    logger.info(f"🔒 Lock obtenido para ChromaDB: {persist_directory}")
                else:
                    # En Windows: lock por creación atómica (O_CREAT|O_EXCL).
                    # `Path.touch()` y `exists()` no eran atómicos: dos procesos
                    # podían encontrar el lock libre y crearlo a la vez,
                    # corrompiendo el directorio Chroma.
                    lock_file_path = Path(persist_directory) / ".chroma_lock"
                    max_attempts = 300  # 30s con polling cada 0.1s
                    attempts = 0
                    acquired = False
                    while attempts < max_attempts:
                        try:
                            fd = os.open(
                                str(lock_file_path),
                                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                            )
                            os.close(fd)
                            acquired = True
                            break
                        except FileExistsError:
                            time.sleep(0.1)
                            attempts += 1

                    if not acquired:
                        logger.warning(
                            f"⚠️ No se pudo adquirir lock atómico para ChromaDB tras "
                            f"{max_attempts * 0.1:.0f}s: {lock_file_path}. "
                            "Otro proceso puede estar usándolo o el lock quedó huérfano."
                        )
                    else:
                        logger.info(
                            f"🔒 Lock atómico obtenido para ChromaDB (Windows): {lock_file_path}"
                        )
            
            logger.info(f"📦 Creando nuevo cliente ChromaDB para: {persist_directory}")
            
            if client_settings is None:
                # Usar la nueva configuración de ChromaDB
                client_settings = Settings(
                    anonymized_telemetry=False
                )
            
            if persist_directory:
                # Asegurar que el directorio existe
                os.makedirs(persist_directory, exist_ok=True)
                
                client = chromadb.PersistentClient(
                    path=persist_directory,
                    settings=client_settings
                )
            else:
                client = chromadb.Client(settings=client_settings)
            
            cls._clients[key] = client
            logger.info(f"✅ Cliente ChromaDB creado exitosamente")
            
            return client
            
        except Exception as e:
            logger.error(f"❌ Error creando cliente ChromaDB: {e}")
            raise
        finally:
            # Liberar el lock
            if lock_file:
                try:
                    if fcntl is not None:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                        lock_file.close()
                        logger.info(f"🔓 Lock liberado para ChromaDB")
                    else:
                        # En Windows, eliminar archivo de bloqueo
                        lock_file.close()
                        if lock_file_path and lock_file_path.exists():
                            lock_file_path.unlink()
                            logger.info(f"🔓 Lock file eliminado para ChromaDB (Windows): {lock_file_path}")
                except Exception as e:
                    logger.warning(f"⚠️ Error liberando lock: {e}")
    
    @classmethod
    def reset_clients(cls):
        """Reinicia todos los clientes (útil para testing)"""
        logger.info("🔄 Reiniciando cache de clientes ChromaDB")
        cls._clients = {}


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
        
        # Usar el singleton para obtener el cliente
        client = ChromaClientManager.get_client(persist_directory, client_settings)
        
        # Crear instancia de Chroma con el cliente reutilizable
        try:
            vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=embeddings,
                collection_name=collection_name,
                client=client
            )
        except Exception as e:
            # Si falla por problemas de base de datos, intentar con cliente en memoria
            error_str = str(e)
            if ("readonly database" in error_str or 
                "unable to open database file" in error_str or 
                "code: 14" in error_str or 
                "code: 1032" in error_str):
                logger.warning(f"Error de base de datos en ChromaDB, usando cliente en memoria: {e}")
                # Crear cliente en memoria sin persistencia
                memory_client = ChromaClientManager.get_client(persist_directory=None, client_settings=client_settings)
                vectorstore = Chroma.from_documents(
                    documents=documents,
                    embedding=embeddings,
                    collection_name=collection_name,
                    client=memory_client
                )
                logger.info("✅ Índice Chroma creado en memoria exitosamente")
            else:
                raise
        
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
            # Usar el singleton para obtener el cliente
            client = ChromaClientManager.get_client(persist_directory, client_settings)

            # Crear argumentos para Chroma con el cliente reutilizable
            chroma_args = {
                "embedding_function": embeddings,
                "collection_name": collection_name,
                "client": client
            }
            
            # Crear instancia de Chroma con el cliente reutilizable
            logger.info("Usando langchain_chroma.Chroma")
            vectorstore = Chroma(
                embedding_function=embeddings,
                collection_name=collection_name,
                client=client
            )
            
            return vectorstore
                
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

        logger.info("Documentos añadidos al índice Chroma")
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
        logger.info(f"Eliminando colección '{collection_name}' en {persist_directory}")
        
        # Usar el singleton para obtener el cliente
        client = ChromaClientManager.get_client(persist_directory)
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
