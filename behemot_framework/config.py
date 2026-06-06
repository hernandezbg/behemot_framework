# app/config.py
import os
import yaml
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Configurar logger
logger = logging.getLogger(__name__)

# Cargar .env por defecto
load_dotenv()

class Config:
    """
    Clase singleton para manejar toda la configuración del framework.
    """
    _instance = None
    _initialized = False
    _config = {}
    _config_path = None

    def __new__(cls):
        """Implementación del patrón singleton"""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, config_path: Optional[str] = None) -> None:
        """
        Inicializa la configuración con los valores por defecto y 
        la configuración del archivo si se proporciona.
        
        Args:
            config_path: Ruta al archivo de configuración (YAML o JSON)
        """
        instance = cls()

        # Si ya está inicializado con la misma ruta, no hacer nada
        if instance._initialized and instance._config_path == config_path:
            logger.debug(f"Configuración ya inicializada con {config_path}. No se recargará.")
            return
        
        # Si está inicializado con una ruta diferente, registrar un aviso
        if instance._initialized and instance._config_path != config_path:
            logger.warning(f"Recargando configuración con ruta diferente: {instance._config_path} -> {config_path}")
            
        # Cargar configuración por defecto
        instance._config = cls._get_default_config()
        instance._config_path = config_path
        
        # Si se proporciona una ruta de configuración, cargar desde archivo
        if config_path:
            logger.info(f"Cargando configuración desde: {config_path}")
            if os.path.exists(config_path):
                try:
                    ext = os.path.splitext(config_path)[1].lower()
                    
                    if ext in ('.yaml', '.yml'):
                        with open(config_path, 'r', encoding='utf-8') as f:
                            file_config = yaml.safe_load(f)
                    elif ext == '.json':
                        with open(config_path, 'r', encoding='utf-8') as f:
                            file_config = json.load(f)
                    else:
                        logger.error(f"Formato de configuración no soportado: {ext}")
                        raise ValueError(f"Formato de configuración no soportado: {ext}")
                        
                    # Actualizar configuración con valores del archivo
                    logger.info(f"Configuración cargada desde {config_path}")
                    
                    # Mostrar información relevante en logs
                    if "PROMPT_SISTEMA" in file_config:
                        prompt_preview = file_config["PROMPT_SISTEMA"][:50] + "..." if len(file_config["PROMPT_SISTEMA"]) > 50 else file_config["PROMPT_SISTEMA"]
                        logger.info(f"PROMPT_SISTEMA cargado: {prompt_preview}")
                    
                    instance._config.update(file_config)
                    
                    # Guardar la ruta para acceso posterior
                    instance._config["_config_path"] = config_path
                        
                except Exception as e:
                    logger.error(f"Error al cargar configuración desde {config_path}: {e}", exc_info=True)
            else:
                logger.warning(f"Archivo de configuración no encontrado: {config_path}")
        
        # Cargar prompt personalizado si existe
        prompt_path = os.getenv("PROMPT_PATH", "")
        if prompt_path and os.path.exists(prompt_path):
            try:
                logger.info(f"Cargando prompt desde archivo: {prompt_path}")
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    instance._config["PROMPT_SISTEMA"] = f.read()
                    logger.info(f"Prompt cargado exitosamente desde: {prompt_path}")
            except Exception as e:
                logger.error(f"Error al cargar prompt desde {prompt_path}: {e}")
        
        # Mostrar algunas configuraciones clave para depuración
        logger.info(f"Configuración final cargada:")
        logger.info(f"- VERSION: {instance._config.get('VERSION')}")
        logger.info(f"- MODEL_NAME: {instance._config.get('MODEL_NAME')}")
        
        # Mostrar una vista previa del prompt (solo primeros 50 caracteres)
        prompt_preview = instance._config.get("PROMPT_SISTEMA", "")[:50] + "..." if len(instance._config.get("PROMPT_SISTEMA", "")) > 50 else instance._config.get("PROMPT_SISTEMA", "")
        logger.info(f"- PROMPT_SISTEMA: {prompt_preview}")
        
        instance._initialized = True

    @staticmethod
    def _get_default_config() -> Dict[str, Any]:
        """
        Retorna la configuración por defecto basada en variables de entorno.
        
        Returns:
            Dict: Configuración por defecto
        """
        return {
            # Versión del framework
            "VERSION": "1.0.0",
            
            # Configuración de API Keys
            "GPT_API_KEY": os.getenv("GPT_API_KEY", ""),
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
            "VERTEX_API_KEY": os.getenv("VERTEX_API_KEY", ""),
            "VERTEX_PROJECT_ID": os.getenv("VERTEX_PROJECT_ID", ""),
            "VERTEX_LOCATION": os.getenv("VERTEX_LOCATION", "us-central1"),
            "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
            "TELEGRAM_TOKEN": os.getenv("TELEGRAM_TOKEN", ""),

            # Configuración de WhatsApp
            "WHATSAPP_TOKEN": os.getenv("WHATSAPP_TOKEN", ""),
            "WHATSAPP_PHONE_ID": os.getenv("WHATSAPP_PHONE_ID", ""),
            "WHATSAPP_VERIFY_TOKEN": os.getenv("WHATSAPP_VERIFY_TOKEN", ""),
            
            # Configuración de conectores
            "WEBHOOK_URL": os.getenv("WEBHOOK_URL", ""),

            # Configuración específica por conector
            "TELEGRAM_WEBHOOK_URL": os.getenv("TELEGRAM_WEBHOOK_URL", ""),
            # Secreto compartido con Telegram para validar X-Telegram-Bot-Api-Secret-Token.
            # Si está vacío, el framework genera uno aleatorio en runtime (no persistente).
            # Para deploys multi-réplica/serverless, definirlo explícitamente.
            "TELEGRAM_WEBHOOK_SECRET": os.getenv("TELEGRAM_WEBHOOK_SECRET", ""),
            "WHATSAPP_WEBHOOK_URL": os.getenv("WHATSAPP_WEBHOOK_URL", ""),
            # App Secret de Meta (Facebook Developer Console) para validar firma HMAC
            # del header X-Hub-Signature-256 en webhooks de WhatsApp Cloud API.
            "WHATSAPP_APP_SECRET": os.getenv("WHATSAPP_APP_SECRET", ""),
            "API_WEBHOOK_URL": os.getenv("API_WEBHOOK_URL", ""),
            # Por seguridad/UX el default es false: voice requiere GPT_API_KEY
            # (Whisper de OpenAI) y romper el arranque cuando el usuario usa
            # otro provider es desagradable. Quien lo necesite lo activa
            # explícitamente en su YAML o con enable_voice=True.
            "ENABLE_VOICE": os.getenv("ENABLE_VOICE", "false").lower() in ("true", "1", "yes"),
            
            # Configuración de Redis para persistencia. Aceptamos también
            # REDIS_URL como fallback porque muchas plataformas
            # (Railway, Render, Heroku) inyectan ese nombre por convención.
            # REDIS_PUBLIC_URL tiene prioridad si ambas están definidas.
            "REDIS_PUBLIC_URL": os.getenv("REDIS_PUBLIC_URL", "") or os.getenv("REDIS_URL", ""),
            
            # Configuración de seguridad
            "SAFETY_LEVEL": os.getenv("SAFETY_LEVEL", "medium"),  # low, medium, high

            # Configuración de administración (default seguro: production sin admins).
            # Para habilitar comandos admin se debe definir ADMIN_USERS en el YAML.
            "ADMIN_MODE": os.getenv("ADMIN_MODE", "production"),  # production | dev
            "ADMIN_USERS": [],

            # Bearer token requerido para acceder a /status. Si está vacío, /status
            # queda accesible sin auth (uso solo recomendado detrás de firewall).
            "STATUS_API_TOKEN": os.getenv("STATUS_API_TOKEN", ""),

            # Auth para el endpoint /api/chat: none | api_key. En modo api_key
            # se valida X-API-Key contra API_KEYS (lista, comparación constant-time).
            "API_AUTH_MODE": os.getenv("API_AUTH_MODE", "none"),
            "API_KEYS": (
                os.getenv("API_KEYS", "").split(",")
                if os.getenv("API_KEYS")
                else []
            ),

            # Rate limiting de /api/chat (in-memory, por IP). 0 desactiva el límite.
            "API_RATE_LIMIT_PER_MINUTE": int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "60")),
            # Tope de tamaño de body para JSON y audios (bytes).
            "API_MAX_REQUEST_SIZE": int(os.getenv("API_MAX_REQUEST_SIZE", str(10 * 1024 * 1024))),
            "API_MAX_AUDIO_SIZE": int(os.getenv("API_MAX_AUDIO_SIZE", str(25 * 1024 * 1024))),
            
            # Configuración TTS (Text-to-Speech)
            # Modo de respuesta para canales de voz: "text" | "audio" | "both" | "adaptive"
            "WHATSAPP_RESPONSE_MODE": os.getenv("WHATSAPP_RESPONSE_MODE", "text"),
            "TELEGRAM_RESPONSE_MODE": os.getenv("TELEGRAM_RESPONSE_MODE", "text"),
            # Provider TTS: "openai" | "elevenlabs"
            "TTS_PROVIDER": os.getenv("TTS_PROVIDER", "openai"),
            # OpenAI TTS
            "TTS_MODEL": os.getenv("TTS_MODEL", "tts-1"),
            "TTS_VOICE": os.getenv("TTS_VOICE", "alloy"),
            # ElevenLabs TTS
            "ELEVENLABS_API_KEY": os.getenv("ELEVENLABS_API_KEY", ""),
            "ELEVENLABS_VOICE_ID": os.getenv("ELEVENLABS_VOICE_ID", "Rachel"),
            "ELEVENLABS_MODEL": os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2"),

            # Configuración de RAG (Retrieval Augmented Generation)
            "ENABLE_RAG": os.getenv("ENABLE_RAG", "false").lower() in ("true", "1", "yes"),
            "AUTO_RAG": os.getenv("AUTO_RAG", "false").lower() in ("true", "1", "yes"),  # Nuevo: RAG automático
            "RAG_FOLDERS": os.getenv("RAG_FOLDERS", "").split(",") if os.getenv("RAG_FOLDERS") else [],
            # Política anti-path-traversal y anti-SSRF para fuentes RAG.
            # Si RAG_ALLOWED_ROOTS no se define, se usa RAG_FOLDERS como fallback.
            "RAG_ALLOWED_ROOTS": (
                os.getenv("RAG_ALLOWED_ROOTS", "").split(",")
                if os.getenv("RAG_ALLOWED_ROOTS")
                else None
            ),
            "RAG_ALLOWED_URL_HOSTS": (
                os.getenv("RAG_ALLOWED_URL_HOSTS", "").split(",")
                if os.getenv("RAG_ALLOWED_URL_HOSTS")
                else []
            ),
            "RAG_ALLOW_PRIVATE_NETWORKS": os.getenv(
                "RAG_ALLOW_PRIVATE_NETWORKS", "false"
            ).lower() in ("true", "1", "yes"),
            "GCP_BUCKET_NAME": os.getenv("GCP_BUCKET_NAME", ""),
            
            # Configuración RAG avanzada
            "RAG_EMBEDDING_PROVIDER": os.getenv("RAG_EMBEDDING_PROVIDER", "openai"),  # openai, google, huggingface
            "RAG_EMBEDDING_MODEL": os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small"),
            "RAG_PERSIST_DIRECTORY": os.getenv("RAG_PERSIST_DIRECTORY", "chroma_db"),
            "RAG_COLLECTION_NAME": os.getenv("RAG_COLLECTION_NAME", "default_collection"),
            "RAG_CHUNK_SIZE": int(os.getenv("RAG_CHUNK_SIZE", "1000")),
            "RAG_CHUNK_OVERLAP": int(os.getenv("RAG_CHUNK_OVERLAP", "200")),
            
            # Configuración AUTO_RAG
            "RAG_MAX_RESULTS": int(os.getenv("RAG_MAX_RESULTS", "3")),
            "RAG_SIMILARITY_THRESHOLD": float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.6")),
            
            # Prompt del sistema por defecto
            "PROMPT_SISTEMA": os.getenv("PROMPT_SISTEMA", """
            Eres un asistente de IA útil y amigable.
            """),
            
            # Modelo a utilizar
            "MODEL_PROVIDER": os.getenv("MODEL_PROVIDER", "openai"),  # openai, gemini, vertex, anthropic
            "MODEL_NAME": os.getenv("MODEL_NAME", "gpt-4o-mini"),
            "MODEL_TEMPERATURE": float(os.getenv("MODEL_TEMPERATURE", "0.7")),
            "MODEL_MAX_TOKENS": int(os.getenv("MODEL_MAX_TOKENS", "150")),
            
            # Lista de herramientas a cargar por defecto
            "DEFAULT_TOOLS": [],
            
            # Configuración de Gradio
            "GRADIO_SHARE": os.getenv("GRADIO_SHARE", "false").lower() in ("true", "1", "yes"),
            
            # Configuración de Morphing (por defecto deshabilitado)
            "MORPHING": {
                "enabled": os.getenv("MORPHING_ENABLED", "false").lower() in ("true", "1", "yes"),
                "default_morph": "general",
                "settings": {
                    "sensitivity": "medium",
                    "transition_style": "seamless"
                },
                "morphs": {
                    "general": {
                        "personality": "Soy un asistente útil y amigable",
                        "model": "gpt-4o-mini",
                        "temperature": 0.7
                    }
                },
                "advanced": {
                    "instant_layer": {
                        "enabled": True
                    },
                    "gradual_layer": {
                        "enabled": True,
                        "confidence_threshold": 0.6
                    },
                    "transitions": {
                        "prevent_morphing_loops": True,
                        "preserve_context": True
                    }
                }
            },
        }

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor específico de la configuración.
        
        Args:
            key: Clave a buscar
            default: Valor por defecto si la clave no existe
            
        Returns:
            Any: Valor asociado a la clave
        """
        instance = cls()
        if not instance._initialized:
            instance.initialize()
        return instance._config.get(key, default)

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """
        Obtiene la configuración completa.
        
        Returns:
            Dict: Configuración actual
        """
        instance = cls()
        if not instance._initialized:
            instance.initialize()
        return instance._config

    @classmethod
    def get_config_path(cls) -> Optional[str]:
        """
        Obtiene la ruta del archivo de configuración.
        
        Returns:
            str: Ruta de configuración o None
        """
        instance = cls()
        return instance._config_path

    @classmethod
    def reload(cls) -> None:
        """
        Recarga la configuración desde el archivo.
        """
        instance = cls()
        instance.initialize(instance._config_path)

# Para compatibilidad con código existente
def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Función de compatibilidad para código existente.
    En lugar de cargar la configuración directamente, usa el singleton.
    
    Args:
        config_path: Ruta al archivo de configuración
    
    Returns:
        Dict: Configuración actual
    """
    Config.initialize(config_path)
    return Config.get_config()

# Inicializar configuración por defecto
#Config.initialize()

# Variables globales para compatibilidad con código existente
GPT_API_KEY = Config.get("GPT_API_KEY")
TELEGRAM_TOKEN = Config.get("TELEGRAM_TOKEN")
WEBHOOK_URL = Config.get("WEBHOOK_URL")
REDIS_PUBLIC_URL = Config.get("REDIS_PUBLIC_URL")
PROMPT_SISTEMA = Config.get("PROMPT_SISTEMA")
SAFETY_LEVEL = Config.get("SAFETY_LEVEL")
RAG_FOLDERS = Config.get("RAG_FOLDERS")
