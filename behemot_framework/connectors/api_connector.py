# app/connectors/api_connector.py
import logging
from typing import Dict, Any
from datetime import datetime



logger = logging.getLogger(__name__)

# app/connectors/api_connector.py
class ApiConnector:
    """Conector genérico para recibir y responder mensajes via API."""
    
    def __init__(self):
        pass
    
    def extraer_mensaje(self, data: Dict[str, Any]) -> tuple:
        """
        Extrae el identificador de sesión y el mensaje del payload recibido.
        Args:
            data: Diccionario con los datos recibidos en la API
        Returns:
            tuple: (session_id, mensaje)
        """
        try:
            session_id = data.get("session_id")
            mensaje = data.get("message")
            
            if not session_id or not mensaje:
                logger.warning(f"Payload incompleto: {data}")
                return None, None
            return session_id, mensaje
        except Exception as e:
            logger.error(f"Error al extraer mensaje: {e}")
            return None, None
    
    def preparar_respuesta(self, mensaje: str) -> Dict[str, Any]:
        """
        Prepara la respuesta para enviar al cliente.
        Args:
            mensaje: Texto de respuesta del asistente
        Returns:
            Dict: Respuesta formateada para la API
        """
        return {
            "message": mensaje,
            "timestamp": str(datetime.now().isoformat())
        }
