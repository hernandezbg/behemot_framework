# behemot_framework/commandos/rag_commands.py
import logging
import os
import json
from typing import Dict, Any, List, Optional
from behemot_framework.commandos.command_handler import command
from behemot_framework.rag.rag_manager import RAGManager
from behemot_framework.config import Config

# Importar Google Cloud Storage solo si está disponible
try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False

logger = logging.getLogger(__name__)

def _is_gcs_url(path: str) -> bool:
    """Verifica si una ruta es una URL de Google Cloud Storage."""
    return path.startswith("gs://")

def _validate_gcs_url(gcs_url: str) -> bool:
    """
    Valida si una URL de GCS existe y es accesible.
    
    Args:
        gcs_url: URL en formato gs://bucket/path
        
    Returns:
        True si el archivo existe, False en caso contrario
    """
    if not GCS_AVAILABLE:
        logger.warning("Google Cloud Storage no está disponible. Instale google-cloud-storage")
        return False
        
    try:
        # Parsear la URL GCS
        if not gcs_url.startswith("gs://"):
            logger.error(f"URL no comienza con gs://: {gcs_url}")
            return False
            
        path_parts = gcs_url[5:].split("/", 1)  # Remover "gs://"
        if len(path_parts) != 2:
            logger.error(f"Formato de URL GCS inválido: {gcs_url}")
            return False
            
        bucket_name, blob_path = path_parts
        logger.info(f"Validando GCS: bucket='{bucket_name}', path='{blob_path}'")
        
        # Crear cliente de GCS
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        # Verificar si el blob existe
        exists = blob.exists()
        logger.info(f"GCS URL {gcs_url}: {'existe' if exists else 'no existe'}")
        return exists
        
    except Exception as e:
        logger.error(f"Error validando URL GCS {gcs_url}: {e}", exc_info=True)
        return False

def _validate_source(source: str) -> bool:
    """
    Valida si una fuente (local o GCS) existe y es accesible.
    
    Args:
        source: Ruta local o URL de GCS
        
    Returns:
        True si la fuente existe, False en caso contrario
    """
    if _is_gcs_url(source):
        return _validate_gcs_url(source)
    else:
        return os.path.exists(source)

@command(name="reindex_rag", description="Reindexar todos los documentos RAG de una colección")
async def reindex_rag_command(chat_id: str, collection: str = "default", sources: str = None, **kwargs) -> str:
    """
    Reindexar documentos en el sistema RAG.
    
    Args:
        chat_id: ID del usuario que ejecuta el comando
        collection: Nombre de la colección a reindexar (default: "default")
        sources: Rutas de documentos separadas por coma (opcional, usa config si no se especifica)
        
    Returns:
        str: Resultado de la reindexación
    """
    try:
        # Verificar permisos
        from behemot_framework.commandos.permissions import get_permission_manager
        
        perm_manager = get_permission_manager()
        user_platform = _get_user_platform(chat_id)
        
        if not perm_manager.has_permission(chat_id, "reindex_rag", user_platform):
            return "❌ **Acceso denegado**: No tienes permisos para reindexar documentos RAG.\n\nUsa `&whoami` para ver tus permisos actuales."
        
        logger.info(f"Iniciando reindexación RAG para colección '{collection}'")
        
        # Obtener configuración
        config = Config.get_config()
        
        # Verificar si RAG está habilitado
        if not config.get("ENABLE_RAG", False):
            return "❌ **Error**: El sistema RAG no está habilitado. Configura ENABLE_RAG=true en tu archivo de configuración."
        
        # Obtener pipeline RAG con directorio temporal para escritura
        config_override = {"RAG_PERSIST_DIRECTORY": "/tmp/chroma_db"}
        pipeline = RAGManager.get_pipeline(folder_name=collection, config_override=config_override)
        
        # Determinar fuentes de documentos
        if sources:
            # Usar fuentes especificadas por el usuario
            document_sources = [s.strip() for s in sources.split(",")]
        else:
            # Usar fuentes de la configuración
            document_sources = config.get("RAG_DOCUMENT_SOURCES", [])
            if not document_sources:
                return "❌ **Error**: No se especificaron documentos para indexar. Use el parámetro 'sources' o configure RAG_DOCUMENT_SOURCES."
        
        # Verificar que las fuentes existan (local o GCS)
        valid_sources = []
        invalid_sources = []
        gcs_sources_skipped = []
        
        for source in document_sources:
            if _is_gcs_url(source):
                # Para URLs de GCS, saltamos la validación y asumimos que existen
                # El DocumentLoader se encargará de manejar errores de acceso
                logger.info(f"URL GCS detectada, saltando validación: {source}")
                valid_sources.append(source)
                gcs_sources_skipped.append(source)
            else:
                # Para archivos locales, validar normalmente
                if _validate_source(source):
                    valid_sources.append(source)
                else:
                    invalid_sources.append(source)
        
        if not valid_sources:
            return f"❌ **Error**: Ninguna de las fuentes especificadas existe:\n" + "\n".join(f"• {s}" for s in invalid_sources)
        
        # Mostrar estado inicial
        result = f"🔄 **Reindexación RAG iniciada**\n\n"
        result += f"📁 **Colección**: `{collection}`\n"
        result += f"📚 **Documentos a procesar**: {len(valid_sources)}\n"
        
        # Mostrar tipos de fuentes
        local_sources = [s for s in valid_sources if not _is_gcs_url(s)]
        gcs_sources = [s for s in valid_sources if _is_gcs_url(s)]
        
        if local_sources:
            result += f"📂 **Archivos locales**: {len(local_sources)}\n"
        if gcs_sources:
            result += f"☁️ **Archivos GCS**: {len(gcs_sources)}\n"
        
        if invalid_sources:
            result += f"\n⚠️ **Fuentes no encontradas** ({len(invalid_sources)}):\n"
            for source in invalid_sources[:5]:  # Mostrar máximo 5
                result += f"• {source}\n"
            if len(invalid_sources) > 5:
                result += f"• ... y {len(invalid_sources) - 5} más\n"
        
        if gcs_sources_skipped:
            result += f"\n🔄 **URLs GCS sin validar** ({len(gcs_sources_skipped)}) - se intentará procesar:\n"
            for source in gcs_sources_skipped[:3]:  # Mostrar máximo 3
                result += f"• {source}\n"
        
        # Paso 1: Eliminar colección existente si existe
        try:
            if pipeline.vectorstore:
                pipeline.delete_collection()
                result += "\n✅ Colección anterior eliminada correctamente"
                logger.info(f"Colección '{collection}' eliminada")
                
                # También eliminar directorio físico para evitar carga automática
                import shutil
                persist_dir = pipeline.persist_directory
                if persist_dir and os.path.exists(persist_dir):
                    shutil.rmtree(persist_dir)
                    logger.info(f"Directorio {persist_dir} eliminado físicamente")
                    result += f"\n✅ Directorio {persist_dir} limpiado"
                    
        except Exception as e:
            logger.warning(f"No se pudo eliminar la colección anterior: {e}")
            result += f"\n⚠️ No se pudo eliminar la colección anterior: {str(e)}"
        
        # Reinicializar el pipeline para asegurar estado limpio
        logger.info(f"Reiniciando cache de pipelines RAG")
        RAGManager.reset_pipelines()
        
        # Obtener nuevo pipeline limpio con directorio temporal
        pipeline = RAGManager.get_pipeline(folder_name=collection, config_override=config_override)
        logger.info(f"Nuevo pipeline obtenido para colección '{collection}' en directorio temporal")
        
        # Asegurar que el vectorstore esté limpio después de la eliminación
        pipeline.vectorstore = None
        logger.info("Vectorstore configurado a None para forzar creación nueva")
        
        # Paso 2: Ingerir documentos
        result += f"\n\n📥 **Procesando documentos**:\n"
        
        # Obtener configuración de chunking
        chunk_size = config.get("RAG_CHUNK_SIZE", 1000)
        chunk_overlap = config.get("RAG_CHUNK_OVERLAP", 200)
        splitter_type = config.get("RAG_SPLITTER_TYPE", "recursive")
        
        try:
            # Ingerir todos los documentos
            vectorstore = await pipeline.aingest_documents(
                sources=valid_sources,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                splitter_type=splitter_type
            )
            
            result += f"\n✅ **Reindexación completada exitosamente**\n"
            result += f"• Documentos procesados: {len(valid_sources)}\n"
            result += f"• Tamaño de chunks: {chunk_size}\n"
            result += f"• Superposición: {chunk_overlap}\n"
            result += f"• Tipo de divisor: {splitter_type}\n"
            
            # Hacer una búsqueda de prueba
            test_query = "test"
            test_results = await pipeline.aquery_documents(test_query, k=1)
            if test_results:
                result += f"\n🔍 **Verificación**: El índice responde correctamente a consultas"
            
            logger.info(f"Reindexación completada para colección '{collection}'")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error durante la ingestión: {error_msg}", exc_info=True)
            result += f"\n❌ **Error durante la ingestión**: {error_msg}\n"
            result += "\nVerifique que:\n"
            result += "• Los archivos tengan contenido válido\n"
            result += "• Las API keys estén configuradas correctamente\n"
            result += "• El directorio de persistencia tenga permisos de escritura\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error en comando reindex_rag: {str(e)}", exc_info=True)
        return f"❌ **Error al reindexar RAG**: {str(e)}"

@command(name="rag_status", description="Muestra el estado actual del sistema RAG")
async def rag_status_command(chat_id: str, collection: str = None, **kwargs) -> str:
    """
    Muestra información detallada sobre el estado del sistema RAG.
    
    Args:
        chat_id: ID del usuario que ejecuta el comando
        collection: Colección específica a consultar (opcional)
        
    Returns:
        str: Estado del sistema RAG
    """
    try:
        # No requiere permisos especiales - información de solo lectura
        from behemot_framework.commandos.system_status import check_rag
        
        logger.info(f"Consultando estado RAG desde {chat_id}")
        
        # Obtener estado general del RAG
        rag_status = await check_rag()
        
        result = "📚 **Estado del Sistema RAG**\n\n"
        
        # Estado general
        result += f"🔹 **Estado**: {rag_status['status']}\n"
        result += f"🔹 **Habilitado**: {'Sí' if rag_status['enabled'] else 'No'}\n"
        
        if not rag_status['enabled']:
            result += "\n⚠️ El sistema RAG no está habilitado. Configura ENABLE_RAG=true para activarlo."
            return result
        
        # Configuración
        result += f"\n📋 **Configuración**:\n"
        result += f"• **Proveedor de embeddings**: {rag_status['embedding_provider']}\n"
        result += f"• **Modelo de embeddings**: {rag_status['embedding_model']}\n"
        
        # Colecciones
        if rag_status.get('collections'):
            result += f"\n📁 **Colecciones** ({len(rag_status['collections'])}):\n"
            
            for col in rag_status['collections']:
                status_icon = "✅" if col.get('initialized') else "❌"
                result += f"\n{status_icon} **{col['name']}**\n"
                
                if col.get('initialized'):
                    # Si se especificó una colección y coincide, mostrar más detalles
                    if collection and col['name'] == collection:
                        try:
                            pipeline = RAGManager.get_pipeline(folder_name=collection)
                            if pipeline.vectorstore:
                                # Hacer una consulta de prueba para verificar funcionamiento
                                test_docs = await pipeline.aquery_documents("test", k=1)
                                result += f"  • Estado: Operativo\n"
                                result += f"  • Responde a consultas: {'Sí' if test_docs else 'Verificando...'}\n"
                        except Exception as e:
                            result += f"  • Error al obtener detalles: {str(e)}\n"
                else:
                    result += f"  • Estado: No inicializada\n"
                    if col.get('error'):
                        result += f"  • Error: {col['error']}\n"
        else:
            result += "\n📁 No hay colecciones registradas"
        
        # Información adicional si se especificó una colección
        if collection:
            result += f"\n\n💡 Para reindexar la colección '{collection}', usa:\n"
            result += f"`&reindex_rag collection=\"{collection}\"`"
        else:
            result += "\n\n💡 **Comandos disponibles**:\n"
            result += "• `&reindex_rag` - Reindexar documentos\n"
            result += "• `&rag_search` - Buscar en documentos\n"
            result += "• `&rag_collections` - Listar todas las colecciones"
        
        return result
        
    except Exception as e:
        logger.error(f"Error en comando rag_status: {str(e)}", exc_info=True)
        return f"❌ **Error al obtener estado RAG**: {str(e)}"

@command(name="rag_search", description="Buscar información en los documentos RAG")
async def rag_search_command(chat_id: str, query: str = None, collection: str = "default", k: str = "4", **kwargs) -> str:
    """
    Busca información en los documentos indexados del sistema RAG.
    
    Args:
        chat_id: ID del usuario que ejecuta el comando
        query: Consulta de búsqueda
        collection: Colección donde buscar (default: "default")
        k: Número de resultados a devolver (default: 4)
        
    Returns:
        str: Resultados de la búsqueda
    """
    try:
        if not query:
            return "❌ **Error**: Debes proporcionar una consulta.\n\nUso: `&rag_search query=\"tu búsqueda\" collection=\"nombre\"`"
        
        # Convertir k a entero
        try:
            k_int = int(k)
            k_int = max(1, min(k_int, 10))  # Entre 1 y 10 resultados
        except ValueError:
            k_int = 4
        
        logger.info(f"Búsqueda RAG: '{query}' en colección '{collection}' (k={k_int})")
        
        # Realizar búsqueda
        search_results = await RAGManager.query_documents(
            query=query,
            folder_name=collection,
            k=k_int
        )
        
        if not search_results["success"]:
            return f"❌ **Error en búsqueda**: {search_results['message']}"
        
        if not search_results["documents"]:
            return f"📭 No se encontraron resultados para: \"{query}\"\n\nColección: {collection}"
        
        # Formatear resultados
        result = f"🔍 **Resultados de búsqueda RAG**\n\n"
        result += f"📝 **Consulta**: \"{query}\"\n"
        result += f"📁 **Colección**: {collection}\n"
        result += f"📊 **Resultados encontrados**: {search_results['count']}\n\n"
        
        # Mostrar cada documento encontrado
        for i, doc in enumerate(search_results["documents"], 1):
            result += f"**Resultado {i}**:\n"
            
            # Contenido (truncar si es muy largo)
            content = doc.page_content
            if len(content) > 300:
                content = content[:297] + "..."
            result += f"```\n{content}\n```\n"
            
            # Metadata
            if doc.metadata:
                source = doc.metadata.get("source", "Desconocido")
                result += f"📄 **Fuente**: {os.path.basename(source)}\n"
                
                if "page" in doc.metadata:
                    result += f"📄 **Página**: {doc.metadata['page']}\n"
                elif "chunk" in doc.metadata:
                    result += f"🔢 **Chunk**: {doc.metadata['chunk']}\n"
            
            result += "\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error en comando rag_search: {str(e)}", exc_info=True)
        return f"❌ **Error al buscar en RAG**: {str(e)}"

@command(name="rag_collections", description="Lista todas las colecciones RAG disponibles")
async def rag_collections_command(chat_id: str, **kwargs) -> str:
    """
    Lista todas las colecciones RAG disponibles y su estado.
    
    Args:
        chat_id: ID del usuario que ejecuta el comando
        
    Returns:
        str: Lista de colecciones
    """
    try:
        logger.info(f"Listando colecciones RAG para {chat_id}")
        
        # Obtener configuración
        config = Config.get_config()
        
        if not config.get("ENABLE_RAG", False):
            return "❌ El sistema RAG no está habilitado. Configura ENABLE_RAG=true para activarlo."
        
        # Obtener información de colecciones desde el estado del sistema
        from behemot_framework.commandos.system_status import check_rag
        rag_status = await check_rag()
        
        result = "📚 **Colecciones RAG Disponibles**\n\n"
        
        if not rag_status.get('collections'):
            result += "📭 No hay colecciones configuradas.\n\n"
            result += "Para crear una nueva colección, usa:\n"
            result += "`&reindex_rag collection=\"nombre_coleccion\" sources=\"ruta/archivo.pdf\"`"
            return result
        
        # Listar colecciones
        total_collections = len(rag_status['collections'])
        initialized = sum(1 for c in rag_status['collections'] if c.get('initialized'))
        
        result += f"📊 **Total**: {total_collections} colecciones\n"
        result += f"✅ **Inicializadas**: {initialized}\n"
        result += f"❌ **No inicializadas**: {total_collections - initialized}\n\n"
        
        # Detalles de cada colección
        for col in rag_status['collections']:
            status_icon = "✅" if col.get('initialized') else "❌"
            result += f"{status_icon} **{col['name']}**\n"
            
            if col.get('initialized'):
                result += f"   • Estado: Activa\n"
                # Intentar obtener más información
                try:
                    pipeline = RAGManager.get_pipeline(folder_name=col['name'])
                    if pipeline.persist_directory:
                        result += f"   • Directorio: {pipeline.persist_directory}\n"
                except:
                    pass
            else:
                result += f"   • Estado: No inicializada\n"
                if col.get('error'):
                    result += f"   • Error: {col['error']}\n"
            
            result += "\n"
        
        # Comandos útiles
        result += "💡 **Comandos útiles**:\n"
        result += "• `&rag_search query=\"búsqueda\" collection=\"nombre\"` - Buscar en una colección\n"
        result += "• `&reindex_rag collection=\"nombre\"` - Reindexar una colección\n"
        result += "• `&rag_status collection=\"nombre\"` - Ver detalles de una colección"
        
        return result
        
    except Exception as e:
        logger.error(f"Error en comando rag_collections: {str(e)}", exc_info=True)
        return f"❌ **Error al listar colecciones RAG**: {str(e)}"

def _get_user_platform(chat_id: str) -> str:
    """
    Detecta la plataforma de un usuario basándose en su registro.
    
    Args:
        chat_id: ID del usuario
        
    Returns:
        Plataforma del usuario o "any" si no se encuentra
    """
    try:
        from behemot_framework.users import get_user_tracker
        user_tracker = get_user_tracker()
        
        for platform in ["telegram", "whatsapp", "api", "google_chat"]:
            users = user_tracker.get_users_by_platform(platform, 365)
            for user in users:
                if user["user_id"] == chat_id:
                    return platform
        return "any"
    except Exception:
        return "any"