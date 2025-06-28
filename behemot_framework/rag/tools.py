# app/rag/tools.py
"""
Herramientas RAG genéricas integradas en el framework Behemot.
Estas herramientas están disponibles para todos los asistentes
que utilicen el framework.
"""

import logging
from behemot_framework.tooling import tool, Param
from behemot_framework.rag.rag_manager import RAGManager

logger = logging.getLogger(__name__)

@tool(name="search_documents", description="Busca información en documentos indexados", params=[
    Param(name="query", type_="string", description="La consulta para buscar en documentos", required=True),
    Param(name="folder", type_="string", description="Carpeta específica en el bucket", required=False),
    Param(name="k", type_="integer", description="Número de resultados a devolver", required=False)
])
async def search_documents(params: dict) -> str:
    """Busca información relevante en documentos indexados."""
    query = params.get("query", "")
    folder = params.get("folder", "")
    k = params.get("k", 4)
    
    logger.info("=" * 40)
    logger.info(f"🔍 RAG SEARCH_DOCUMENTS EJECUTADO")
    logger.info(f"  → Query: '{query}'")
    logger.info(f"  → Folder: '{folder}'")
    logger.info(f"  → K: {k}")
    logger.info("=" * 40)
    
    # Usar el gestor RAG para la búsqueda
    result = await RAGManager.query_documents(query, folder, k)
    
    if not result["success"]:
        logger.error(f"❌ Error en búsqueda RAG: {result['message']}")
        return result["message"]
    
    if not result["documents"]:
        logger.warning("⚠ No se encontraron documentos relevantes")
        return "No encontré información relevante en los documentos."
    
    logger.info(f"✅ Se encontraron {len(result['documents'])} documentos relevantes")
    return result["formatted_context"]

@tool(name="list_document_collections", description="Lista las colecciones de documentos disponibles", params=[])
async def list_document_collections(params: dict) -> str:
    """Lista las colecciones de documentos disponibles en el sistema."""
    try:
        import os
        import chromadb
        from behemot_framework.config import Config
        
        config = Config.get_config()
        persist_directory = config.get("RAG_PERSIST_DIRECTORY", "chroma_db")
        
        if not os.path.exists(persist_directory):
            return "No hay colecciones de documentos disponibles."
        
        # Listar colecciones disponibles
        try:
            client = chromadb.PersistentClient(path=persist_directory)
            collections = client.list_collections()
            
            if not collections:
                return "No hay colecciones de documentos disponibles."
            
            collection_names = [c.name for c in collections]
            
            response = "Colecciones de documentos disponibles:\n\n"
            for name in collection_names:
                response += f"- {name}\n"
            
            return response
        except Exception as e:
            logger.error(f"Error al listar colecciones: {e}")
            return f"Error al listar colecciones: {str(e)}"
    except Exception as e:
        logger.error(f"Error en list_document_collections: {str(e)}", exc_info=True)
        return f"Error al listar colecciones: {str(e)}"
