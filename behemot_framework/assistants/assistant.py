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
        
        # Obtén las definiciones de las funciones registradas
        functions = get_tool_definitions()

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
            tool_result = await call_tool(function_name, function_arguments)
            
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
        