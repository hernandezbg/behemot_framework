# app\rag\document_loader.py

"""
Módulo para cargar documentos de diferentes fuentes.
Soporta archivos PDF, texto plano, URLs, buckets S3, Google Drive, etc.
"""
import os
import tempfile
from typing import List, Dict, Any, Union, Optional
import logging

# Importaciones básicas de LangChain
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    CSVLoader,
    WebBaseLoader,
    DirectoryLoader,
    S3FileLoader,
    GoogleDriveLoader,
)
from langchain_core.documents import Document
from langchain_community.document_loaders import UnstructuredMarkdownLoader
# Para Google Drive
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account

# Para S3
import boto3
from botocore.exceptions import ClientError

# Para GCP
from google.cloud import storage

 

logger = logging.getLogger(__name__)


class DocumentLoader:
    """Clase para cargar documentos desde diferentes fuentes"""

    @staticmethod
    def load_text(file_path: str) -> List[Document]:
        """Carga un archivo de texto"""
        logger.info(f"Cargando texto desde {file_path}")
        loader = TextLoader(file_path)
        docs = loader.load()
        
        # Agregar metadata de filename
        filename = os.path.basename(file_path)
        for doc in docs:
            if not doc.metadata:
                doc.metadata = {}
            doc.metadata['filename'] = filename
            
        return docs

    @staticmethod
    def load_pdf(file_path: str) -> List[Document]:
        """Carga un archivo PDF"""
        logger.info(f"Cargando PDF desde {file_path}")
        loader = PyPDFLoader(file_path)
        docs = loader.load()
        
        # Agregar metadata de filename para mejor trazabilidad
        filename = os.path.basename(file_path)
        for doc in docs:
            if not doc.metadata:
                doc.metadata = {}
            doc.metadata['filename'] = filename
            
        return docs
    
    @staticmethod
    def load_markdown(file_path: str) -> List[Document]:
        """Carga un archivo Markdown"""
        logger.info(f"Cargando Markdown desde {file_path}")
        loader = UnstructuredMarkdownLoader(file_path)
        docs = loader.load()
        
        # Agregar metadata de filename
        filename = os.path.basename(file_path)
        for doc in docs:
            if not doc.metadata:
                doc.metadata = {}
            doc.metadata['filename'] = filename
            
        return docs

    @staticmethod
    def load_csv(file_path: str, csv_args: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Carga un archivo CSV"""
        logger.info(f"Cargando CSV desde {file_path}")
        loader = CSVLoader(file_path, csv_args=csv_args or {})
        docs = loader.load()
        
        # Agregar metadata de filename
        filename = os.path.basename(file_path)
        for doc in docs:
            if not doc.metadata:
                doc.metadata = {}
            doc.metadata['filename'] = filename
            
        return docs

    @staticmethod
    def load_url(url: str) -> List[Document]:
        """Carga contenido desde una URL"""
        logger.info(f"Cargando contenido desde URL: {url}")
        loader = WebBaseLoader(url)
        return loader.load()

    @staticmethod
    def load_directory(dir_path: str, glob_pattern: str = "**/*") -> List[Document]:
        """Carga todos los documentos en un directorio que coinciden con el patrón glob"""
        logger.info(f"Cargando documentos desde directorio: {dir_path}")
        loader = DirectoryLoader(dir_path, glob=glob_pattern)
        return loader.load()

    @staticmethod
    def load_s3(bucket_name: str, key: str) -> List[Document]:
        """
        Carga un documento desde un bucket S3
        
        Args:
            bucket_name: Nombre del bucket
            key: Ruta al archivo dentro del bucket
            
        Returns:
            Lista de documentos cargados desde S3
        """
        logger.info(f"Cargando documento desde S3: {bucket_name}/{key}")
        
        # Método 1: Usando S3FileLoader de LangChain si está disponible para el tipo de archivo
        try:
            loader = S3FileLoader(bucket_name, key)
            return loader.load()
        except Exception as e:
            logger.warning(f"Error al usar S3FileLoader: {e}, intentando método alternativo")
        
        # Método 2: Descarga manual a archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(key)[1]) as temp_file:
            temp_path = temp_file.name
        
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
                region_name=os.environ.get('AWS_REGION', 'us-east-1')
            )
            
            s3_client.download_file(bucket_name, key, temp_path)
            
            # Determinar el tipo de archivo y cargarlo
            return DocumentLoader.load_document(temp_path)
        except ClientError as e:
            logger.error(f"Error al descargar archivo de S3: {e}")
            raise
        finally:
            # Eliminar archivo temporal
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @staticmethod
    def load_gcp_bucket(bucket_name: str, blob_name: str) -> List[Document]:
        """
        Carga un documento desde un bucket de Google Cloud Storage.

        Args:
            bucket_name: Nombre del bucket.
            blob_name: Nombre del blob/archivo a cargar.

        Returns:
            Lista de documentos cargados.
        """
        logger.info(f"Cargando documento desde GCP: {bucket_name}/{blob_name}")

        try:
            # Crear un archivo temporal con la extensión correcta
            _, ext = os.path.splitext(blob_name)
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                temp_path = temp_file.name

            # Log para diagnóstico
            logger.info(f"Credenciales GCP (archivo): {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
            logger.info(f"Temp path: {temp_path}")

            # Intentar usar variables de entorno GS_* para reconstruir las credenciales
            if os.environ.get("GS_PROJECT_ID") and os.environ.get("GS_PRIVATE_KEY"):
                from google.oauth2 import service_account
                credentials_dict = {
                    "type": os.environ.get("GS_ACCOUNT_TYPE", "service_account"),
                    "project_id": os.environ.get("GS_PROJECT_ID"),
                    "private_key_id": os.environ.get("GS_PRIVATE_KEY_ID", ""),
                    "private_key": os.environ.get("GS_PRIVATE_KEY").replace("\\n", "\n"),
                    "client_email": os.environ.get("GS_CLIENT_EMAIL", ""),
                    "client_id": os.environ.get("GS_CLIENT_ID", ""),
                    "auth_uri": os.environ.get("GS_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
                    "token_uri": os.environ.get("GS_TOKEN_URI", "https://oauth2.googleapis.com/token"),
                    "auth_provider_x509_cert_url": os.environ.get("GS_AUTH_PROVIDER_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs"),
                    "client_x509_cert_url": os.environ.get("GS_CLIENT_CERT_URL", "")
                }
                credentials = service_account.Credentials.from_service_account_info(credentials_dict)
                storage_client = storage.Client(credentials=credentials, project=credentials_dict["project_id"])
                logger.info("Usando credenciales reconstruidas desde variables GS_*")
            else:
                # Fallback a intentar usar un archivo JSON definido en GOOGLE_APPLICATION_CREDENTIALS
                credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
                if credentials_path and os.path.exists(credentials_path):
                    storage_client = storage.Client.from_service_account_json(credentials_path)
                    logger.info(f"Usando credenciales desde el archivo: {credentials_path}")
                else:
                    # Último recurso: autenticación por defecto (Application Default Credentials)
                    logger.info("Usando autenticación por defecto de GCP")
                    storage_client = storage.Client()

            # Acceder al bucket y listar los blobs para diagnóstico
            bucket = storage_client.bucket(bucket_name)
            logger.info(f"Conectado al bucket: {bucket.name}")

            directory = os.path.dirname(blob_name)
            blobs = list(bucket.list_blobs(prefix=directory))
            logger.info(f"Blobs en el directorio: {[b.name for b in blobs]}")

            # Obtener el blob específico y verificar su existencia
            blob = bucket.blob(blob_name)
            if not blob.exists():
                logger.error(f"El blob {blob_name} no existe en el bucket {bucket_name}")
                raise FileNotFoundError(f"El archivo {blob_name} no existe en el bucket {bucket_name}")

            # Descargar el blob al archivo temporal
            logger.info(f"Descargando blob: {blob.name} a {temp_path}")
            blob.download_to_filename(temp_path)

            # Cargar el documento a partir del archivo temporal usando el DocumentLoader
            loaded_docs = DocumentLoader.load_document(temp_path)
            logger.info(f"Documento cargado exitosamente: {len(loaded_docs)} partes")
            return loaded_docs

        except Exception as e:
            logger.error(f"Error al cargar archivo de GCP: {e}", exc_info=True)
            raise

        finally:
            # Limpiar y eliminar el archivo temporal
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)

    @staticmethod
    def load_google_drive(file_id: str, credentials_path: Optional[str] = None) -> List[Document]:
        """
        Carga un documento desde Google Drive
        
        Args:
            file_id: ID del archivo en Google Drive
            credentials_path: Ruta al archivo de credenciales (service account)
            
        Returns:
            Lista de documentos cargados desde Google Drive
        """
        logger.info(f"Cargando documento desde Google Drive: {file_id}")
        
        # Método 1: Usando GoogleDriveLoader de LangChain
        credentials_path = credentials_path or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        
        if not credentials_path and os.environ.get('GOOGLE_CREDENTIALS_JSON'):
            # Si las credenciales están en una variable de entorno como JSON
            import json
            import tempfile
            
            creds_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS_JSON'))
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
                json.dump(creds_json, temp_file)
                credentials_path = temp_file.name
        
        try:
            loader = GoogleDriveLoader(
                folder_id=None,  # No estamos cargando una carpeta
                document_ids=[file_id],
                credentials_path=credentials_path,
            )
            return loader.load()
        except Exception as e:
            logger.warning(f"Error al usar GoogleDriveLoader: {e}, intentando método alternativo")
        
        # Método 2: Implementación manual con API de Google Drive
        try:
            # Autenticar con Google Drive API
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
            drive_service = build('drive', 'v3', credentials=credentials)
            
            # Obtener metadatos del archivo
            file_metadata = drive_service.files().get(fileId=file_id, fields='name,mimeType').execute()
            file_name = file_metadata.get('name', 'downloaded_file')
            
            # Crear archivo temporal con la extensión correcta
            _, extension = os.path.splitext(file_name)
            if not extension:
                # Intentar inferir extensión desde mimeType
                mime_type = file_metadata.get('mimeType', '')
                if 'pdf' in mime_type:
                    extension = '.pdf'
                elif 'spreadsheet' in mime_type:
                    extension = '.csv'
                else:
                    extension = '.txt'
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
                temp_path = temp_file.name
            
            # Descargar archivo
            request = drive_service.files().get_media(fileId=file_id)
            
            with io.FileIO(temp_path, 'wb') as file:
                downloader = MediaIoBaseDownload(file, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            
            # Cargar documento según su tipo
            return DocumentLoader.load_document(temp_path)
        except Exception as e:
            logger.error(f"Error al cargar archivo de Google Drive: {e}")
            raise
        finally:
            # Limpiar archivos temporales si existen
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
            if 'credentials_path' in locals() and credentials_path != os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') and os.path.exists(credentials_path):
                os.unlink(credentials_path)

    @classmethod
    def load_document(cls, source: str) -> List[Document]:
        """
        Carga un documento desde una fuente detectando automáticamente el tipo
        
        Args:
            source: Ruta al archivo, URL, o URI especial
            
        Returns:
            Lista de documentos cargados
        """
        # Detectar el tipo de fuente
        if source.startswith(("http://", "https://")):
            return cls.load_url(source)
        
        # Patrones especiales para GCP (soporta tanto gcp:// como gs://)
        elif source.startswith(("gcp://", "gs://")):
            if source.startswith("gcp://"):
                parts = source[6:].split('/', 1)
            else:  # gs://
                parts = source[5:].split('/', 1)
                
            if len(parts) != 2:
                logger.error(f"Formato GCS inválido: {source}")
                raise ValueError(f"Formato GCS inválido. Debe ser gs://bucket/key o gcp://bucket/key: {source}")
            bucket, key = parts
            logger.info(f"Parseo de ruta GCS: bucket={bucket}, key={key}")
            return cls.load_gcp_bucket(bucket, key)
        
        # Patrones especiales para S3
        elif source.startswith("s3://"):
            parts = source[5:].split('/', 1)
            if len(parts) != 2:
                raise ValueError(f"Formato S3 inválido. Debe ser s3://bucket/key: {source}")
            bucket, key = parts
            return cls.load_s3(bucket, key)
        
        # Patrón para Google Drive
        elif source.startswith("gdrive://"):
            file_id = source[9:]
            return cls.load_google_drive(file_id)
        
        # Archivo local
        elif os.path.exists(source):
            if os.path.isdir(source):
                return cls.load_directory(source)
                
            ext = os.path.splitext(source)[1].lower()
            if ext == ".pdf":
                return cls.load_pdf(source)
            elif ext == ".csv":
                return cls.load_csv(source)
            elif ext in [".md", ".markdown"]:
                return cls.load_markdown(source)
            else:
                # Por defecto, intenta cargar como texto
                return cls.load_text(source)
        else:
            raise FileNotFoundError(f"El archivo o recurso no existe o no es accesible: {source}")

    @classmethod
    async def aload_document(cls, source: str) -> List[Document]:
        """Versión asíncrona de load_document para uso con conectores async"""
        # Para funciones que no son naturalmente async, usamos el mismo método
        # dentro de un executor para no bloquear
        import asyncio
        return await asyncio.to_thread(cls.load_document, source)
