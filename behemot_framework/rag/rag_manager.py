# app/rag/rag_manager.py
import os
import logging
import chromadb
from typing import Dict, Any, Optional, List

from behemot_framework.rag.rag_pipeline import RAGPipeline

from behemot_framework.config import Config

logger = logging.getLogger(__name__)

class RAGManager:
    """
    Gestor centralizado para pipelines RAG.
    Proporciona acceso a pipelines RAG configurados para diferentes colecciones.
    """
    
    # Caché de pipelines RAG para reutilización
    _pipelines = {}
    
    @classmethod
    def get_pipeline(cls, folder_name: str = "", config_override: Optional[Dict[str, Any]] = None) -> RAGPipeline:
        """
        Obtiene o crea un pipeline RAG para una carpeta específica
        
        Args:
            folder_name: Nombre de la carpeta dentro del bucket
            config_override: Configuración específica que anula la configuración global
            
        Returns:
            RAGPipeline: Pipeline configurado
        """
        # Normalizar el nombre de la carpeta para usar como clave en el caché
        collection_name = folder_name.replace("/", "_") if folder_name else "default"
        
        # Verificar si ya existe un pipeline para esta colección
        cache_key = collection_name
        if cache_key in cls._pipelines:
            logger.debug(f"Usando pipeline en caché para '{collection_name}'")
            return cls._pipelines[cache_key]
        
        # Cargar configuración global
        config = Config.get_config()
        
        # Aplicar override si existe
        if config_override:
            for key, value in config_override.items():
                config[key] = value
        
        # Detectar si estamos en producción
        is_production = os.getenv("RAILWAY_ENVIRONMENT") is not None or os.getenv("PRODUCTION") is not None
        
        logger.info(f"Inicializando RAG pipeline para '{collection_name}' (Producción: {is_production})")
        
        # Obtener valores de configuración
        persist_directory = config.get("RAG_PERSIST_DIRECTORY", "chroma_db")
        embedding_provider = config.get("RAG_EMBEDDING_PROVIDER", "openai")
        embedding_model = config.get("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
        storage_type = config.get("RAG_STORAGE", "chroma")
        redis_url = config.get("REDIS_PUBLIC_URL") or config.get("REDIS_URL")
        
        logger.info(f"Usando directorio '{persist_directory}' con proveedor '{embedding_provider}' y modelo '{embedding_model}'")
        logger.info(f"Tipo de almacenamiento: {storage_type}")
        
        # Configuración específica para entorno de producción
        client_settings = None
        if is_production:
            client_settings = chromadb.config.Settings(
                chroma_db_impl=config.get("RAG_CHROMA_IMPL", "duckdb+parquet"),
                anonymized_telemetry=config.get("RAG_TELEMETRY_ENABLED", False)
            )
        
        # Crear pipeline con los ajustes correspondientes
        pipeline = RAGPipeline(
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            persist_directory=persist_directory,
            collection_name=collection_name,
            client_settings=client_settings,
            storage_type=storage_type,
            redis_url=redis_url
        )
        
        # Almacenar en caché para futuras solicitudes
        cls._pipelines[cache_key] = pipeline
        
        return pipeline
    
    @classmethod
    def reset_pipelines(cls):
        """Limpia el caché de pipelines RAG"""
        cls._pipelines = {}
        logger.info("Caché de pipelines RAG reiniciado")
    
    @classmethod
    async def query_documents(
        cls, 
        query: str, 
        folder_name: str = "", 
        k: int = 4,
        config_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Realiza una búsqueda en documentos usando RAG
        
        Args:
            query: Texto de la consulta
            folder_name: Carpeta específica a consultar
            k: Número de resultados a devolver
            config_override: Sobreescritura de configuraciones
            
        Returns:
            Dict: Resultado con documents, formatted_context y metadata
        """
        pipeline = cls.get_pipeline(folder_name, config_override)
        
        if pipeline.vectorstore is None:
            return {
                "success": False,
                "message": f"No hay documentos indexados para la carpeta '{folder_name}'",
                "documents": [],
                "formatted_context": ""
            }
        
        try:
            # Realizar la búsqueda
            documents = await pipeline.aquery_documents(query, k=k)
            
            if not documents:
                return {
                    "success": True,
                    "message": "No se encontraron documentos relevantes",
                    "documents": [],
                    "formatted_context": ""
                }
            
            # Preparar respuesta
            formatted_context = pipeline.get_formatted_context(query, k)
            
            return {
                "success": True,
                "message": f"Se encontraron {len(documents)} documentos relevantes",
                "documents": documents,
                "formatted_context": formatted_context,
                "count": len(documents)
            }
        except Exception as e:
            logger.error(f"Error en búsqueda de documentos: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Error al buscar documentos: {str(e)}",
                "documents": [],
                "formatted_context": "",
                "error": str(e)
            }
