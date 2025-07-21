# models/base_model.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union


class BaseModel(ABC):
    """
    Interfaz base para todos los modelos de lenguaje en el framework Behemot.
    Define los métodos que deben implementar todos los proveedores de IA.
    """
    
    @abstractmethod
    def __init__(self, api_key: str):
        """
        Inicializa el modelo con la API key correspondiente.
        
        Args:
            api_key: La clave API del proveedor
        """
        pass
    
    @abstractmethod
    def generar_respuesta(self, mensaje_usuario: str, prompt_sistema: str, imagen_path: Optional[str] = None) -> str:
        """
        Genera una respuesta simple sin contexto de conversación.
        
        Args:
            mensaje_usuario: El mensaje del usuario
            prompt_sistema: El prompt del sistema que define el comportamiento
            imagen_path: Ruta opcional a una imagen para procesamiento multimodal
            
        Returns:
            La respuesta generada como string
        """
        pass
    
    @abstractmethod
    def generar_respuesta_con_functions(self, conversation: List[Dict[str, str]], functions: List[Dict[str, Any]]) -> Any:
        """
        Genera una respuesta con soporte para function calling.
        
        Args:
            conversation: Lista de mensajes de la conversación
            functions: Lista de definiciones de funciones disponibles
            
        Returns:
            El objeto de respuesta completo del proveedor
        """
        pass
    
    @abstractmethod
    def generar_respuesta_desde_contexto(self, conversation: List[Dict[str, str]]) -> str:
        """
        Genera una respuesta basada en el contexto completo de la conversación.
        
        Args:
            conversation: Lista completa de mensajes de la conversación
            
        Returns:
            La respuesta generada como string
        """
        pass
    
    def soporta_vision(self) -> bool:
        """
        Indica si este modelo soporta procesamiento de imágenes.
        Por defecto retorna False, los modelos con visión deben sobrescribir.
        
        Returns:
            True si soporta visión, False en caso contrario
        """
        return False
    
    def generar_respuesta_multimodal(self, mensaje_usuario: str, imagen_path: str, prompt_sistema: str) -> str:
        """
        Genera una respuesta usando tanto texto como imagen.
        Método opcional que pueden implementar modelos con capacidades de visión.
        
        Args:
            mensaje_usuario: El mensaje de texto del usuario
            imagen_path: Ruta al archivo de imagen
            prompt_sistema: El prompt del sistema
            
        Returns:
            La respuesta generada como string
            
        Raises:
            NotImplementedError: Si el modelo no soporta visión
        """
        if not self.soporta_vision():
            raise NotImplementedError(f"El modelo {self.__class__.__name__} no soporta procesamiento de imágenes")
        
        # Por defecto, delegar al método generar_respuesta con imagen_path
        return self.generar_respuesta(mensaje_usuario, prompt_sistema, imagen_path)


