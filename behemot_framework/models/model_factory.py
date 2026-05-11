# models/model_factory.py
import logging
from typing import Dict, Type
from .base_model import BaseModel
from .gpt_model import GPTModel
from behemot_framework.config import Config


logger = logging.getLogger(__name__)


class ModelFactory:
    """
    Factory para crear instancias de modelos de lenguaje basándose en la configuración.
    Permite agregar nuevos proveedores de IA de forma extensible.
    """
    
    # Registro de modelos disponibles
    _models: Dict[str, Type[BaseModel]] = {
        "openai": GPTModel,
        "gpt": GPTModel,  # Alias para compatibilidad
    }
    
    @classmethod
    def register_model(cls, provider_name: str, model_class: Type[BaseModel]):
        """
        Registra un nuevo modelo en el factory.
        
        Args:
            provider_name: Nombre del proveedor (ej: "gemini", "anthropic")
            model_class: Clase que implementa BaseModel
        """
        cls._models[provider_name.lower()] = model_class
        logger.info(f"Modelo registrado: {provider_name}")
    
    @classmethod
    def create_model(cls, provider: str = None, api_key: str = None) -> BaseModel:
        """
        Crea una instancia del modelo basándose en el proveedor especificado.
        
        Args:
            provider: Nombre del proveedor. Si no se especifica, lo obtiene de la configuración.
            api_key: API key del proveedor. Si no se especifica, lo obtiene de la configuración.
            
        Returns:
            Instancia del modelo correspondiente
            
        Raises:
            ValueError: Si el proveedor no está soportado
        """
        config = Config.get_config()
        
        # Obtener proveedor de la configuración si no se especifica
        if provider is None:
            provider = config.get("MODEL_PROVIDER", "openai").lower()
        else:
            provider = provider.lower()
        
        # Obtener la clase del modelo
        if provider not in cls._models:
            available = ", ".join(cls._models.keys())
            raise ValueError(
                f"Proveedor '{provider}' no soportado. "
                f"Proveedores disponibles: {available}"
            )
        
        model_class = cls._models[provider]
        
        # Obtener API key según el proveedor.
        # Vertex AI es un caso especial: NO usa API key, autentica con
        # Application Default Credentials (cuenta de servicio de Cloud Run,
        # `gcloud auth application-default login` en local, etc.). Solo
        # requiere VERTEX_PROJECT_ID, que el propio VertexModel valida.
        if api_key is None:
            api_key_mapping = {
                "openai": "GPT_API_KEY",
                "gpt": "GPT_API_KEY",
                "gemini": "GEMINI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
            }

            if provider == "vertex":
                # No exigir API key. Validar VERTEX_PROJECT_ID está presente
                # — sin él, Vertex no puede inicializar y la cuenta de servicio
                # no resuelve nada.
                if not config.get("VERTEX_PROJECT_ID"):
                    raise ValueError(
                        "VERTEX_PROJECT_ID es obligatorio para usar Vertex AI. "
                        "Defínelo en tu config YAML o como variable de entorno. "
                        "La autenticación usa ADC (Application Default Credentials), "
                        "no API key."
                    )
                api_key = None  # explícito: VertexModel lo ignora
            else:
                api_key_var = api_key_mapping.get(provider, f"{provider.upper()}_API_KEY")
                api_key = config.get(api_key_var)

                if not api_key:
                    raise ValueError(
                        f"No se encontró la API key para {provider}. "
                        f"Asegúrate de configurar {api_key_var} en el archivo .env"
                    )

        # Crear y retornar la instancia del modelo
        logger.info(f"Creando modelo: {provider}")
        return model_class(api_key)
    
    @classmethod
    def get_available_providers(cls) -> list:
        """
        Retorna la lista de proveedores disponibles.
        
        Returns:
            Lista de nombres de proveedores
        """
        return list(cls._models.keys())