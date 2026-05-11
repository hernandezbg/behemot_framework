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
        Crea la interfaz Gradio.
        
        Returns:
            Interfaz Gradio configurada
        """
        # Gradio 6.x pide que `theme` se pase al .launch(), no al constructor.
        # Lo guardamos como atributo de instancia para usarlo en launch().
        self._theme = gr.themes.Soft(
            primary_hue="green",
            neutral_hue="slate",
            text_size="md",
            spacing_size="md",
        )

        with gr.Blocks(title="Behemot Framework - Test Local") as interface:
            gr.Markdown("# 🤖 Behemot Framework - Interfaz de Prueba Local")
            gr.Markdown("Prueba tu asistente de forma interactiva antes de desplegarlo.")

            # Definimos los widgets fuera de los Tabs para que los event
            # handlers puedan referenciarlos sin problemas de contexto.
            with gr.Tab("💬 Chat"):
                chatbot = gr.Chatbot(
                    label="Conversación",
                    height=400,
                    show_label=True,
                    container=True,
                )

                with gr.Row():
                    msg = gr.Textbox(
                        label="Mensaje",
                        placeholder="Escribe tu mensaje aquí...",
                        lines=2,
                        scale=4,
                    )
                    submit = gr.Button("Enviar", variant="primary", scale=1)

                # Audio input (si está habilitado)
                audio = None
                if self.transcriptor:
                    with gr.Row():
                        audio = gr.Audio(
                            sources=["microphone", "upload"],
                            type="filepath",
                            label="🎤 Mensaje de voz (opcional)",
                        )

                clear = gr.Button("🗑️ Limpiar conversación", variant="secondary")

                gr.Examples(
                    examples=[
                        "Hola, ¿cómo estás?",
                        "¿Qué herramientas tienes disponibles?",
                        "¿Cuál es tu propósito?",
                    ],
                    inputs=msg,
                    label="Ejemplos de mensajes",
                )

                # Event handlers dentro del Tab activo: garantiza que el
                # contexto de Blocks siga abierto al registrar los callbacks
                # (Gradio 6.x es estricto con esto).
                submit.click(
                    fn=self.process_message,
                    inputs=[msg, chatbot],
                    outputs=[msg, chatbot],
                    queue=False,
                )
                msg.submit(
                    fn=self.process_message,
                    inputs=[msg, chatbot],
                    outputs=[msg, chatbot],
                    queue=False,
                )
                if audio is not None:
                    audio.change(
                        fn=self.process_audio,
                        inputs=[audio, chatbot],
                        outputs=[audio, msg, chatbot],
                        queue=False,
                    )
                clear.click(lambda: ([], ""), outputs=[chatbot, msg], queue=False)

            with gr.Tab("🔧 Herramientas"):
                gr.Markdown(self.get_tools_info())

            with gr.Tab("⚙️ Configuración"):
                gr.Markdown(self.get_config_info())

            with gr.Tab("📖 Ayuda"):
                gr.Markdown(
                    """
                    ### 🚀 Cómo usar esta interfaz:

                    1. **Chat**: Escribe mensajes o graba audio para interactuar con el asistente
                    2. **Herramientas**: Ve las herramientas disponibles para el asistente
                    3. **Configuración**: Revisa la configuración actual del sistema

                    ### 🎯 Tips:
                    - Prueba las herramientas disponibles pidiendo al asistente que las use
                    - Si RAG está habilitado, pregunta sobre tus documentos
                    - Los mensajes de voz se transcriben automáticamente (si está habilitado)

                    ### ⚠️ Nota:
                    Esta es una interfaz de prueba local. Para producción, usa los conectores
                    de Telegram, WhatsApp, Google Chat o API REST.
                    """
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