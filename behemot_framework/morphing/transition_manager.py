# morphing/transition_manager.py
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class TransitionManager:
    """
    Gestor de transiciones entre morphs.
    En esta versión básica, me enfoco en hacer transiciones suaves y silenciosas.
    """
    
    def __init__(self, transition_style: str = "seamless"):
        """
        Inicializo el gestor de transiciones.
        
        Args:
            transition_style: Estilo de transición ("seamless" por defecto)
        """
        self.transition_style = transition_style
        logger.info(f"🔄 TransitionManager inicializado con estilo: {transition_style}")
    
    def prepare_transition(self, from_morph: str, to_morph: str, reason: str) -> Dict[str, Any]:
        """
        Preparo la transición entre morphs.
        Retorno información sobre cómo debe manejarse la transición.
        """
        logger.info(f"🎭 Preparando transición: {from_morph} → {to_morph} (razón: {reason})")
        
        transition_info = {
            'from_morph': from_morph,
            'to_morph': to_morph,
            'reason': reason,
            'should_acknowledge': self._should_acknowledge_transition(from_morph, to_morph),
            'continuity_phrase': self._generate_continuity_phrase(from_morph, to_morph),
            'transition_type': 'seamless'  # Por ahora siempre seamless
        }
        
        return transition_info
    
    def _should_acknowledge_transition(self, from_morph: str, to_morph: str) -> bool:
        """
        Determino si la transición debe ser reconocida explícitamente.
        Para la versión básica, mantengo todo silencioso.
        """
        if self.transition_style == "acknowledged":
            return True
        
        # Para seamless, no reconozco transiciones
        return False
    
    def _generate_continuity_phrase(self, from_morph: str, to_morph: str) -> Optional[str]:
        """
        Genero una frase de continuidad para la transición.
        En la versión básica, uso frases simples y genéricas.
        """
        if self.transition_style != "seamless":
            return None
        
        # Mapeo simple de morphs a frases de transición
        transition_phrases = {
            'sales': 'Perfecto, te ayudo a encontrar lo que buscas.',
            'support': 'Entiendo, vamos a resolver esto paso a paso.',
            'creative': 'Excelente, exploremos algunas ideas creativas.',
            'general': 'Por supuesto, estoy aquí para ayudarte.'
        }
        
        phrase = transition_phrases.get(to_morph)
        if phrase:
            logger.info(f"💬 Frase de continuidad generada para {to_morph}: {phrase[:30]}...")
        
        return phrase
    
    def execute_transition(self, transition_info: Dict[str, Any], preserved_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuto la transición usando la información preparada y el estado preservado.
        Retorno el contexto final para el nuevo morph.
        """
        from_morph = transition_info['from_morph']
        to_morph = transition_info['to_morph']
        
        logger.info(f"⚡ Ejecutando transición: {from_morph} → {to_morph}")
        
        # Preparo el contexto para el nuevo morph
        new_morph_context = {
            'conversation': preserved_state.get('conversation_history', []),
            'continuity_phrase': transition_info.get('continuity_phrase'),
            'should_acknowledge': transition_info.get('should_acknowledge', False),
            'transition_reason': transition_info.get('reason', ''),
            'previous_morph': from_morph,
            'current_morph': to_morph
        }
        
        logger.info(f"✅ Transición ejecutada exitosamente a '{to_morph}'")
        return new_morph_context