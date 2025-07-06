# morphing/state_manager.py
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class MorphStateManager:
    """
    Gestor de estado que preserva información entre transformaciones de morph.
    En esta versión básica, solo mantengo el contexto esencial de la conversación.
    """
    
    def __init__(self):
        """Inicializo el gestor de estado"""
        logger.info("🔄 MorphStateManager inicializado")
    
    def preserve_state(self, conversation: List[Dict[str, str]], current_morph: str) -> Dict[str, Any]:
        """
        Preservo el estado actual antes de cambiar de morph.
        Por ahora solo guardo lo esencial para mantener la continuidad.
        """
        logger.info(f"💾 Preservando estado del morph '{current_morph}'")
        
        # Extraigo información clave de la conversación
        preserved_state = {
            'conversation_history': conversation.copy(),  # Toda la conversación
            'current_morph': current_morph,
            'conversation_length': len(conversation),
            'last_user_message': self._get_last_user_message(conversation),
            'conversation_summary': self._create_simple_summary(conversation)
        }
        
        logger.info(f"✅ Estado preservado: {preserved_state['conversation_length']} mensajes")
        return preserved_state
    
    def restore_state(self, preserved_state: Dict[str, Any], new_morph_name: str) -> Dict[str, Any]:
        """
        Restauro el estado para el nuevo morph.
        Retorno información que el nuevo morph puede usar para mantener continuidad.
        """
        logger.info(f"🔄 Restaurando estado para morph '{new_morph_name}'")
        
        # Preparo el contexto para el nuevo morph
        context_for_new_morph = {
            'conversation': preserved_state.get('conversation_history', []),
            'previous_morph': preserved_state.get('current_morph', 'unknown'),
            'last_user_message': preserved_state.get('last_user_message', ''),
            'summary': preserved_state.get('conversation_summary', ''),
            'should_acknowledge_transition': self._should_acknowledge_transition(
                preserved_state.get('current_morph'), new_morph_name
            )
        }
        
        logger.info(f"✅ Estado restaurado para '{new_morph_name}'")
        return context_for_new_morph
    
    def _get_last_user_message(self, conversation: List[Dict[str, str]]) -> str:
        """Extraigo el último mensaje del usuario"""
        for message in reversed(conversation):
            if message.get('role') == 'user':
                return message.get('content', '')
        return ''
    
    def _create_simple_summary(self, conversation: List[Dict[str, str]]) -> str:
        """
        Creo un resumen muy simple de la conversación.
        Por ahora solo tomo los últimos mensajes relevantes.
        """
        if len(conversation) <= 2:
            return "Conversación inicial"
        
        # Tomo los últimos mensajes para el contexto
        recent_messages = conversation[-3:]  # Últimos 3 mensajes
        summary_parts = []
        
        for msg in recent_messages:
            role = msg.get('role', '')
            content = msg.get('content', '')[:50]  # Primeros 50 chars
            if role == 'user':
                summary_parts.append(f"Usuario: {content}...")
            elif role == 'assistant':
                summary_parts.append(f"Asistente: {content}...")
        
        return " | ".join(summary_parts)
    
    def _should_acknowledge_transition(self, from_morph: Optional[str], to_morph: str) -> bool:
        """
        Determino si el cambio de morph debe ser reconocido explícitamente.
        Por ahora, mantengo todas las transiciones silenciosas para simplicidad.
        """
        # Para la versión básica, siempre transiciones silenciosas
        return False