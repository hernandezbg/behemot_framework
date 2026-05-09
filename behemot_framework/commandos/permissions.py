# behemot_framework/commandos/permissions.py
import logging
from typing import Dict, List, Optional, Set
from behemot_framework.config import Config

logger = logging.getLogger(__name__)

class PermissionManager:
    """
    Gestiona permisos de usuarios para comandos administrativos.
    """
    
    # Definición de permisos y comandos asociados.
    # `rag` solo concede búsqueda y consulta; `rag_admin` añade reindexación —
    # esta operación puede ingerir nuevas fuentes y se separó para minimizar
    # superficie ante prompt injection / abuso de comandos.
    PERMISSION_GROUPS = {
        "user_info": ["whoami"],
        "broadcast": ["sendmsg", "list_users"],
        "user_management": ["delete_session", "list_sessions", "analyze_session"],
        "system": ["status", "monitor", "reset_to_fabric", "clear_msg"],
        "rag": ["rag_status", "rag_search", "rag_collections"],
        "rag_admin": ["reindex_rag"],
        "super_admin": ["*"]  # Acceso a todos los comandos
    }
    
    def __init__(self):
        """
        Inicializa el gestor de permisos.
        """
        self.config = Config.get_config()
        # Default seguro: production. En "dev" NO se conceden permisos automáticos:
        # solo permite logs adicionales y omitir validaciones no relacionadas con
        # autorización. Para que un usuario sea admin debe estar en ADMIN_USERS.
        self.admin_mode = self.config.get("ADMIN_MODE", "production").lower()
        self.admin_users = self._load_admin_users()

        logger.info(f"🔐 PermissionManager inicializado en modo: {self.admin_mode}")
        if self.admin_users:
            logger.info(f"👥 {len(self.admin_users)} administradores configurados")
        elif self.admin_mode == "dev":
            logger.warning(
                "⚠️  ADMIN_MODE='dev' sin ADMIN_USERS configurados: ningún usuario "
                "podrá ejecutar comandos administrativos. Añade ADMIN_USERS al "
                "config para habilitar admins."
            )
        else:
            logger.warning(
                "⚠️  ADMIN_MODE='production' sin ADMIN_USERS configurados: los "
                "comandos administrativos quedan deshabilitados (comportamiento seguro)."
            )
    
    def _load_admin_users(self) -> Dict[str, Dict]:
        """
        Carga la configuración de usuarios administradores.
        
        Returns:
            Dict con usuarios admin y sus permisos
        """
        admin_users_config = self.config.get("ADMIN_USERS", [])
        admin_users = {}
        
        if isinstance(admin_users_config, list):
            for user_config in admin_users_config:
                if isinstance(user_config, dict):
                    user_id = user_config.get("user_id")
                    platform = user_config.get("platform", "any")
                    permissions = user_config.get("permissions", [])
                    
                    if user_id:
                        key = f"{user_id}:{platform}"
                        admin_users[key] = {
                            "user_id": user_id,
                            "platform": platform,
                            "permissions": permissions
                        }
                        logger.info(f"👤 Admin configurado: {user_id} ({platform}) - Permisos: {permissions}")
        
        return admin_users
    
    def is_admin(self, user_id: str, platform: str = "any") -> bool:
        """
        Verifica si un usuario es administrador.

        El privilegio se concede ÚNICAMENTE si el usuario está listado en
        ADMIN_USERS. El antiguo bypass por `admin_mode == "dev"` se eliminó por
        seguridad: dejaba super_admin abierto a cualquiera por defecto.

        Args:
            user_id: ID del usuario
            platform: Plataforma del usuario

        Returns:
            True si es administrador
        """
        # Buscar en configuración específica
        keys_to_check = [
            f"{user_id}:{platform}",  # Específico de plataforma
            f"{user_id}:any"          # Cualquier plataforma
        ]

        for key in keys_to_check:
            if key in self.admin_users:
                logger.debug(f"✅ {user_id} encontrado como admin: {key}")
                return True

        logger.debug(f"❌ {user_id} no es administrador")
        return False
    
    def get_user_permissions(self, user_id: str, platform: str = "any") -> List[str]:
        """
        Obtiene los permisos de un usuario.

        El bypass de "todos super_admin en modo dev" se eliminó. Los permisos
        provienen exclusivamente de la lista ADMIN_USERS.

        Args:
            user_id: ID del usuario
            platform: Plataforma del usuario

        Returns:
            Lista de permisos del usuario
        """
        # Si no es admin, solo permisos básicos
        if not self.is_admin(user_id, platform):
            return ["user_info"]  # Solo puede ver su propia información
        
        # Buscar permisos específicos
        keys_to_check = [
            f"{user_id}:{platform}",
            f"{user_id}:any"
        ]
        
        for key in keys_to_check:
            if key in self.admin_users:
                permissions = self.admin_users[key]["permissions"]
                logger.debug(f"📋 Permisos para {user_id}: {permissions}")
                return permissions
        
        # Si es admin pero no tiene permisos específicos, dar permisos básicos de admin
        return ["user_info", "broadcast"]
    
    def has_permission(self, user_id: str, command: str, platform: str = "any") -> bool:
        """
        Verifica si un usuario tiene permiso para ejecutar un comando.
        
        Args:
            user_id: ID del usuario
            command: Nombre del comando
            platform: Plataforma del usuario
            
        Returns:
            True si tiene permiso
        """
        user_permissions = self.get_user_permissions(user_id, platform)
        
        # Super admin puede hacer todo
        if "super_admin" in user_permissions:
            logger.debug(f"🔑 {user_id} tiene super_admin - comando '{command}' permitido")
            return True
        
        # Verificar si el comando está en algún grupo de permisos del usuario
        for permission in user_permissions:
            if permission in self.PERMISSION_GROUPS:
                allowed_commands = self.PERMISSION_GROUPS[permission]
                if command in allowed_commands or "*" in allowed_commands:
                    logger.debug(f"✅ {user_id} tiene permiso '{permission}' para comando '{command}'")
                    return True
        
        logger.debug(f"❌ {user_id} NO tiene permiso para comando '{command}'")
        return False
    
    def get_available_commands(self, user_id: str, platform: str = "any") -> List[str]:
        """
        Obtiene la lista de comandos disponibles para un usuario.
        
        Args:
            user_id: ID del usuario
            platform: Plataforma del usuario
            
        Returns:
            Lista de comandos disponibles
        """
        user_permissions = self.get_user_permissions(user_id, platform)
        available_commands = set()
        
        for permission in user_permissions:
            if permission in self.PERMISSION_GROUPS:
                commands = self.PERMISSION_GROUPS[permission]
                if "*" in commands:
                    # Super admin - todos los comandos
                    for perm_group in self.PERMISSION_GROUPS.values():
                        available_commands.update(cmd for cmd in perm_group if cmd != "*")
                else:
                    available_commands.update(commands)
        
        return sorted(list(available_commands))
    
    def get_permission_info(self, user_id: str, platform: str = "any") -> Dict:
        """
        Obtiene información completa de permisos para un usuario.
        
        Args:
            user_id: ID del usuario
            platform: Plataforma del usuario
            
        Returns:
            Dict con información de permisos
        """
        user_permissions = self.get_user_permissions(user_id, platform)
        available_commands = self.get_available_commands(user_id, platform)
        
        # Información detallada de permisos
        permission_details = {}
        for permission in ["user_info", "broadcast", "user_management", "system", "rag", "rag_admin", "super_admin"]:
            has_perm = permission in user_permissions
            commands = self.PERMISSION_GROUPS.get(permission, [])
            permission_details[permission] = {
                "has_permission": has_perm,
                "commands": commands,
                "description": self._get_permission_description(permission)
            }
        
        return {
            "is_admin": self.is_admin(user_id, platform),
            "admin_mode": self.admin_mode,
            "permissions": user_permissions,
            "available_commands": available_commands,
            "permission_details": permission_details
        }
    
    def _get_permission_description(self, permission: str) -> str:
        """
        Obtiene la descripción de un permiso.
        
        Args:
            permission: Nombre del permiso
            
        Returns:
            Descripción del permiso
        """
        descriptions = {
            "user_info": "Puede ver su propia información",
            "broadcast": "Puede enviar mensajes masivos",
            "user_management": "Puede gestionar usuarios y sesiones",
            "system": "Puede acceder a comandos de sistema",
            "rag": "Puede consultar el sistema RAG (búsqueda, estado, colecciones)",
            "rag_admin": "Puede reindexar el sistema RAG (ingesta de fuentes)",
            "super_admin": "Acceso completo a todos los comandos"
        }
        return descriptions.get(permission, "Permiso desconocido")


# Instancia global del gestor de permisos
_permission_manager: Optional[PermissionManager] = None

def get_permission_manager() -> PermissionManager:
    """
    Obtiene la instancia global del PermissionManager.
    
    Returns:
        PermissionManager: Instancia del gestor de permisos
    """
    global _permission_manager
    
    if _permission_manager is None:
        _permission_manager = PermissionManager()
        
    return _permission_manager

def require_permission(permission: str):
    """
    Decorador para comandos que requieren permisos específicos.
    
    Args:
        permission: Permiso requerido
    """
    def decorator(func):
        # Agregar metadatos de permiso a la función
        func._required_permission = permission
        return func
    return decorator