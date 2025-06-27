# app/core/tools/date_tools.py
import logging
from datetime import datetime, timedelta
from behemot_framework.tooling import tool, Param

logger = logging.getLogger(__name__)

@tool(name="get_current_date", description="Obtiene la fecha y hora actuales", params=[])
async def get_current_date(params: dict) -> str:
    """Obtiene la fecha y hora actuales del sistema"""
    try:
        now = datetime.now()
        weekday = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][now.weekday()]
        month = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", 
                 "agosto", "septiembre", "octubre", "noviembre", "diciembre"][now.month - 1]
        
        return f"""Fecha actual: {now.strftime('%Y-%m-%d')}
Hora actual: {now.strftime('%H:%M:%S')}
Día de la semana: {weekday.capitalize()}
Fecha en formato largo: {weekday.capitalize()}, {now.day} de {month} de {now.year}"""
    
    except Exception as e:
        logger.error(f"Error al obtener fecha actual: {e}")
        return f"Error al obtener la fecha actual: {str(e)}"

@tool(name="parse_relative_date", description="Convierte una expresión de fecha relativa a formato YYYY-MM-DD", params=[
    Param(name="expression", type_="string", description="Expresión de fecha como 'mañana', 'próximo lunes', etc.", required=True)
])
async def parse_relative_date(params: dict) -> str:
    """Convierte expresiones de fecha relativas a formato YYYY-MM-DD"""
    try:
        expression = params.get("expression", "").lower().strip()
        today = datetime.now()
        
        # Mapeo de nombres de días a números (0=lunes, 6=domingo)
        days = {
            "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, 
            "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6
        }
        
        # Expresiones relativas simples
        if expression == "hoy":
            date = today
        elif expression == "mañana" or expression == "manana":
            date = today + timedelta(days=1)
        elif expression == "pasado mañana" or expression == "pasado manana":
            date = today + timedelta(days=2)
        elif "próximo" in expression or "proximo" in expression or "siguiente" in expression or "que viene" in expression:
            # Buscar el día de la semana mencionado
            for day_name, day_num in days.items():
                if day_name in expression:
                    # Calcular días hasta el próximo día mencionado
                    days_until = (day_num - today.weekday()) % 7
                    if days_until == 0:  # Si es hoy, ir a la próxima semana
                        days_until = 7
                    date = today + timedelta(days=days_until)
                    break
            else:
                return f"No pude entender la expresión de fecha: {expression}"
        elif "este" in expression or "esta" in expression:
            # Buscar el día de la semana mencionado
            for day_name, day_num in days.items():
                if day_name in expression:
                    # Calcular días hasta el día mencionado en esta semana
                    days_until = (day_num - today.weekday()) % 7
                    date = today + timedelta(days=days_until)
                    break
            else:
                return f"No pude entender la expresión de fecha: {expression}"
        else:
            # Verificar si la expresión ya es una fecha en formato YYYY-MM-DD
            try:
                date = datetime.strptime(expression, "%Y-%m-%d")
            except ValueError:
                return f"No pude convertir la expresión a una fecha válida: {expression}"
        
        # Información de la fecha calculada
        weekday = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][date.weekday()]
        month = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", 
                "agosto", "septiembre", "octubre", "noviembre", "diciembre"][date.month - 1]
        
        return f"""Fecha calculada: {date.strftime('%Y-%m-%d')}
Día de la semana: {weekday.capitalize()}
Fecha en formato largo: {weekday.capitalize()}, {date.day} de {month} de {date.year}"""
        
    except Exception as e:
        logger.error(f"Error al analizar fecha relativa: {e}")
        return f"Error al procesar la expresión de fecha: {str(e)}"
