# behemot_framework/users/user_tracker.py
import logging
import json
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
import redis

logger = logging.getLogger(__name__)

class UserTracker:
    """
    Rastrea usuarios que han interactuado con el bot.
    Almacena información básica para poder enviar mensajes masivos.
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Inicializa el rastreador de usuarios.
        
        Args:
            redis_client: Cliente Redis para persistencia (opcional)
        """
        self.redis_client = redis_client
        self.users_key = "behemot:active_users"
        self.user_data_prefix = "behemot:user:"
        
        # Cache local para cuando no hay Redis
        self.local_users: Set[str] = set()
        self.local_user_data: Dict[str, Dict] = {}
        
    def register_user(self, user_id: str, platform: str, metadata: Optional[Dict] = None) -> bool:
        """
        Registra un usuario que ha interactuado con el bot.
        
        Args:
            user_id: ID único del usuario (chat_id, phone_number, etc.)
            platform: Plataforma del usuario (telegram, whatsapp, api, google_chat)
            metadata: Datos adicionales del usuario (nombre, username, etc.)
            
        Returns:
            bool: True si se registró correctamente
        """
        try:
            user_data = {
                "user_id": user_id,
                "platform": platform,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            if self.redis_client:
                # Guardar en Redis
                self.redis_client.sadd(self.users_key, user_id)
                self.redis_client.hset(
                    f"{self.user_data_prefix}{user_id}",
                    mapping={
                        "data": json.dumps(user_data),
                        "platform": platform
                    }
                )
                # Establecer TTL de 30 días para datos de usuario
                self.redis_client.expire(f"{self.user_data_prefix}{user_id}", 30 * 24 * 60 * 60)
                logger.info(f"✅ Usuario registrado en Redis: {user_id} ({platform})")
            else:
                # Guardar en memoria local
                self.local_users.add(user_id)
                self.local_user_data[user_id] = user_data
                logger.info(f"✅ Usuario registrado localmente: {user_id} ({platform})")
                
            return True
            
        except Exception as e:
            logger.error(f"Error registrando usuario {user_id}: {e}")
            return False
    
    def update_last_seen(self, user_id: str) -> bool:
        """
        Actualiza la última vez que se vio al usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            bool: True si se actualizó correctamente
        """
        try:
            if self.redis_client:
                user_data_key = f"{self.user_data_prefix}{user_id}"
                if self.redis_client.exists(user_data_key):
                    data = json.loads(self.redis_client.hget(user_data_key, "data"))
                    data["last_seen"] = datetime.now().isoformat()
                    self.redis_client.hset(user_data_key, "data", json.dumps(data))
                    # Renovar TTL
                    self.redis_client.expire(user_data_key, 30 * 24 * 60 * 60)
            else:
                if user_id in self.local_user_data:
                    self.local_user_data[user_id]["last_seen"] = datetime.now().isoformat()
                    
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando last_seen para {user_id}: {e}")
            return False
    
    def get_users_by_platform(self, platform: str, active_days: int = 30) -> List[Dict]:
        """
        Obtiene usuarios de una plataforma específica activos en los últimos N días.
        
        Args:
            platform: Nombre de la plataforma (telegram, whatsapp, etc.)
            active_days: Número de días para considerar un usuario activo
            
        Returns:
            Lista de usuarios con su información
        """
        users = []
        cutoff_date = datetime.now() - timedelta(days=active_days)
        
        try:
            if self.redis_client:
                # Obtener todos los usuarios
                all_user_ids = self.redis_client.smembers(self.users_key)
                
                for user_id in all_user_ids:
                    user_id = user_id.decode() if isinstance(user_id, bytes) else user_id
                    user_data_key = f"{self.user_data_prefix}{user_id}"
                    
                    if self.redis_client.exists(user_data_key):
                        platform_data = self.redis_client.hget(user_data_key, "platform")
                        if platform_data:
                            platform_data = platform_data.decode() if isinstance(platform_data, bytes) else platform_data
                            
                            if platform_data == platform:
                                data = self.redis_client.hget(user_data_key, "data")
                                if data:
                                    user_data = json.loads(data)
                                    last_seen = datetime.fromisoformat(user_data["last_seen"])
                                    
                                    if last_seen >= cutoff_date:
                                        users.append(user_data)
            else:
                # Usar datos locales
                for user_id, user_data in self.local_user_data.items():
                    if user_data["platform"] == platform:
                        last_seen = datetime.fromisoformat(user_data["last_seen"])
                        if last_seen >= cutoff_date:
                            users.append(user_data)
                            
            logger.info(f"📊 Encontrados {len(users)} usuarios activos en {platform}")
            return users
            
        except Exception as e:
            logger.error(f"Error obteniendo usuarios de {platform}: {e}")
            return []
    
    def get_all_active_users(self, active_days: int = 30) -> Dict[str, List[Dict]]:
        """
        Obtiene todos los usuarios activos agrupados por plataforma.
        
        Args:
            active_days: Número de días para considerar un usuario activo
            
        Returns:
            Diccionario con usuarios agrupados por plataforma
        """
        platforms = ["telegram", "whatsapp", "api", "google_chat"]
        result = {}
        
        for platform in platforms:
            users = self.get_users_by_platform(platform, active_days)
            if users:
                result[platform] = users
                
        return result
    
    def remove_user(self, user_id: str) -> bool:
        """
        Elimina un usuario del registro.
        
        Args:
            user_id: ID del usuario a eliminar
            
        Returns:
            bool: True si se eliminó correctamente
        """
        try:
            if self.redis_client:
                self.redis_client.srem(self.users_key, user_id)
                self.redis_client.delete(f"{self.user_data_prefix}{user_id}")
            else:
                self.local_users.discard(user_id)
                self.local_user_data.pop(user_id, None)
                
            logger.info(f"🗑️ Usuario eliminado: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando usuario {user_id}: {e}")
            return False


# Instancia global del tracker
_user_tracker: Optional[UserTracker] = None

def get_user_tracker(redis_client: Optional[redis.Redis] = None) -> UserTracker:
    """
    Obtiene la instancia global del UserTracker.
    
    Args:
        redis_client: Cliente Redis (solo necesario en la primera llamada)
        
    Returns:
        UserTracker: Instancia del rastreador
    """
    global _user_tracker
    
    if _user_tracker is None:
        _user_tracker = UserTracker(redis_client)
        
    return _user_tracker