# app/commandos/__init__.py

# Importar command_handler para registrar la decoración de comandos
from behemot_framework.commandos.command_handler import command, CommandHandler

# Importar system_status para funciones de verificación del sistema
from behemot_framework.commandos.system_status import (
    check_redis,
    check_rag,
    check_model,
    check_config,
    check_tools,
    get_performance_metrics,
    get_memory_usage,
    BEHEMOT_START_TIME
)

# Importar módulos de monitoreo y análisis de sesiones
import behemot_framework.commandos.system_monitor
from . import session_analyzer

# Importar comandos RAG
from . import rag_commands

# Importar comandos definidos
from behemot_framework.commandos.command_handler import (
    clear_messages,
    help_command,
    enhanced_status_command,
    reset_to_fabric_command,
    delete_session_command,
    list_sessions_command,
    monitor_command,
    analyze_session_command
)

__all__ = [
    'command',
    'CommandHandler',
    'clear_messages',
    'help_command',
    'enhanced_status_command',
    'reset_to_fabric_command',
    'delete_session_command',
    'list_sessions_command',
    'monitor_command',
    'analyze_session_command',
    'check_redis',
    'check_rag',
    'check_model',
    'check_config',
    'check_tools',
    'get_performance_metrics'
]
