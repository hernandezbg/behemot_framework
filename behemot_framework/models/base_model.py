# models/base_model.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any


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
    def generar_respuesta(self, mensaje_usuario: str, prompt_sistema: str) -> str:
        """
        Genera una respuesta simple sin contexto de conversación.
        
        Args:
            mensaje_usuario: El mensaje del usuario
            prompt_sistema: El prompt del sistema que define el comportamiento
            
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


