# behemot_framework/commandos/admin_commands.py
import logging
import re
import asyncio
from typing import Dict, List, Optional, Tuple
from behemot_framework.users import get_user_tracker

logger = logging.getLogger(__name__)

class AdminCommands:
    """
    Maneja comandos de administración como envío de mensajes masivos.
    """
    
    def __init__(self, factory=None):
        """
        Inicializa los comandos de administración.
        
        Args:
            factory: Instancia de BehemotFactory para acceso a conectores
        """
        self.factory = factory
        self.user_tracker = get_user_tracker()
        
        # Lista de usuarios administradores (puedes configurar esto)
        self.admin_users = set()  # Se puede configurar desde variables de entorno
        
    def is_admin_user(self, user_id: str) -> bool:
        """
        Verifica si un usuario es administrador.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            bool: True si es administrador
        """
        # Por ahora, cualquier usuario puede usar comandos admin
        # En el futuro se puede implementar un sistema de permisos
        return True
        
    def parse_sendmsg_command(self, message: str) -> Optional[Tuple[str, str]]:
        """
        Parsea el comando &sendmsg.
        
        Args:
            message: Mensaje completo del usuario
            
        Returns:
            Tupla (comando, mensaje) o None si no es válido
        """
        # Patrón: &sendmsg "mensaje" o &sendmsg mensaje
        patterns = [
            r'^&sendmsg\s+"([^"]+)"',  # Con comillas
            r'^&sendmsg\s+(.+)',       # Sin comillas
        ]
        
        for pattern in patterns:
            match = re.match(pattern, message.strip(), re.IGNORECASE)
            if match:
                return ("sendmsg", match.group(1).strip())
                
        return None
    
    async def execute_sendmsg(self, admin_user_id: str, broadcast_message: str, target_platform: Optional[str] = None) -> Dict:
        """
        Ejecuta el comando de envío masivo.
        
        Args:
            admin_user_id: ID del usuario administrador que ejecuta el comando
            broadcast_message: Mensaje a enviar
            target_platform: Plataforma específica (opcional)
            
        Returns:
            Dict con resultado de la operación
        """
        if not self.is_admin_user(admin_user_id):
            return {
                "success": False,
                "message": "❌ No tienes permisos para ejecutar este comando",
                "sent_count": 0
            }
            
        try:
            # Obtener usuarios activos
            if target_platform:
                users_by_platform = {target_platform: self.user_tracker.get_users_by_platform(target_platform)}
            else:
                users_by_platform = self.user_tracker.get_all_active_users()
            
            total_users = sum(len(users) for users in users_by_platform.values())
            
            if total_users == 0:
                return {
                    "success": False,
                    "message": "📭 No hay usuarios activos para enviar mensajes",
                    "sent_count": 0
                }
            
            # Preparar mensaje de broadcast
            broadcast_text = f"📢 **Mensaje del administrador:**\n\n{broadcast_message}"
            
            sent_count = 0
            failed_count = 0
            results = {}
            
            # Enviar a cada plataforma
            for platform, users in users_by_platform.items():
                platform_sent = 0
                platform_failed = 0
                
                logger.info(f"📤 Enviando mensaje a {len(users)} usuarios de {platform}")
                
                for user in users:
                    user_id = user["user_id"]
                    
                    try:
                        success = await self._send_to_platform(platform, user_id, broadcast_text)
                        
                        if success:
                            platform_sent += 1
                            sent_count += 1
                        else:
                            platform_failed += 1
                            failed_count += 1
                            
                        # Pequeña pausa para evitar rate limiting
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        logger.error(f"Error enviando mensaje a {user_id} en {platform}: {e}")
                        platform_failed += 1
                        failed_count += 1
                
                results[platform] = {
                    "sent": platform_sent,
                    "failed": platform_failed
                }
                
                logger.info(f"✅ {platform}: {platform_sent} enviados, {platform_failed} fallidos")
            
            # Preparar mensaje de resultado
            result_message = f"📊 **Resultado del envío masivo:**\n\n"
            result_message += f"✅ Mensajes enviados: {sent_count}\n"
            
            if failed_count > 0:
                result_message += f"❌ Mensajes fallidos: {failed_count}\n"
            
            result_message += f"\n**Detalle por plataforma:**\n"
            for platform, stats in results.items():
                result_message += f"• {platform.title()}: {stats['sent']} ✅"
                if stats['failed'] > 0:
                    result_message += f", {stats['failed']} ❌"
                result_message += "\n"
            
            return {
                "success": True,
                "message": result_message,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error ejecutando sendmsg: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"❌ Error interno: {str(e)}",
                "sent_count": 0
            }
    
    async def _send_to_platform(self, platform: str, user_id: str, message: str) -> bool:
        """
        Envía un mensaje a una plataforma específica.
        
        Args:
            platform: Nombre de la plataforma
            user_id: ID del usuario
            message: Mensaje a enviar
            
        Returns:
            bool: True si se envió correctamente
        """
        try:
            if not self.factory:
                logger.warning("Factory no disponible para envío")
                return False
                
            if platform == "telegram" and hasattr(self.factory, 'telegram_connector') and self.factory.telegram_connector:
                # Enviar vía Telegram
                self.factory.telegram_connector.enviar_mensaje(user_id, message)
                return True
                
            elif platform == "whatsapp" and hasattr(self.factory, 'whatsapp_connector') and self.factory.whatsapp_connector:
                # Enviar vía WhatsApp
                await self.factory.whatsapp_connector.enviar_mensaje(user_id, message)
                return True
                
            elif platform == "google_chat" and hasattr(self.factory, 'google_chat_connector') and self.factory.google_chat_connector:
                # Google Chat requiere un space específico, más complejo
                logger.warning(f"Google Chat broadcast no implementado aún para {user_id}")
                return False
                
            elif platform == "api":
                # API REST no puede enviar mensajes proactivos por naturaleza
                logger.warning(f"API REST no soporta mensajes proactivos para {user_id}")
                return False
                
            else:
                logger.warning(f"Plataforma {platform} no disponible o no configurada")
                return False
                
        except Exception as e:
            logger.error(f"Error enviando a {platform}:{user_id}: {e}")
            return False


# Instancia global
_admin_commands: Optional[AdminCommands] = None

def get_admin_commands(factory=None) -> AdminCommands:
    """
    Obtiene la instancia global de AdminCommands.
    
    Args:
        factory: Instancia de BehemotFactory (solo necesario en la primera llamada)
        
    Returns:
        AdminCommands: Instancia de comandos de administración
    """
    global _admin_commands
    
    if _admin_commands is None:
        _admin_commands = AdminCommands(factory)
    elif factory and not _admin_commands.factory:
        _admin_commands.factory = factory
        
    return _admin_commands