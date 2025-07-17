# app/startup.py
"""
Funciones de inicialización y configuración para el framework Behemot.
Este módulo contiene utilidades para inicializar diferentes componentes
durante el arranque de la aplicación.
"""

import logging
import requests
import asyncio
import os
import glob
from typing import List, Dict, Any, Optional
from fastapi import FastAPI
from google.cloud import storage



logger = logging.getLogger(__name__)

# ----- Funciones para Telegram -----

def set_telegram_webhook(token: str, webhook_url: str) -> bool:
    """
    Configura el webhook de Telegram.
    
    Args:
        token: Token de bot de Telegram
        webhook_url: URL del webhook a configurar
        
    Returns:
        bool: True si se configuró correctamente, False en caso contrario
    """
    if not webhook_url:
        logger.error("URL de webhook no proporcionada")
        return False
        
    url = f"https://api.telegram.org/bot{token}/setWebhook"
    params = {"url": webhook_url}
    
    try:
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.info(f"Webhook de Telegram configurado: {webhook_url}")
                return True
            else:
                logger.error(f"Error al configurar webhook: {result.get('description')}")
        else:
            logger.error(f"Error HTTP al configurar webhook: {response.status_code}")
    except Exception as e:
        logger.error(f"Excepción al configurar webhook: {e}")
    
    return False

# ----- Funciones para RAG -----

async def ingest_folder_documents(folder: str, config: Dict[str, Any]) -> bool:
    """
    Ingiere documentos de una carpeta específica (local o GCP bucket).
    
    Args:
        folder: Nombre de la carpeta (local o en GCP bucket)
        config: Configuración del sistema
        
    Returns:
        bool: True si se ingirieron documentos correctamente
    """
    try:
        # Determinar si usar almacenamiento local o GCP
        bucket_name = config.get("GCP_BUCKET_NAME", "")
        use_gcp = bool(bucket_name)
        
        if use_gcp:
            # Lógica para GCP
            return await _ingest_from_gcp(folder, config)
        else:
            # Lógica para almacenamiento local
            return await _ingest_from_local(folder, config)
            
    except Exception as e:
        logger.error(f"Error al ingerir documentos de carpeta '{folder}': {e}")
        return False


async def _ingest_from_local(folder: str, config: Dict[str, Any]) -> bool:
    """
    Ingiere documentos desde una carpeta local.
    """
    logger.info(f"📁 Procesando carpeta local: {folder}")
    
    # Verificar si la carpeta existe
    if not os.path.exists(folder):
        logger.error(f"❌ Carpeta no encontrada: {folder}")
        return False
    
    # Buscar archivos soportados
    supported_extensions = ['*.pdf', '*.txt', '*.md', '*.docx', '*.doc']
    files = []
    
    for ext in supported_extensions:
        pattern = os.path.join(folder, '**', ext)
        files.extend(glob.glob(pattern, recursive=True))
    
    if not files:
        logger.warning(f"⚠️ No se encontraron archivos en carpeta: {folder}")
        return False
    
    logger.info(f"📄 Encontrados {len(files)} archivos para procesar")
    
    # Procesar archivos
    try:
        from behemot_framework.rag.rag_manager import RAGManager
        
        # Usar RAGManager para obtener pipeline con configuración unificada
        collection_name = folder.replace("/", "_").replace("\\", "_")
        rag_pipeline = RAGManager.get_pipeline(collection_name)
        
        # Procesar todos los archivos de una vez usando el método aingest_documents
        try:
            logger.info(f"📄 Procesando {len(files)} archivos con pipeline RAG")
            
            # Usar rutas absolutas directamente (sin prefijo file://)
            local_paths = [os.path.abspath(file_path) for file_path in files]
            
            # Ingerir documentos y obtener el vectorstore resultante
            vectorstore = await rag_pipeline.aingest_documents(
                sources=local_paths,
                chunk_size=config.get("RAG_CHUNK_SIZE", 1000),
                chunk_overlap=config.get("RAG_CHUNK_OVERLAP", 200),
                splitter_type=config.get("RAG_SPLITTER_TYPE", "recursive")
            )
            
            # Verificar si realmente se indexaron documentos
            if vectorstore and hasattr(vectorstore, '_collection'):
                # Obtener el conteo real de documentos en el vectorstore
                try:
                    doc_count = vectorstore._collection.count()
                    if doc_count > 0:
                        processed_count = len(files)  # Archivos procesados exitosamente
                        logger.info(f"✅ Indexados {doc_count} chunks de {processed_count} archivos")
                    else:
                        processed_count = 0
                        logger.error(f"❌ Vectorstore creado pero sin documentos indexados")
                except Exception as count_error:
                    logger.warning(f"⚠️ No se pudo verificar conteo de documentos: {count_error}")
                    processed_count = 0
            else:
                processed_count = 0
                logger.error(f"❌ No se pudo crear el vectorstore")
            
        except Exception as e:
            logger.error(f"❌ Error en pipeline RAG: {e}")
            processed_count = 0
        
        logger.info(f"📊 Resultado final: {processed_count}/{len(files)} archivos procesados exitosamente")
        return processed_count > 0
        
    except Exception as e:
        logger.error(f"❌ Error en pipeline RAG: {e}")
        return False


async def _ingest_from_gcp(folder: str, config: Dict[str, Any]) -> bool:
    """
    Ingiere documentos desde GCP bucket (código original).
    """
    try:
        from behemot_framework.rag.rag_manager import RAGManager
        from behemot_framework.rag.document_loader import DocumentLoader
        
        # Verificar credenciales GCP
        if not check_gcp_credentials():
            logger.error("No se puede ingerir desde GCP: credenciales incompletas")
            return False
        
        # Usar RAGManager para obtener pipeline con configuración unificada
        collection_name = folder.replace("/", "_").replace("\\", "_")
        rag_pipeline = RAGManager.get_pipeline(collection_name)
        
        # Implementar lógica GCP completa
        from google.cloud import storage
        from google.oauth2 import service_account
        
        # Obtener cliente de storage
        storage_client = _get_gcp_storage_client()
        
        # Obtener bucket y archivos
        bucket_name = config.get("GCP_BUCKET_NAME")
        if not bucket_name:
            logger.error("No se especificó GCP_BUCKET_NAME en la configuración")
            return False
            
        # Asegurar que folder termina con '/'
        if folder and not folder.endswith('/'):
            folder += '/'
            
        logger.info(f"🔍 Buscando archivos en bucket {bucket_name}, carpeta '{folder}'")
        
        bucket = storage_client.bucket(bucket_name)
        if not bucket.exists():
            logger.error(f"❌ El bucket {bucket_name} no existe o no tienes acceso")
            return False
            
        blobs = list(bucket.list_blobs(prefix=folder))
        files = [blob.name for blob in blobs if not blob.name.endswith('/')]
        
        if not files:
            logger.info(f"⚠️ No hay documentos en la carpeta '{folder}'.")
            return False
            
        logger.info(f"📄 Encontrados {len(files)} archivos en '{folder}'")
        
        # Preparar rutas GCP para cada archivo
        gcp_paths = [f"gcp://{bucket_name}/{file}" for file in files]
        
        # Obtener configuración de chunks
        chunk_size = config.get("RAG_CHUNK_SIZE", 1000)
        chunk_overlap = config.get("RAG_CHUNK_OVERLAP", 200)
        splitter_type = config.get("RAG_SPLITTER_TYPE", "recursive")
        
        # Ingerir documentos usando el pipeline
        logger.info(f"📥 Ingiriendo {len(files)} documentos de '{folder}'...")
        
        await rag_pipeline.aingest_documents(
            sources=gcp_paths,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            splitter_type=splitter_type
        )
        
        logger.info(f"✅ Documentos de '{folder}' ingresados correctamente.")
        return True
        
    except Exception as e:
        logger.error(f"Error en ingesta GCP: {e}")
        return False


async def ingest_all_folders(folders: List[str], config: Dict[str, Any]) -> Dict[str, bool]:
    """
    Ingiere documentos de múltiples carpetas en paralelo.
    
    Args:
        folders: Lista de carpetas
        config: Configuración del sistema
        
    Returns:
        Dict: Resultados por carpeta
    """
    if not folders:
        logger.warning("No se especificaron carpetas para ingerir documentos")
        return {}
        
    results = {}
    tasks = []
    
    # Crear tareas para cada carpeta
    for folder in folders:
        if folder.strip():
            task = asyncio.create_task(ingest_folder_documents(folder.strip(), config))
            tasks.append((folder.strip(), task))
    
    # Esperar a que todas las tareas terminen
    for folder, task in tasks:
        try:
            success = await task
            results[folder] = success
        except Exception as e:
            logger.error(f"Error al procesar carpeta '{folder}': {e}")
            results[folder] = False
    
    # Mostrar resumen
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    logger.info(f"Ingestión completada: {successful}/{total} carpetas procesadas correctamente")
    
    return results


def check_gcp_credentials():
    """Verifica la configuración de credenciales GCP"""
    logger.info("Verificando credenciales GCP...")
    project_id = os.getenv("GS_PROJECT_ID")
    private_key = os.getenv("GS_PRIVATE_KEY")
    client_email = os.getenv("GS_CLIENT_EMAIL")
    
    if project_id and private_key and client_email:
        logger.info(f"Credenciales GCP encontradas para proyecto: {project_id}")
        logger.info(f"Client email: {client_email[:5]}...{client_email[-5:] if len(client_email) > 10 else ''}")
        private_key_preview = "Presente (longitud: " + str(len(private_key)) + ")"
        logger.info(f"Private key: {private_key_preview}")
        return True
    else:
        logger.error("Credenciales GCP incompletas")
        logger.error(f"Project ID presente: {project_id is not None}")
        logger.error(f"Private key presente: {private_key is not None}")
        logger.error(f"Client email presente: {client_email is not None}")
        return False


def _get_gcp_storage_client():
    """Obtiene el cliente de Google Cloud Storage con manejo de credenciales."""
    from google.cloud import storage
    from google.oauth2 import service_account
    
    # Intentar usando variables GS_* primero (como en DocumentLoader)
    if os.environ.get("GS_PROJECT_ID") and os.environ.get("GS_PRIVATE_KEY"):
        credentials_dict = {
            "type": os.environ.get("GS_ACCOUNT_TYPE", "service_account"),
            "project_id": os.environ.get("GS_PROJECT_ID"),
            "private_key_id": os.environ.get("GS_PRIVATE_KEY_ID", ""),
            "private_key": os.environ.get("GS_PRIVATE_KEY").replace("\\n", "\n"),
            "client_email": os.environ.get("GS_CLIENT_EMAIL", ""),
            "client_id": os.environ.get("GS_CLIENT_ID", ""),
            "auth_uri": os.environ.get("GS_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
            "token_uri": os.environ.get("GS_TOKEN_URI", "https://oauth2.googleapis.com/token"),
            "auth_provider_x509_cert_url": os.environ.get("GS_AUTH_PROVIDER_CERT_URL", 
                                            "https://www.googleapis.com/oauth2/v1/certs"),
            "client_x509_cert_url": os.environ.get("GS_CLIENT_CERT_URL", "")
        }
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        return storage.Client(credentials=credentials, project=credentials_dict["project_id"])
    
    # Fallback a archivo JSON si existe
    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_path and os.path.exists(credentials_path):
        return storage.Client.from_service_account_json(credentials_path)
    
    # Último recurso: ADC
    return storage.Client()
    

async def initialize_rag(config):
    """Inicializa RAG forzando la ingestión de documentos"""
    logger.info("Iniciando inicialización de RAG")
    
    # Verificar si se usa GCP o almacenamiento local
    bucket_name = config.get("GCP_BUCKET_NAME", "")
    use_gcp = bool(bucket_name)
    
    if use_gcp:
        # Solo verificar credenciales GCP si se va a usar
        if not check_gcp_credentials():
            logger.error("No se puede inicializar RAG: credenciales GCP incompletas")
            return False
        logger.info("🗃️ Usando almacenamiento GCP")
    else:
        logger.info("🗂️ Usando almacenamiento local (ChromaDB)")
        # No requerir credenciales GCP para almacenamiento local
    
    # Obtener carpetas a ingerir
    folders = config.get("RAG_FOLDERS", [])
    if isinstance(folders, str):
        folders = [f.strip() for f in folders.split(",") if f.strip()]
    
    logger.info(f"Carpetas a ingerir: {folders}")
    
    # Resetear singleton ChromaDB en entorno de producción para evitar conflictos
    if os.getenv("RAILWAY_ENVIRONMENT"):
        try:
            from behemot_framework.rag.vector_store import ChromaClientManager
            ChromaClientManager.reset_clients()
            logger.info("🔄 Singleton ChromaDB reseteado para reinicialización")
        except Exception as e:
            logger.warning(f"⚠️ Error reseteando singleton ChromaDB: {e}")
            
        # También resetear cache de pipelines RAG
        try:
            from behemot_framework.rag.rag_manager import RAGManager
            RAGManager.reset_pipelines()
            logger.info("🔄 Cache de pipelines RAG reseteado")
        except Exception as e:
            logger.warning(f"⚠️ Error reseteando pipelines RAG: {e}")
    
    # Ingerir documentos
    results = await ingest_all_folders(folders, config)
    logger.info(f"Inicialización RAG completada: {results}")
    return results