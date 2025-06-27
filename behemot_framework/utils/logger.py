# app/utils/logger.py
import logging

# Configuración básica del logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Obtener un logger para el módulo actual
logger = logging.getLogger(__name__)

# Ejemplo de uso:
# logger.info("Este es un mensaje informativo.")
# logger.warning("Esta es una advertencia.")
# logger.error("Este es un error.")
# logger.debug("Este es un mensaje de depuración.")

# Puedes obtener loggers para otros módulos de la misma manera:
# from behemot_framework.utils.logger import logger as my_module_logger
# my_module_logger.info("Mensaje desde mi módulo.")
