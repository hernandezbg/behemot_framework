# morphing/instant_triggers.py
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class MorphDecision:
    """Representa una decisión de transformación"""
    def __init__(self, morph_name: str, confidence: float, reason: str = ""):
        self.morph_name = morph_name
        self.confidence = confidence
        self.reason = reason

class InstantMorphTriggers:
    """
    Capa 1: Detección instantánea de cambios de morph basada en triggers simples.
    Esta es la capa más rápida (0ms) que detecta cambios obvios.
    """
    
    def __init__(self, morphs_config: Dict[str, Any]):
        """
        Inicializo con la configuración de morphs del YAML.
        Solo extraigo los instant_triggers de cada morph.
        """
        self.morphs_triggers = {}
        
        # Extraigo los instant_triggers de cada morph
        for morph_name, morph_config in morphs_config.items():
            instant_triggers = morph_config.get('instant_triggers', [])
            if instant_triggers:
                # Convierto todo a lowercase para matching case-insensitive
                self.morphs_triggers[morph_name] = [
                    trigger.lower() for trigger in instant_triggers
                ]
                logger.info(f"📢 Morph '{morph_name}' configurado con {len(instant_triggers)} instant triggers")
    
    def check(self, user_input: str, current_morph: str = "general") -> Optional[MorphDecision]:
        """
        Verifico si el input del usuario contiene algún trigger instantáneo.
        Retorno MorphDecision si encuentro un match, None si no.
        """
        if not user_input:
            return None
            
        # Convierto input a lowercase para matching
        input_lower = user_input.lower()
        
        # Reviso cada morph para ver si tiene triggers que matcheen
        for morph_name, triggers in self.morphs_triggers.items():
            # No sugiero cambiar al mismo morph que ya está activo
            if morph_name == current_morph:
                continue
                
            # Busco si algún trigger está presente en el input
            for trigger in triggers:
                if trigger in input_lower:
                    logger.info(f"🎯 Instant trigger detectado: '{trigger}' → {morph_name}")
                    return MorphDecision(
                        morph_name=morph_name,
                        confidence=1.0,  # Los instant triggers tienen máxima confianza
                        reason=f"Trigger instantáneo: '{trigger}'"
                    )
        
        # No encontré ningún trigger
        return None
    
    def get_available_morphs(self) -> List[str]:
        """Retorno lista de morphs que tienen instant triggers configurados"""
        return list(self.morphs_triggers.keys())
    
    def get_triggers_for_morph(self, morph_name: str) -> List[str]:
        """Retorno los triggers de un morph específico (para debugging)"""
        return self.morphs_triggers.get(morph_name, [])