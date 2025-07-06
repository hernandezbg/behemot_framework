# morphing/morphing_manager.py
import logging
from typing import Dict, Any, Optional, List
from .instant_triggers import InstantMorphTriggers, MorphDecision
from .gradual_analyzer import GradualMorphAnalyzer
from .state_manager import MorphStateManager
from .transition_manager import TransitionManager
from .metrics import morph_metrics

logger = logging.getLogger(__name__)

class MorphingManager:
    """
    Coordinador principal del sistema de morphing.
    En esta versión básica (Fase 1), solo manejo la Capa 1 (Instant Triggers).
    """
    
    def __init__(self, morphing_config: Dict[str, Any]):
        """
        Inicializo el sistema de morphing con la configuración del YAML.
        
        Args:
            morphing_config: Configuración completa de MORPHING desde el YAML
        """
        self.config = morphing_config
        self.enabled = morphing_config.get('enabled', False)
        
        if not self.enabled:
            logger.info("🚫 Morphing está deshabilitado en la configuración")
            return
        
        # Extraigo configuraciones básicas
        self.default_morph = morphing_config.get('default_morph', 'general')
        self.morphs_config = morphing_config.get('morphs', {})
        
        # Configuración de comportamiento
        settings = morphing_config.get('settings', {})
        self.transition_style = settings.get('transition_style', 'seamless')
        
        # Inicializo componentes
        self.instant_triggers = InstantMorphTriggers(self.morphs_config)
        self.gradual_analyzer = GradualMorphAnalyzer(self.morphs_config)
        self.state_manager = MorphStateManager()
        self.transition_manager = TransitionManager(self.transition_style)
        
        # Configuración avanzada
        advanced = morphing_config.get('advanced', {})
        self.gradual_enabled = advanced.get('gradual_layer', {}).get('enabled', True)
        self.confidence_threshold = advanced.get('gradual_layer', {}).get('confidence_threshold', 0.6)
        self.anti_loop_protection = advanced.get('transitions', {}).get('prevent_morphing_loops', True)
        
        # Estado para anti-loop protection
        self.recent_morphs = []  # Historial de morphs recientes
        
        # Estado actual
        self.current_morph = self.default_morph
        
        logger.info(f"🤖 MorphingManager inicializado - Morph por defecto: {self.default_morph}")
        logger.info(f"📋 Morphs disponibles: {list(self.morphs_config.keys())}")
    
    def process_message(self, user_input: str, conversation: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Proceso un mensaje del usuario y determino si necesito cambiar de morph.
        
        Args:
            user_input: Mensaje del usuario
            conversation: Historial de conversación actual
            
        Returns:
            Dict con información sobre el morph a usar y el contexto
        """
        if not self.enabled:
            # Si morphing está deshabilitado, siempre uso el morph por defecto
            return {
                'should_morph': False,
                'target_morph': self.default_morph,
                'current_morph': self.default_morph,
                'morph_config': self._get_morph_config(self.default_morph),
                'context': {'conversation': conversation}
            }
        
        # SISTEMA HÍBRIDO DE 2 CAPAS (Fase 2)
        
        # Capa 1: Verifico instant triggers (prioridad alta)
        instant_decision = self.instant_triggers.check(user_input, self.current_morph)
        
        if instant_decision and instant_decision.confidence >= 0.9:
            logger.info(f"⚡ Instant trigger detectado: {self.current_morph} → {instant_decision.morph_name}")
            if self._should_allow_morph_change(instant_decision.morph_name):
                return self._execute_morph_change(instant_decision, conversation, "instant")
            else:
                morph_metrics.record_anti_loop_block(instant_decision.morph_name)
        
        # Capa 2: Análisis gradual (si no hay trigger instantáneo)
        gradual_result = None
        if self.gradual_enabled:
            gradual_result = self.gradual_analyzer.analyze(user_input, conversation, self.current_morph)
            
            if gradual_result and gradual_result['confidence'] >= self.confidence_threshold:
                logger.info(f"📊 Análisis gradual sugiere: {self.current_morph} → {gradual_result['morph_name']} (conf: {gradual_result['confidence']:.2f})")
                if self._should_allow_morph_change(gradual_result['morph_name']):
                    # Creo un MorphDecision compatible desde el resultado gradual
                    gradual_decision = MorphDecision(
                        morph_name=gradual_result['morph_name'],
                        confidence=gradual_result['confidence'],
                        reason=gradual_result['reason']
                    )
                    return self._execute_morph_change(gradual_decision, conversation, "gradual")
                else:
                    morph_metrics.record_anti_loop_block(gradual_result['morph_name'])
        
        # No hay cambio necesario, continúo con el morph actual
        logger.debug(f"📝 Manteniendo morph actual: {self.current_morph}")
        return {
            'should_morph': False,
            'target_morph': self.current_morph,
            'current_morph': self.current_morph,
            'morph_config': self._get_morph_config(self.current_morph),
            'context': {'conversation': conversation},
            'analysis_details': {
                'instant_checked': instant_decision is not None,
                'gradual_checked': gradual_result is not None,
                'gradual_confidence': gradual_result['confidence'] if gradual_result else 0
            }
        }
    
    def _execute_morph_change(self, morph_decision: MorphDecision, conversation: List[Dict[str, str]], 
                            trigger_type: str = "unknown") -> Dict[str, Any]:
        """
        Ejecuto un cambio de morph usando los componentes del sistema.
        
        Args:
            morph_decision: Decisión de cambio
            conversation: Conversación actual
            trigger_type: Tipo de trigger ("instant", "gradual", etc.)
        """
        import time
        start_time = time.time()
        
        target_morph = morph_decision.morph_name
        
        # 1. Preservo estado actual
        preserved_state = self.state_manager.preserve_state(conversation, self.current_morph)
        
        # 2. Preparo transición
        transition_info = self.transition_manager.prepare_transition(
            self.current_morph, target_morph, morph_decision.reason
        )
        
        # 3. Ejecuto transición
        new_context = self.transition_manager.execute_transition(transition_info, preserved_state)
        
        # 4. Actualizo estado interno
        previous_morph = self.current_morph
        self.current_morph = target_morph
        self._track_morph_change(target_morph)  # Para anti-loop protection
        
        # 5. Registro métricas
        execution_time = (time.time() - start_time) * 1000  # En milisegundos
        morph_metrics.record_transformation(
            from_morph=previous_morph,
            to_morph=target_morph,
            trigger_type=trigger_type,
            confidence=morph_decision.confidence,
            success=True,  # Si llegamos aquí, fue exitoso
            time_ms=execution_time
        )
        
        # 6. Retorno información completa
        return {
            'should_morph': True,
            'target_morph': target_morph,
            'current_morph': target_morph,
            'previous_morph': previous_morph,
            'morph_config': self._get_morph_config(target_morph),
            'context': new_context,
            'transition_info': transition_info,
            'morph_decision': {
                'confidence': morph_decision.confidence,
                'reason': morph_decision.reason
            }
        }
    
    def _get_morph_config(self, morph_name: str) -> Dict[str, Any]:
        """
        Retorno la configuración completa de un morph específico.
        Si el morph no existe, retorno configuración por defecto.
        """
        morph_config = self.morphs_config.get(morph_name, {})
        
        # Configuración por defecto si no se especifica
        default_config = {
            'personality': f'Soy un asistente especializado en {morph_name}',
            'model': 'gpt-4o-mini',
            'temperature': 0.7,
            'tools': []
        }
        
        # Combino default con configuración específica
        final_config = {**default_config, **morph_config}
        
        return final_config
    
    def get_current_morph(self) -> str:
        """Retorno el morph actualmente activo"""
        return self.current_morph
    
    def get_available_morphs(self) -> List[str]:
        """Retorno lista de morphs disponibles"""
        return list(self.morphs_config.keys())
    
    def is_enabled(self) -> bool:
        """Retorno si el morphing está habilitado"""
        return self.enabled
    
    def reset_to_default(self):
        """Reseteo el morph al valor por defecto"""
        logger.info(f"🔄 Reseteando morph a: {self.default_morph}")
        self.current_morph = self.default_morph
        self.recent_morphs = []  # Limpio historial también
    
    def _should_allow_morph_change(self, target_morph: str) -> bool:
        """
        Determino si debo permitir un cambio de morph basándome en anti-loop protection.
        """
        if not self.anti_loop_protection:
            return True
        
        # Evito cambios muy frecuentes al mismo morph
        if len(self.recent_morphs) >= 3:
            # Si los últimos 3 cambios incluyen este morph, lo bloqueo temporalmente
            if self.recent_morphs[-3:].count(target_morph) >= 2:
                logger.warning(f"🚫 Anti-loop: Bloqueando cambio frecuente a '{target_morph}'")
                return False
        
        return True
    
    def _track_morph_change(self, new_morph: str):
        """
        Registro un cambio de morph para el anti-loop protection.
        """
        self.recent_morphs.append(new_morph)
        
        # Mantengo solo los últimos 5 cambios
        if len(self.recent_morphs) > 5:
            self.recent_morphs = self.recent_morphs[-5:]
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Retorno un resumen de métricas del sistema de morphing"""
        return morph_metrics.get_summary_stats()
    
    def get_morph_metrics(self, morph_name: str) -> Dict[str, Any]:
        """Retorno métricas específicas de un morph"""
        return morph_metrics.get_morph_stats(morph_name)
    
    def log_metrics_summary(self):
        """Registro un resumen de métricas en los logs"""
        morph_metrics.log_summary()