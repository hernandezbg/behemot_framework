# app/assistants/assistant.py
import json
import logging
import re
from behemot_framework.context import get_conversation, save_conversation
from behemot_framework.tooling import get_tool_definitions, call_tool
from behemot_framework.security.langchain_safety import LangChainSafetyFilter
from behemot_framework.config import Config
from behemot_framework.commandos.command_handler import CommandHandler
from behemot_framework.core.middleware.date_middleware import DateMiddleware


logger = logging.getLogger(__name__)

class Assistant:
    def __init__(self, modelo, prompt_sistema: str, safety_level: str = "medium"):
        self.modelo = modelo
        self.prompt_sistema = prompt_sistema
        
        # Determinar el proveedor del modelo
        model_provider = Config.get("MODEL_PROVIDER", "openai").lower()
        
        # Solo inicializar el filtro de seguridad si estamos usando OpenAI
        if model_provider in ["openai", "gpt"]:
            api_key = Config.get("GPT_API_KEY")
            if api_key:
                self.safety_filter = LangChainSafetyFilter(api_key=api_key, safety_level=safety_level)
            else:
                logger.warning("GPT_API_KEY no configurada. Filtro de seguridad desactivado.")
                self.safety_filter = None
        else:
            # Para otros proveedores, no usar el filtro de OpenAI
            logger.info(f"Filtro de seguridad desactivado para proveedor: {model_provider}")
            self.safety_filter = None
        
        # Configuración AUTO_RAG
        self.auto_rag_enabled = Config.get("AUTO_RAG", False) and Config.get("ENABLE_RAG", False)
        if self.auto_rag_enabled:
            logger.info("🤖 AUTO_RAG activado - El asistente enriquecerá automáticamente las respuestas con documentos")
            self.rag_max_results = Config.get("RAG_MAX_RESULTS", 3)
            self.rag_similarity_threshold = Config.get("RAG_SIMILARITY_THRESHOLD", 0.6)

    async def generar_respuesta(self, chat_id: str, mensaje_usuario: str) -> str:

        # Verificar si es un comando especial
        if mensaje_usuario.strip().startswith("&"):
            # Procesar como comando y retornar la respuesta
            return await CommandHandler.process_command(chat_id, mensaje_usuario)
        

        # Aplicar filtro al mensaje del usuario solo si está disponible
        if self.safety_filter:
            safety_result = await self.safety_filter.filter_content(mensaje_usuario)
            
            if not safety_result["is_safe"]:
                logger.warning(f"Mensaje de usuario filtrado - Chat {chat_id}: {safety_result['reason']}")
                mensaje_usuario = safety_result["filtered_content"]

        # Recupera el historial de la conversación
        conversation = get_conversation(chat_id)
        if not conversation:
            conversation.append({"role": "system", "content": self.prompt_sistema})

        # Inyectar fecha actual en el mensaje del sistema
        conversation = DateMiddleware.inject_current_date(conversation)

        conversation.append({"role": "user", "content": mensaje_usuario})
        
        # AUTO_RAG: Enriquecer automáticamente con contexto de documentos
        if self.auto_rag_enabled:
            logger.info(f"🔍 AUTO_RAG: Buscando documentos relevantes para: '{mensaje_usuario[:50]}...'")
            try:
                from behemot_framework.rag.rag_manager import RAGManager
                
                # Obtener todas las carpetas configuradas para RAG
                rag_folders = Config.get("RAG_FOLDERS", ["docs"])
                logger.info(f"🗂️ AUTO_RAG: Buscando en carpetas: {rag_folders}")
                
                # Buscar en todas las carpetas configuradas
                all_documents = []
                successful_searches = 0
                
                for folder in rag_folders:
                    try:
                        logger.info(f"📁 AUTO_RAG: Buscando en carpeta '{folder}'")
                        folder_result = await RAGManager.query_documents(
                            query=mensaje_usuario,
                            folder_name=folder,
                            k=self.rag_max_results
                        )
                        
                        if folder_result["success"] and folder_result["documents"]:
                            folder_docs = folder_result["documents"]
                            all_documents.extend(folder_docs)
                            successful_searches += 1
                            logger.info(f"✅ AUTO_RAG: Encontrados {len(folder_docs)} documentos en '{folder}'")
                        else:
                            logger.info(f"ℹ️ AUTO_RAG: No se encontraron documentos en carpeta '{folder}'")
                            
                    except Exception as folder_error:
                        logger.warning(f"⚠️ AUTO_RAG: Error buscando en carpeta '{folder}': {folder_error}")
                        continue
                
                # Procesar resultados combinados
                if all_documents:
                    # Ordenar por score (similitud) y tomar los mejores
                    def get_score(doc):
                        if hasattr(doc, 'metadata') and isinstance(doc.metadata, dict):
                            return doc.metadata.get("score", 0)
                        elif isinstance(doc, dict):
                            return doc.get("score", 0)
                        else:
                            return 0
                    
                    best_documents = sorted(
                        all_documents, 
                        key=get_score, 
                        reverse=True
                    )[:self.rag_max_results]
                    
                    # Crear contexto combinado
                    context_parts = []
                    for i, doc in enumerate(best_documents, 1):
                        # Manejar diferentes tipos de objetos de documento
                        if hasattr(doc, 'page_content'):
                            content = doc.page_content
                            # Extraer información de página de metadata
                            page_info = ""
                            if hasattr(doc, 'metadata') and doc.metadata:
                                page = doc.metadata.get('page')
                                source = doc.metadata.get('source', '')
                                if page is not None:
                                    page_info = f" (Página {page + 1})"  # +1 porque páginas empiezan en 0
                                elif source:
                                    page_info = f" (Fuente: {source})"
                        elif hasattr(doc, 'content'):
                            content = doc.content
                            page_info = ""
                        elif isinstance(doc, dict):
                            content = doc.get("content", str(doc))
                            page_info = f" (Página {doc.get('page', 'N/A')})" if 'page' in doc else ""
                        else:
                            content = str(doc)
                            page_info = ""
                        
                        context_parts.append(f"Documento {i}{page_info}:\n{content}")
                    
                    context_message = f"Información relevante de documentos:\n\n" + "\n\n---\n\n".join(context_parts)
                    conversation.append({"role": "system", "content": context_message})
                    
                    logger.info(f"📚 AUTO_RAG: {len(best_documents)} documentos relevantes de {successful_searches} carpetas")
                    logger.info(f"✅ AUTO_RAG: Contexto agregado al historial de conversación")
                else:
                    logger.info("ℹ️ AUTO_RAG: No se encontraron documentos relevantes en ninguna carpeta")
                    
            except Exception as e:
                logger.error(f"❌ AUTO_RAG Error: {e}")
                # Continuar sin RAG si hay error
        
        # Obtén las definiciones de las funciones registradas
        functions = get_tool_definitions()
        
        # Debug: Mostrar herramientas disponibles
        logger.info(f"🔧 Herramientas disponibles para el assistant: {[f['name'] for f in functions]}")

        try:
            response = self.modelo.generar_respuesta_con_functions(conversation, functions)
        except Exception as e:
            return f"Error al generar respuesta: {str(e)}"

        choice = response.choices[0]
        
        # Si hay un mensaje, lo procesamos primero
        if choice.message and choice.message.content:
            answer = choice.message.content.strip()
            
            # Si es un mensaje que indica búsqueda, ejecutamos la función inmediatamente
            search_keywords = ["buscaré", "procederé a buscar", "buscar", "momento", "buscando"]
            if any(keyword in answer.lower() for keyword in search_keywords):
                # Extraer la consulta del mensaje con patrones más amplios
                query = None
                patterns = [
                    r"buscar[ée]\s+(?:información)?\s+(?:de|sobre)?\s+(.*?)(?:\.||" ")",
                    r"buscar[ée]\s+(.*?)(?:\.||" ")",
                    r"(?:de|para|en)\s+(.*?)(?:\.||" ")"
                ]
                
                for pattern in patterns:
                    search_terms = re.search(pattern, answer, re.IGNORECASE)
                    if search_terms:
                        query = search_terms.group(1).strip()
                        break
                
                # Si no se puede extraer la consulta, usar el mensaje original del usuario
                if not query:
                    query = mensaje_usuario
                
                logger.info(f"Consulta extraída para búsqueda automática: {query}")
                
                # Guardar la respuesta intermedia
                conversation.append({"role": "assistant", "content": answer})
                save_conversation(chat_id, conversation)
                
                # Determinar qué herramienta usar para la búsqueda
                default_tool = None
                default_tool_args = {"query": query}
                
                # Obtener la primera herramienta de búsqueda disponible
                for tool in functions:
                    tool_name = tool.get("name", "")
                    tool_desc = tool.get("description", "").lower()
                    
                    # Buscar herramientas de búsqueda o consulta entre las disponibles
                    if ("search" in tool_name.lower() or "buscar" in tool_name.lower() or 
                        "query" in tool_name.lower() or "consult" in tool_name.lower() or
                        "búsqueda" in tool_desc or "buscar" in tool_desc or 
                        "consultar" in tool_desc or "información" in tool_desc):
                        default_tool = tool_name
                        break
                
                # Si no se encuentra ninguna herramienta de búsqueda, usar la primera disponible
                if not default_tool and functions:
                    default_tool = functions[0]["name"]
                
                # CORRECCIÓN: Verificar si choice.message tiene function_call antes de usarlo
                if hasattr(choice.message, "function_call") and choice.message.function_call is not None:
                    # Ejecutar la herramienta especificada por el modelo
                    function_name = choice.message.function_call.name
                    function_arguments = choice.message.function_call.arguments if choice.message.function_call.arguments else "{}"
                    tool_result = await call_tool(function_name, function_arguments)
                elif default_tool:
                    # Si no hay function_call, usar la herramienta por defecto
                    function_name = default_tool  
                    function_arguments = json.dumps(default_tool_args)
                    tool_result = await call_tool(function_name, function_arguments)
                else:
                    # Si no hay herramientas disponibles, continuar con la conversación normal
                    return answer
                
                # Agrega el resultado de la función al contexto
                conversation.append({
                    "role": "function",
                    "name": function_name,
                    "content": tool_result
                })
                
                # Generar respuesta final
                final_response = self.modelo.generar_respuesta_desde_contexto(conversation)
                
                # Aplicar filtro a la respuesta final si está disponible
                if self.safety_filter:
                    safety_result = await self.safety_filter.filter_content(final_response)
                    if not safety_result["is_safe"]:
                        logger.warning(f"Respuesta filtrada - Chat {chat_id}: {safety_result['reason']}")
                        final_response = safety_result["filtered_content"]
                    
                # Guardar la respuesta final
                conversation.append({"role": "assistant", "content": final_response})
                save_conversation(chat_id, conversation)
                
                # Devolver ambas respuestas separadas para que el conector las envíe como mensajes separados
                return answer + "\n---SPLIT_MESSAGE---\n" + final_response
            
            # Mensaje normal
            if self.safety_filter:
                safety_result = await self.safety_filter.filter_content(answer)
                if not safety_result["is_safe"]:
                    logger.warning(f"Respuesta filtrada - Chat {chat_id}: {safety_result['reason']}")
                    answer = safety_result["filtered_content"]
                
            conversation.append({"role": "assistant", "content": answer})
            save_conversation(chat_id, conversation)
            return answer
        
        # Si hay una llamada a función, procesamos la función
        if hasattr(choice.message, "function_call") and choice.message.function_call:
            function_call = choice.message.function_call
            function_name = function_call.name
            function_arguments = function_call.arguments if function_call.arguments else "{}"
            
            # Ejecutar la herramienta
            logger.info(f"🚀 Ejecutando herramienta: {function_name} con argumentos: {function_arguments}")
            tool_result = await call_tool(function_name, function_arguments)
            logger.info(f"✅ Resultado de herramienta '{function_name}': {str(tool_result)[:100]}...")
            
            # Agrega el resultado de la función al contexto
            conversation.append({
                "role": "function",
                "name": function_name,
                "content": tool_result
            })
            
            # Generamos la respuesta final basada en el resultado de la función
            final_response = self.modelo.generar_respuesta_desde_contexto(conversation)
            
            # Aplicar filtro a la respuesta final si está disponible
            if self.safety_filter:
                safety_result = await self.safety_filter.filter_content(final_response)
                if not safety_result["is_safe"]:
                    logger.warning(f"Respuesta filtrada - Chat {chat_id}: {safety_result['reason']}")
                    final_response = safety_result["filtered_content"]
                
            conversation.append({"role": "assistant", "content": final_response})
            save_conversation(chat_id, conversation)
            return final_response
        
        # Si no hay mensaje ni función
        answer = "No se recibió respuesta del asistente."
        conversation.append({"role": "assistant", "content": answer})
        save_conversation(chat_id, conversation)
        return answer
        