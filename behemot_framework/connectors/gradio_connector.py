# behemot_framework/connectors/gradio_connector.py
import logging
import gradio as gr
from typing import List, Tuple, Optional, Dict, Any
import asyncio
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class GradioConnector:
    """
    Conector para crear interfaz de prueba local usando Gradio.
    Proporciona una UI web para testing y demos del asistente.
    """
    
    def __init__(self, assistant, tools_registry=None, transcriptor=None):
        """
        Inicializa el conector Gradio.
        
        Args:
            assistant: Instancia del asistente de Behemot
            tools_registry: Registro de herramientas disponibles
            transcriptor: Servicio de transcripción (opcional)
        """
        self.assistant = assistant
        self.tools_registry = tools_registry
        self.transcriptor = transcriptor
        self.interface = None
        
    async def process_message(self, message: str, history: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
        """
        Procesa un mensaje del usuario y actualiza el historial.
        
        Args:
            message: Mensaje del usuario
            history: Historial de conversación [{"role": "user", "content": "..."}, ...]
            
        Returns:
            Tupla con ("", historial_actualizado)
        """
        if not message.strip():
            return "", history
            
        # Usar un chat_id consistente para la sesión
        chat_id = "gradio_test_session"
        
        try:
            # Agregar mensaje del usuario al historial
            history.append({"role": "user", "content": message})
            
            # Generar respuesta del asistente
            logger.info(f"Procesando mensaje en Gradio: {message[:50]}...")
            response = await self.assistant.generar_respuesta(chat_id, message)
            
            # Agregar respuesta del asistente al historial
            history.append({"role": "assistant", "content": response})
            
            logger.info(f"Respuesta generada: {response[:50]}...")
            
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}", exc_info=True)
            history.append({"role": "assistant", "content": f"❌ Error: {str(e)}"})
            
        return "", history
    
    async def process_audio(self, audio_path: str, history: List[Dict[str, str]]) -> Tuple[None, str, List[Dict[str, str]]]:
        """
        Procesa un archivo de audio, lo transcribe y envía como mensaje.
        
        Args:
            audio_path: Ruta al archivo de audio
            history: Historial de conversación
            
        Returns:
            Tupla con (None, "", historial_actualizado)
        """
        if not audio_path or not self.transcriptor:
            return None, "", history
            
        try:
            # Transcribir audio
            logger.info(f"Transcribiendo audio: {audio_path}")
            transcribed_text = self.transcriptor.transcribe_audio(audio_path)
            
            if transcribed_text:
                # Procesar el texto transcrito
                _, history = await self.process_message(transcribed_text, history)
                
        except Exception as e:
            logger.error(f"Error procesando audio: {e}", exc_info=True)
            history.append({"role": "user", "content": "🎤 [Audio]"})
            history.append({"role": "assistant", "content": f"❌ Error transcribiendo: {str(e)}"})
            
        return None, "", history
    
    def get_tools_info(self) -> str:
        """
        Obtiene información sobre las herramientas disponibles.
        
        Returns:
            Texto formateado con la información de herramientas
        """
        if not self.tools_registry:
            return "No hay herramientas cargadas."
            
        from behemot_framework.tooling import get_tool_definitions
        tools = get_tool_definitions()
        
        if not tools:
            return "No hay herramientas disponibles."
            
        info = "### 🔧 Herramientas Disponibles:\n\n"
        for tool in tools:
            info += f"**{tool['name']}**\n"
            info += f"_{tool.get('description', 'Sin descripción')}_\n\n"
            
        return info
    
    def get_config_info(self) -> str:
        """
        Obtiene información de configuración del asistente.
        
        Returns:
            Texto formateado con la configuración
        """
        from behemot_framework.config import Config
        
        config_info = "### ⚙️ Configuración Actual:\n\n"
        
        # Información básica
        config_info += f"**Modelo**: {Config.get('MODEL_PROVIDER', 'N/A')} - {Config.get('MODEL_NAME', 'N/A')}\n"
        config_info += f"**Seguridad**: {Config.get('SAFETY_LEVEL', 'medium')}\n"
        config_info += f"**RAG**: {'✅ Habilitado' if Config.get('ENABLE_RAG', False) else '❌ Deshabilitado'}\n"
        
        if Config.get('ENABLE_RAG', False):
            folders = Config.get('RAG_FOLDERS', [])
            if folders:
                config_info += f"**Carpetas RAG**: {', '.join(folders)}\n"
        
        config_info += f"**Redis**: {'✅ Configurado' if Config.get('REDIS_PUBLIC_URL') else '❌ No configurado'}\n"
        config_info += f"**Voz**: {'✅ Habilitado' if self.transcriptor else '❌ Deshabilitado'}\n"
        
        # Prompt preview
        prompt = Config.get('PROMPT_SISTEMA', '')
        if prompt:
            preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
            config_info += f"\n**Prompt Sistema** (preview):\n```\n{preview}\n```"
            
        return config_info
    
    def create_interface(self) -> gr.Blocks:
        """
        Crea la interfaz Gradio con estilo WhatsApp.
        
        Returns:
            Interfaz Gradio configurada
        """
        # CSS personalizado para estilo WhatsApp
        custom_css = """
        .gradio-container {
            max-width: 500px !important;
            margin: 0 auto !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }
        
        /* Header estilo WhatsApp */
        .header-container {
            background-color: #075E54 !important;
            color: white !important;
            padding: 16px !important;
            border-radius: 0 !important;
            margin: -20px -20px 0 -20px !important;
        }
        
        .header-container h1 {
            margin: 0 !important;
            font-size: 20px !important;
            font-weight: 500 !important;
        }
        
        .header-container p {
            margin: 4px 0 0 0 !important;
            font-size: 14px !important;
            opacity: 0.9 !important;
        }
        
        /* Área de chat */
        .chat-container {
            background-color: #E5DDD5 !important;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'%3E%3Cg fill-opacity='0.03'%3E%3Cpolygon fill='%23000' points='50 0 60 40 100 50 60 60 50 100 40 60 0 50 40 40'/%3E%3C/g%3E%3C/svg%3E") !important;
            min-height: 500px !important;
            padding: 10px !important;
        }
        
        /* Mensajes */
        .message {
            max-width: 70% !important;
            word-wrap: break-word !important;
        }
        
        .user-message {
            background-color: #DCF8C6 !important;
            margin-left: auto !important;
            border-radius: 7px 7px 0 7px !important;
        }
        
        .bot-message {
            background-color: white !important;
            margin-right: auto !important;
            border-radius: 7px 7px 7px 0 !important;
        }
        
        /* Input área */
        .input-container {
            background-color: #F0F0F0 !important;
            padding: 10px !important;
            margin: 0 -20px -20px -20px !important;
        }
        
        .input-row {
            display: flex !important;
            gap: 8px !important;
            align-items: flex-end !important;
        }
        
        /* Botón de enviar estilo WhatsApp */
        .send-button {
            background-color: #25D366 !important;
            color: white !important;
            border: none !important;
            border-radius: 50% !important;
            width: 48px !important;
            height: 48px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            cursor: pointer !important;
            transition: background-color 0.2s !important;
        }
        
        .send-button:hover {
            background-color: #22C35E !important;
        }
        
        /* Input de texto */
        .message-input {
            flex: 1 !important;
            border: 1px solid #DDD !important;
            border-radius: 24px !important;
            padding: 10px 15px !important;
            font-size: 16px !important;
            background-color: white !important;
        }
        
        /* Ocultar labels */
        label {
            display: none !important;
        }
        
        /* Ajustar chatbot */
        .chatbot {
            border: none !important;
            shadow: none !important;
        }
        """
        
        with gr.Blocks(
            title="Behemot Chat", 
            theme=gr.themes.Base(),
            css=custom_css
        ) as interface:
            # Header estilo WhatsApp
            with gr.Column(elem_classes="header-container"):
                gr.HTML("""
                    <h1>🤖 Behemot Assistant</h1>
                    <p>En línea</p>
                """)
            
            # Área de chat
            with gr.Column(elem_classes="chat-container"):
                chatbot = gr.Chatbot(
                    label="",
                    height=500,
                    show_label=False,
                    container=False,
                    type="messages",
                    elem_classes="chatbot",
                    show_copy_button=True,
                    bubble_full_width=False
                )
            
            # Área de input
            with gr.Column(elem_classes="input-container"):
                with gr.Row(elem_classes="input-row"):
                    # Audio button (si está habilitado)
                    if self.transcriptor:
                        audio = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            label="",
                            show_label=False,
                            container=False,
                            interactive=True,
                            elem_classes="audio-input"
                        )
                    
                    # Input de mensaje
                    msg = gr.Textbox(
                        label="",
                        placeholder="Escribe un mensaje",
                        lines=1,
                        max_lines=3,
                        show_label=False,
                        container=False,
                        elem_classes="message-input",
                        autofocus=True
                    )
                    
                    # Botón de enviar con ícono
                    submit = gr.Button(
                        value="➤",
                        elem_classes="send-button",
                        variant="primary"
                    )
            
            # Event handlers
            submit.click(
                fn=self.process_message,
                inputs=[msg, chatbot],
                outputs=[msg, chatbot],
                queue=False
            )
            
            msg.submit(
                fn=self.process_message,
                inputs=[msg, chatbot],
                outputs=[msg, chatbot],
                queue=False
            )
            
            if self.transcriptor:
                audio.change(
                    fn=self.process_audio,
                    inputs=[audio, chatbot],
                    outputs=[audio, msg, chatbot],
                    queue=False
                )
            
        return interface
    
    def launch(self, port: int = 7860, share: bool = None):
        """
        Lanza la interfaz Gradio.
        
        Args:
            port: Puerto para la interfaz (default: 7860)
            share: Si crear un link público temporal. Si es None, lee de configuración
        """
        from behemot_framework.config import Config
        
        # Determinar si compartir públicamente
        if share is None:
            # Primero buscar en variables de entorno
            share_env = os.getenv('GRADIO_SHARE', '').lower()
            if share_env in ['true', '1', 'yes']:
                share = True
            elif share_env in ['false', '0', 'no']:
                share = False
            else:
                # Si no está en env, buscar en configuración
                share = Config.get('GRADIO_SHARE', False)
        
        self.interface = self.create_interface()
        
        logger.info(f"🚀 Lanzando interfaz de prueba local en puerto {port}")
        logger.info(f"🌐 Accede a http://localhost:{port}")
        if share:
            logger.info("🔗 Se creará un link público temporal para compartir")
        
        # Usar try_launch con rango de puertos
        try:
            self.interface.launch(
                server_port=port,
                share=share,
                server_name="0.0.0.0",
                quiet=False,
                show_error=True,
                prevent_thread_lock=True,
                inbrowser=False
            )
        except Exception as e:
            # Si falla el puerto, intentar con otros puertos
            logger.warning(f"⚠️ Puerto {port} ocupado, buscando puerto disponible...")
            for test_port in range(port + 1, port + 10):
                try:
                    logger.info(f"🔄 Intentando puerto {test_port}")
                    self.interface.launch(
                        server_port=test_port,
                        share=share,
                        server_name="0.0.0.0",
                        quiet=False,
                        show_error=True,
                        prevent_thread_lock=True,
                        inbrowser=False
                    )
                    logger.info(f"✅ Interfaz iniciada en puerto {test_port}")
                    logger.info(f"🌐 Accede a http://localhost:{test_port}")
                    return
                except Exception:
                    continue
            logger.error(f"❌ No se pudo encontrar un puerto disponible")