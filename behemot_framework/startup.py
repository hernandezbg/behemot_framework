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
                logger.error(f"Error al configurar webhook: {result.get("description")}")
        else:
            logger.error(f"Error HTTP {response.status_code} al configurar webhook: {response.text}")
    except Exception as e:
        logger.exception(f"Excepción al configurar webhook: {e}")
    
    return False

# ----- Funciones para RAG -----

async def ingest_folder_documents(folder: str, config: Dict[str, Any]) -> bool:
    """
    Ingiere documentos de una carpeta específica del bucket GCP.
    
    Args:
        folder: Nombre de la carpeta
        config: Configuración del sistema
        
    Returns:
        bool: True si se ingirieron documentos correctamente
    """
    try:
        import os
        # Importación dinámica para evitar dependencias innecesarias
        from behemot_framework.rag.rag_pipeline import RAGPipeline
        from behemot_framework.rag.document_loader import DocumentLoader
        from google.cloud import storage
        
        # Obtener el cliente de almacenamiento con manejo mejorado de credenciales
        try:
            # Primer intento: usar credenciales explícitas si están configuradas
            credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if credentials_path and os.path.exists(credentials_path):
                logger.info(f"Usando credenciales de GCP desde: {credentials_path}")
                storage_client = storage.Client.from_service_account_json(credentials_path)
            elif os.environ.get("GOOGLE_CREDENTIALS_JSON"):
                # Segundo intento: usar JSON en variable de entorno
                import json
                import tempfile
                
                logger.info("Usando credenciales de variable GOOGLE_CREDENTIALS_JSON")
                creds_json = json.loads(os.environ.get("GOOGLE_CREDENTIALS_JSON"))
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
                    json.dump(creds_json, temp_file)
                    temp_path = temp_file.name
                
                storage_client = storage.Client.from_service_account_json(temp_path)
                # Limpiar archivo temporal
                try:
                    os.unlink(temp_path)
                except:
                    pass
            elif os.environ.get("GS_PROJECT_ID") and os.environ.get("GS_PRIVATE_KEY"):
                # Tercer intento: reconstruir desde variables individuales
                from google.oauth2 import service_account
                
                logger.info("Usando credenciales reconstruidas desde variables GS_*")
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
                storage_client = storage.Client(credentials=credentials, project=credentials_dict["project_id"])
            else:
                # Último intento: Autenticación por defecto (ADC)
                logger.info("Intentando autenticación por defecto de GCP")
                storage_client = storage.Client()
                
            # Mostrar información del proyecto para verificar
            logger.info(f"Conectado a proyecto GCP: {storage_client.project}")
            
        except Exception as e:
            logger.error(f"Error en autenticación GCP: {e}")
            return False
        
        # Obtener la lista de archivos
        bucket_name = config.get("GCP_BUCKET_NAME")
        
        if not bucket_name:
            logger.error("No se especificó GCP_BUCKET_NAME en la configuración")
            return False
            
        # Asegurar que folder_name termina con '/'
        if folder and not folder.endswith('/'):
            folder += '/'
        
        logger.info(f"Buscando archivos en bucket {bucket_name}, carpeta '{folder}'")
        
        try:
            bucket = storage_client.bucket(bucket_name)
            
            # Verificar si el bucket existe
            if not bucket.exists():
                logger.error(f"El bucket {bucket_name} no existe o no tienes acceso")
                return False
                
            blobs = list(bucket.list_blobs(prefix=folder))
        except Exception as e:
            logger.error(f"Error al acceder al bucket {bucket_name}: {e}")
            return False
        
        # Filtrar solo archivos (no carpetas)
        files = [blob.name for blob in blobs if not blob.name.endswith('/')]
        
        if not files:
            logger.info(f"No hay documentos en la carpeta '{folder}'.")
            return False
        
        logger.info(f"Encontrados {len(files)} archivos en '{folder}'")
        
        # Obtener parámetros de configuración RAG
        embedding_provider = config.get("RAG_EMBEDDING_PROVIDER", "openai")
        embedding_model = config.get("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
        chunk_size = config.get("RAG_CHUNK_SIZE", 1000)
        chunk_overlap = config.get("RAG_CHUNK_OVERLAP", 200)
        splitter_type = config.get("RAG_SPLITTER_TYPE", "recursive")
        
        # Log de la configuración RAG
        logger.info(f"Configuración RAG: provider={embedding_provider}, model={embedding_model}")
        logger.info(f"Configuración chunks: size={chunk_size}, overlap={chunk_overlap}, splitter={splitter_type}")
        
        # Inicializar pipeline RAG para esta carpeta
        # Asegurar que el nombre de colección sea válido para Chroma (alfanumérico con _ y -)
        if folder:
            # Eliminar el '/' del final si existe
            clean_folder = folder[:-1] if folder.endswith('/') else folder
            # Reemplazar caracteres no permitidos
            collection_name = clean_folder.replace("/", "_").replace(" ", "_")
            # Asegurar que tenga al menos 3 caracteres y no termine con '_'
            if collection_name.endswith('_'):
                collection_name = collection_name[:-1]
            if len(collection_name) < 3:
                collection_name = collection_name + "_col"
        else:
            collection_name = "default_collection"

        logger.info(f"Usando nombre de colección: {collection_name}")
        
        persist_directory = config.get("RAG_PERSIST_DIRECTORY", f"chroma_db_{collection_name}")
        
        pipeline = RAGPipeline(
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            persist_directory=persist_directory,
            collection_name=collection_name
        )
        
        # Preparar rutas GCP para cada archivo
        gcp_paths = [f"gcp://{bucket_name}/{file}" for file in files]
        
        # Ingerir documentos
        logger.info(f"Ingiriendo {len(files)} documentos de '{folder}'...")
        
        await pipeline.aingest_documents(
            sources=gcp_paths,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            splitter_type=splitter_type
        )
        
        logger.info(f"Documentos de '{folder}' ingresados correctamente.")
        return True
        
    except Exception as e:
        logger.error(f"Error al ingerir documentos de '{folder}': {str(e)}", exc_info=True)
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
            logger.error(f"Error al ingerir documentos de '{folder}': {e}")
            results[folder] = False
    
    # Resumen de resultados
    succeeded = sum(1 for success in results.values() if success)
    logger.info(f"Ingestión completada: {succeeded}/{len(results)} carpetas procesadas correctamente")
    
    return results

# ----- Funciones generales de inicialización -----

def check_required_env_vars(vars_list: List[str]) -> List[str]:
    """
    Verifica que las variables de entorno requeridas estén definidas.
    
    Args:
        vars_list: Lista de nombres de variables a verificar
        
    Returns:
        List: Lista de variables que faltan
    """
    missing = []
    for var in vars_list:
        if not os.environ.get(var):
            missing.append(var)
    
    if missing:
        logger.warning(f"Faltan variables de entorno requeridas: {', '.join(missing)}")
    
    return missing

def setup_logging(level: str = "INFO") -> None:
    """
    Configura el sistema de logging.
    
    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configuración básica
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Silenciar loggers ruidosos
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    
    logger.info(f"Sistema de logging configurado en nivel {level}")


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
    


async def initialize_rag(config):
    """Inicializa RAG forzando la ingestión de documentos"""
    logger.info("Iniciando inicialización de RAG")
    
    # Verificar credenciales GCP
    if not check_gcp_credentials():
        logger.error("No se puede inicializar RAG: credenciales GCP incompletas")
        return False
    
    # Obtener carpetas a ingerir
    folders = config.get("RAG_FOLDERS", [])
    if isinstance(folders, str):
        folders = [f.strip() for f in folders.split(",") if f.strip()]
    
    logger.info(f"Carpetas a ingerir: {folders}")
    
    # Forzar reinicio/recreación de colecciones en entorno de producción
    if os.getenv("RAILWAY_ENVIRONMENT"):
        persist_directory = "chroma_db"  # Usar 'chroma_db' consistentemente
        
        for folder in folders:
            collection_name = folder.replace("/", "_") if folder else "default"
            try:
                # Eliminar colección si existe
                from behemot_framework.rag.vector_store import VectorStoreManager
                VectorStoreManager.delete_collection(persist_directory, collection_name)
                logger.info(f"Colección {collection_name} eliminada para reinicialización")
            except Exception as e:
                logger.warning(f"Error al eliminar colección: {e}")
    
    # Ingerir documentos
    results = await ingest_all_folders(folders, config)
    logger.info(f"Inicialización RAG completada: {results}")
    return results
