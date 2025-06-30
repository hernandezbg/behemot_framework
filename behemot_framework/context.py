# app/context.py
import redis
import json
import logging
from behemot_framework.config import Config

logger = logging.getLogger(__name__)
 
REDIS_PUBLIC_URL = Config.get("REDIS_PUBLIC_URL")

# Conexión a Redis usando la URL de conexión
try:
    redis_client = redis.from_url(REDIS_PUBLIC_URL, decode_responses=True)
    # Probar la conexión
    redis_client.ping()
    logger.info(f"✅ Conexión a Redis exitosa: {REDIS_PUBLIC_URL}")
except Exception as e:
    logger.error(f"❌ Error conectando a Redis: {e}")
    redis_client = None

def get_conversation(chat_id: str):
    """Recupera el historial de mensajes para un chat dado."""
    if not redis_client:
        logger.warning("Redis no disponible, retornando conversación vacía")
        return []
    
    try:
        data = redis_client.get(f"chat:{chat_id}")
        if data:
            logger.info(f"📥 Conversación recuperada para {chat_id}: {len(data)} caracteres")
            return json.loads(data)
        else:
            logger.info(f"📭 No hay conversación previa para {chat_id}")
        return []  # Si no hay historial, devuelve una lista vacía
    except Exception as e:
        logger.error(f"❌ Error recuperando conversación para {chat_id}: {e}")
        return []

def save_conversation(chat_id: str, conversation: list):
    """Guarda el historial de mensajes en Redis."""
    if not redis_client:
        logger.warning("Redis no disponible, no se puede guardar conversación")
        return False
    
    try:
        data = json.dumps(conversation)
        redis_client.set(f"chat:{chat_id}", data)
        logger.info(f"💾 Conversación guardada para {chat_id}: {len(conversation)} mensajes, {len(data)} caracteres")
        return True
    except Exception as e:
        logger.error(f"❌ Error guardando conversación para {chat_id}: {e}")
        return False

def redis_diagnostics():
    """Función de diagnóstico para validar Redis."""
    results = {
        "redis_url": REDIS_PUBLIC_URL,
        "connection_status": False,
        "can_write": False,
        "can_read": False,
        "test_key": "behemot:test"
    }
    
    if not redis_client:
        results["error"] = "Cliente Redis no inicializado"
        return results
    
    try:
        # Probar conexión
        redis_client.ping()
        results["connection_status"] = True
        
        # Probar escritura
        test_value = {"test": "data", "timestamp": "2025-06-30"}
        redis_client.set(results["test_key"], json.dumps(test_value))
        results["can_write"] = True
        
        # Probar lectura
        retrieved = redis_client.get(results["test_key"])
        if retrieved and json.loads(retrieved) == test_value:
            results["can_read"] = True
        
        # Limpiar
        redis_client.delete(results["test_key"])
        
    except Exception as e:
        results["error"] = str(e)
    
    return results
