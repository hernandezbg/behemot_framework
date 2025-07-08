# morphing/morphing_manager.py
import logging
from typing import Dict, Any, Optional, List
from .instant_triggers import InstantMorphTriggers, MorphDecision
from .gradual_analyzer import GradualMorphAnalyzer
from .state_manager import MorphStateManager
from .transition_manager import TransitionManager
from .metrics import morph_metrics
from .feedback_system import MorphingFeedbackSystem
from .ab_testing import MorphingABTesting

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
        
        # Sistema de feedback (se inicializa después con Redis)
        self.feedback_system = None
        
        # Sistema de A/B testing (se inicializa después con Redis)
        self.ab_testing = None
        
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
        
        # Aplicar ajustes de confianza aprendidos
        if instant_decision:
            instant_decision = self._apply_learned_adjustments(instant_decision, user_input)
        
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
                # Creo un MorphDecision compatible desde el resultado gradual
                gradual_decision = MorphDecision(
                    morph_name=gradual_result['morph_name'],
                    confidence=gradual_result['confidence'],
                    reason=gradual_result['reason']
                )
                
                # Aplicar ajustes de confianza aprendidos
                gradual_decision = self._apply_learned_adjustments(gradual_decision, user_input)
                
                # Revisar si aún cumple el umbral después del ajuste
                if gradual_decision.confidence >= self.confidence_threshold:
                    logger.info(f"📊 Análisis gradual sugiere: {self.current_morph} → {gradual_decision.morph_name} (conf: {gradual_decision.confidence:.2f})")
                    if self._should_allow_morph_change(gradual_decision.morph_name):
                        return self._execute_morph_change(gradual_decision, conversation, "gradual")
                    else:
                        morph_metrics.record_anti_loop_block(gradual_decision.morph_name)
                else:
                    logger.debug(f"📉 Decisión gradual rechazada por ajuste de confianza aprendido: {gradual_result['confidence']:.2f} → {gradual_decision.confidence:.2f}")
        
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
    
    def set_redis_client(self, redis_client):
        """
        Inicializa el sistema de feedback con cliente Redis.
        Debe llamarse después de la inicialización del manager.
        """
        if redis_client:
            self.feedback_system = MorphingFeedbackSystem(redis_client)
            self.ab_testing = MorphingABTesting(redis_client)
            logger.info("🧠 Sistema de feedback inicializado con Redis")
            logger.info("🧪 Sistema de A/B testing inicializado con Redis")
        else:
            logger.info("ℹ️ Sistema de feedback deshabilitado (sin Redis)")
            logger.info("ℹ️ Sistema de A/B testing deshabilitado (sin Redis)")
    
    def record_morph_feedback(self, success: bool, user_id: str = None,
                             trigger: str = "", confidence: float = 0.0):
        """
        Registra feedback sobre la transformación actual.
        
        Args:
            success: Si la transformación fue exitosa
            user_id: ID del usuario (opcional)
            trigger: Input que causó la transformación
            confidence: Confianza de la decisión
        """
        if self.feedback_system and self.enabled:
            self.feedback_system.record_feedback(
                morph=self.current_morph,
                success=success,
                trigger=trigger,
                confidence=confidence,
                user_id=user_id
            )
    
    def detect_implicit_feedback(self, user_messages: List[str]) -> Optional[bool]:
        """
        Detecta feedback implícito del usuario.
        
        Returns:
            True si positivo, False si negativo, None si no claro
        """
        if self.feedback_system:
            return self.feedback_system.detect_implicit_feedback(
                user_messages, self.current_morph
            )
        return None
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """
        Obtiene resumen del aprendizaje del sistema.
        """
        if self.feedback_system:
            return self.feedback_system.get_learning_summary()
        return {"enabled": False}
    
    def _apply_learned_adjustments(self, decision: MorphDecision, user_input: str):
        """
        Aplica ajustes de confianza aprendidos al feedback.
        """
        if not self.feedback_system:
            return decision
            
        # Obtener ajuste aprendido
        adjustment = self.feedback_system.get_confidence_adjustment(
            decision.morph_name, user_input
        )
        
        if adjustment != 0:
            original_confidence = decision.confidence
            decision.confidence = max(0.0, min(1.0, decision.confidence + adjustment))
            
            logger.debug(f"📈 Ajuste de confianza aplicado: {original_confidence:.2f} → "
                        f"{decision.confidence:.2f} (ajuste: {adjustment:+.2f})")
            
        return decision
    
    # Métodos para A/B Testing
    
    def apply_ab_test_config(self, user_id: str, test_id: str = None):
        """
        Aplica configuración de A/B testing si existe test activo.
        
        Args:
            user_id: ID del usuario
            test_id: ID del test específico (opcional)
        """
        if not self.ab_testing:
            return
            
        try:
            # Si no se especifica test_id, buscar tests activos
            if test_id is None:
                # Por ahora usar un test por defecto si existe
                test_id = "confidence_threshold_test"
                
            variant = self.ab_testing.get_variant_for_user(user_id, test_id)
            
            if variant:
                config_overrides = variant["config"]
                
                # Aplicar overrides de configuración
                if "gradual_layer" in config_overrides:
                    gradual_config = config_overrides["gradual_layer"]
                    if "confidence_threshold" in gradual_config:
                        self.confidence_threshold = gradual_config["confidence_threshold"]
                        logger.debug(f"🧪 A/B Test aplicado: confidence_threshold = {self.confidence_threshold}")
                
                if "settings" in config_overrides:
                    settings_config = config_overrides["settings"]
                    if "sensitivity" in settings_config:
                        # Aplicar sensibilidad (podría afectar otros parámetros)
                        sensitivity = settings_config["sensitivity"]
                        logger.debug(f"🧪 A/B Test aplicado: sensitivity = {sensitivity}")
                        
                return variant["variant_id"]
                
        except Exception as e:
            logger.debug(f"Error aplicando configuración A/B: {e}")
            
        return None
    
    def record_ab_interaction(self, user_id: str, test_id: str, 
                             success: bool, confidence: float, 
                             transformation_time_ms: float):
        """
        Registra una interacción para análisis A/B.
        
        Args:
            user_id: ID del usuario
            test_id: ID del test
            success: Si la transformación fue exitosa
            confidence: Nivel de confianza
            transformation_time_ms: Tiempo de transformación
        """
        if self.ab_testing:
            self.ab_testing.record_interaction(
                user_id=user_id,
                test_id=test_id,
                success=success,
                confidence=confidence,
                transformation_time_ms=transformation_time_ms
            )
    
    def create_ab_test(self, test_config) -> bool:
        """
        Crea un nuevo test A/B.
        
        Args:
            test_config: Configuración del test A/B
            
        Returns:
            True si se creó exitosamente
        """
        if self.ab_testing:
            return self.ab_testing.create_test(test_config)
        return False
    
    def get_ab_test_results(self, test_id: str) -> Dict[str, Any]:
        """
        Obtiene resultados de un test A/B.
        
        Args:
            test_id: ID del test
            
        Returns:
            Resultados del test
        """
        if self.ab_testing:
            return self.ab_testing.get_test_results(test_id)
        return {}
    
    def get_optimal_config(self, test_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene la configuración óptima basada en resultados A/B.
        
        Args:
            test_id: ID del test
            
        Returns:
            Configuración ganadora
        """
        if self.ab_testing:
            return self.ab_testing.get_optimal_config(test_id)
        return None