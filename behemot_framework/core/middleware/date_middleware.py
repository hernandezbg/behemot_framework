# app/core/middleware/date_middleware.py
import logging
import re
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class DateMiddleware:
    """Middleware para inyectar la fecha y hora actuales en las conversaciones"""
    
    @staticmethod
    def inject_current_date(conversation: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Inyecta la fecha y hora actuales en el mensaje del sistema.
        """
        # Fecha actual formateada
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_weekday = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][datetime.now().weekday()]
        date_info = f"La fecha actual es: {current_date} ({current_weekday}). La hora actual es: {current_datetime.split()[1]}.";
        
        # Buscar y modificar el mensaje del sistema
        for message in conversation:
            if message.get("role") == "system":
                content = message.get("content", "")
                
                # Buscar y actualizar información de fecha existente
                date_pattern = r"La fecha actual es:.*?La hora actual es:.*\."
                
                if "La fecha actual es:" in content:
                    # Actualizar la fecha existente
                    message["content"] = re.sub(date_pattern, date_info, content)
                else:
                    # Añadir al inicio si no existe
                    message["content"] = date_info + "\n\n" + content
                break
        
        return conversation
