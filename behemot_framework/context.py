# app/context.py
import redis
import json
from behemot_framework.config import Config

 
 
REDIS_PUBLIC_URL = Config.get("REDIS_PUBLIC_URL")

# Conexión a Redis usando la URL de conexión
redis_client = redis.from_url(REDIS_PUBLIC_URL, decode_responses=True)

def get_conversation(chat_id: str):
    """Recupera el historial de mensajes para un chat dado."""
    data = redis_client.get(f"chat:{chat_id}")
    if data:
        return json.loads(data)
    return []  # Si no hay historial, devuelve una lista vacía

def save_conversation(chat_id: str, conversation: list):
    """Guarda el historial de mensajes en Redis."""
    redis_client.set(f"chat:{chat_id}", json.dumps(conversation))
