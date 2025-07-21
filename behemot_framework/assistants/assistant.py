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
from behemot_framework.morphing import MorphingManager


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
        
        # Configuración MORPHING
        morphing_config = Config.get("MORPHING", {})
        self.morphing_manager = MorphingManager(morphing_config)
        if self.morphing_manager.is_enabled():
            logger.info("🎭 MORPHING activado - El asistente puede transformarse según el contexto")
            
            # Inicializar sistema de feedback con Redis si está disponible
            try:
                from behemot_framework.context import redis_client
                if redis_client:
                    self.morphing_manager.set_redis_client(redis_client)
                else:
                    logger.info("ℹ️ Sistema de feedback de morphing deshabilitado (sin Redis)")
            except ImportError:
                logger.info("ℹ️ Sistema de feedback de morphing deshabilitado (Redis no disponible)")
        else:
            logger.info("🚫 MORPHING deshabilitado")

    async def generar_respuesta(self, chat_id: str, mensaje_usuario: str, imagen_path: str = None) -> str:

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

        # Manejar imágenes - Almacenar la ruta de la imagen para usarla más adelante
        self._current_image_path = imagen_path if imagen_path else None
        
        # Preparar el mensaje del usuario
        user_message_content = mensaje_usuario
        if imagen_path:
            if hasattr(self.modelo, 'soporta_vision') and self.modelo.soporta_vision():
                # Si el modelo soporta visión, agregar contexto sobre la imagen
                user_message_content = f"{mensaje_usuario}\n[Imagen adjunta para análisis]"
                logger.info(f"🖼️ Procesando mensaje con imagen: {imagen_path}")
            else:
                # Si el modelo no soporta visión, informar al usuario
                user_message_content = f"{mensaje_usuario}\n\n[Nota: Recibí una imagen pero este modelo no puede procesarla. Solo puedo responder al texto.]"
                logger.warning(f"⚠️ Modelo {type(self.modelo).__name__} no soporta visión. Imagen ignorada: {imagen_path}")
        
        conversation.append({"role": "user", "content": user_message_content})
        
        # MORPHING: Verificar si necesito cambiar de personalidad/configuración
        morph_result = self.morphing_manager.process_message(mensaje_usuario, conversation)
        current_morph_config = morph_result['morph_config']
        
        # Si hubo un cambio de morph, actualizo la configuración del modelo
        if morph_result['should_morph']:
            logger.info(f"🎭 Morphing activo: {morph_result['previous_morph']} → {morph_result['target_morph']}")
            
            # Actualizo el prompt del sistema si es necesario
            new_personality = current_morph_config.get('personality', self.prompt_sistema)
            if new_personality != self.prompt_sistema:
                # Actualizo el primer mensaje del sistema en la conversación
                for i, msg in enumerate(conversation):
                    if msg.get('role') == 'system':
                        conversation[i]['content'] = new_personality
                        break
                        
            # Si hay continuity phrase, la agrego al contexto
            continuity_phrase = morph_result.get('context', {}).get('continuity_phrase')
            if continuity_phrase:
                # Agrego una nota del sistema sobre la transición
                conversation.append({
                    "role": "system", 
                    "content": f"Contexto de transición: {continuity_phrase}"
                })
        
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
                            # Extraer información de página y fuente de metadata
                            page_info = ""
                            if hasattr(doc, 'metadata') and doc.metadata:
                                page = doc.metadata.get('page')
                                source = doc.metadata.get('source', '')
                                filename = doc.metadata.get('filename', source)
                                
                                # Construir información de fuente
                                source_parts = []
                                if filename:
                                    # Extraer solo el nombre del archivo sin ruta
                                    import os
                                    filename = os.path.basename(filename)
                                    source_parts.append(f"📄 {filename}")
                                
                                if page is not None:
                                    source_parts.append(f"Página {page + 1}")  # +1 porque páginas empiezan en 0
                                
                                if source_parts:
                                    page_info = f" ({', '.join(source_parts)})"
                                elif source:
                                    page_info = f" (📄 {source})"
                        elif hasattr(doc, 'content'):
                            content = doc.content
                            page_info = ""
                        elif isinstance(doc, dict):
                            content = doc.get("content", str(doc))
                            # Construir información de fuente para dict
                            source_parts = []
                            if 'filename' in doc or 'source' in doc:
                                filename = doc.get('filename', doc.get('source', ''))
                                if filename:
                                    import os
                                    filename = os.path.basename(filename)
                                    source_parts.append(f"📄 {filename}")
                            
                            if 'page' in doc:
                                page_num = doc.get('page')
                                if page_num is not None:
                                    source_parts.append(f"Página {page_num + 1 if isinstance(page_num, int) else page_num}")
                            
                            page_info = f" ({', '.join(source_parts)})" if source_parts else ""
                        else:
                            content = str(doc)
                            page_info = ""
                        
                        context_parts.append(f"Documento {i}{page_info}:\n{content}")
                    
                    # Mejorar formato si múltiples chunks son del mismo archivo
                    if len(best_documents) > 1:
                        # Verificar si todos son del mismo archivo
                        filenames = set()
                        for doc in best_documents:
                            if hasattr(doc, 'metadata') and doc.metadata:
                                filename = doc.metadata.get('filename', '')
                                if filename:
                                    filenames.add(filename)
                        
                        if len(filenames) == 1:
                            # Todos del mismo archivo - usar formato simplificado
                            single_filename = list(filenames)[0]
                            context_message = f"Información relevante de {single_filename}:\n\n" + "\n\n---\n\n".join(context_parts)
                        else:
                            # Múltiples archivos - usar formato detallado
                            context_message = f"Información relevante de documentos:\n\n" + "\n\n---\n\n".join(context_parts)
                    else:
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

        # Debug: Verificar condiciones para procesamiento de imagen
        has_image = self._current_image_path is not None
        has_vision_method = hasattr(self.modelo, 'soporta_vision')
        supports_vision = has_vision_method and self.modelo.soporta_vision() if has_vision_method else False
        
        logger.info(f"🔍 Debug procesamiento imagen: has_image={has_image}, has_vision_method={has_vision_method}, supports_vision={supports_vision}")
        if has_image:
            logger.info(f"📷 Ruta imagen: {self._current_image_path}")
            logger.info(f"🤖 Tipo de modelo: {type(self.modelo).__name__}")

        # Decidir qué método usar basado en si hay imagen y si el modelo soporta visión
        if (self._current_image_path and 
            hasattr(self.modelo, 'soporta_vision') and 
            self.modelo.soporta_vision()):  # Si hay imagen y el modelo soporta visión, usar método directo
            
            logger.info(f"🖼️ USANDO FLUJO DIRECTO PARA IMAGEN: {self._current_image_path}")
            try:
                # Para mensajes con imagen sin herramientas, usar el método directo
                response_text = self.modelo.generar_respuesta(
                    mensaje_usuario, 
                    self.prompt_sistema, 
                    self._current_image_path
                )
                
                # Aplicar filtro si está disponible
                if self.safety_filter:
                    safety_result = await self.safety_filter.filter_content(response_text)
                    if not safety_result["is_safe"]:
                        logger.warning(f"Respuesta filtrada - Chat {chat_id}: {safety_result['reason']}")
                        response_text = safety_result["filtered_content"]
                
                # Agregar a la conversación y guardar
                conversation.append({"role": "assistant", "content": response_text})
                save_conversation(chat_id, conversation)
                
                return response_text
                
            except Exception as e:
                return f"Error al generar respuesta con imagen: {str(e)}"
        else:
            # Usar el método con herramientas (comportamiento actual)
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
                
                # Detectar feedback implícito si morphing está activo
                if self.morphing_manager.is_enabled():
                    self._detect_and_record_feedback(chat_id, conversation, mensaje_usuario)
                
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
            
            # Detectar feedback implícito si morphing está activo
            if self.morphing_manager.is_enabled():
                self._detect_and_record_feedback(chat_id, conversation, mensaje_usuario)
            
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
            
            # Detectar feedback implícito si morphing está activo
            if self.morphing_manager.is_enabled():
                self._detect_and_record_feedback(chat_id, conversation, mensaje_usuario)
            
            save_conversation(chat_id, conversation)
            return final_response
        
        # Si no hay mensaje ni función
        answer = "No se recibió respuesta del asistente."
        conversation.append({"role": "assistant", "content": answer})
        save_conversation(chat_id, conversation)
        return answer
    
    def _detect_and_record_feedback(self, chat_id: str, conversation: list, user_input: str):
        """
        Detecta y registra feedback implícito sobre transformaciones de morphing.
        """
        try:
            # Extraer solo los mensajes del usuario de los últimos intercambios
            user_messages = []
            for msg in conversation[-4:]:  # Últimos 4 mensajes
                if msg.get('role') == 'user':
                    user_messages.append(msg.get('content', ''))
            
            if len(user_messages) >= 1:
                # Detectar feedback implícito
                feedback = self.morphing_manager.detect_implicit_feedback(user_messages)
                
                if feedback is not None:
                    # Registrar el feedback
                    self.morphing_manager.record_morph_feedback(
                        success=feedback,
                        user_id=chat_id,
                        trigger=user_input[:50],  # Primeros 50 chars del trigger
                        confidence=0.7  # Confianza media para feedback implícito
                    )
                    
                    logger.debug(f"📝 Feedback implícito detectado: {'positivo' if feedback else 'negativo'} "
                                f"para morph '{self.morphing_manager.get_current_morph()}'")
        except Exception as e:
            logger.debug(f"Error detectando feedback: {e}")
        