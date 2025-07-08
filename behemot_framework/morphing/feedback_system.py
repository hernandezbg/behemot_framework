"""
Sistema de Feedback para Live Agent Morphing
Aprende de las interacciones y mejora las decisiones de morphing con el tiempo.
Almacenamiento 100% en Redis para compatibilidad cloud.
"""

import json
import time
from typing import Dict, Optional, List, Tuple
from datetime import datetime


class MorphingFeedbackSystem:
    """
    Sistema de feedback que aprende de las transformaciones exitosas y fallidas.
    Almacena todo en Redis para funcionar en entornos cloud multi-instancia.
    """
    
    def __init__(self, redis_client=None):
        """
        Inicializa el sistema de feedback.
        
        Args:
            redis_client: Cliente Redis para almacenamiento
        """
        self.redis = redis_client
        self.enabled = redis_client is not None
        
        # Prefijos de keys para Redis
        self.STATS_KEY = "morphing:stats:{morph}"
        self.PATTERNS_POS_KEY = "morphing:patterns:positive"
        self.PATTERNS_NEG_KEY = "morphing:patterns:negative"
        self.CONFIDENCE_ADJ_KEY = "morphing:confidence:adjustments"
        self.RECENT_FEEDBACK_KEY = "morphing:feedback:recent"
        
    def record_feedback(self, morph: str, success: bool, trigger: str, 
                       confidence: float, user_id: Optional[str] = None):
        """
        Registra feedback sobre una transformación de morph.
        
        Args:
            morph: Nombre del morph al que se transformó
            success: Si la transformación fue exitosa o no
            trigger: El trigger/input que causó la transformación
            confidence: Nivel de confianza de la decisión
            user_id: ID opcional del usuario
        """
        if not self.enabled:
            return
            
        try:
            pipe = self.redis.pipeline()
            
            # 1. Actualizar estadísticas agregadas
            stats_key = self.STATS_KEY.format(morph=morph)
            pipe.hincrby(stats_key, "total", 1)
            pipe.hincrby(stats_key, "success" if success else "failed", 1)
            pipe.hincrbyfloat(stats_key, "total_confidence", confidence)
            
            # 2. Registrar patrón (positivo o negativo)
            pattern_key = f"{morph}:{trigger.lower()[:50]}"  # Limitar longitud
            if success:
                pipe.zincrby(self.PATTERNS_POS_KEY, 1, pattern_key)
            else:
                pipe.zincrby(self.PATTERNS_NEG_KEY, 1, pattern_key)
                
            # 3. Ajustar confianza futura si hay suficiente evidencia
            self._adjust_confidence_if_needed(pipe, morph, trigger, success)
            
            # 4. Registrar feedback reciente (para análisis)
            feedback_data = {
                "morph": morph,
                "success": success,
                "trigger": trigger,
                "confidence": confidence,
                "timestamp": time.time(),
                "user_id": user_id
            }
            pipe.lpush(self.RECENT_FEEDBACK_KEY, json.dumps(feedback_data))
            pipe.ltrim(self.RECENT_FEEDBACK_KEY, 0, 999)  # Mantener últimos 1000
            
            pipe.execute()
            
        except Exception as e:
            print(f"Error registrando feedback: {e}")
            
    def _adjust_confidence_if_needed(self, pipe, morph: str, trigger: str, success: bool):
        """
        Ajusta la confianza futura basándose en el feedback acumulado.
        Solo ajusta después de suficiente evidencia.
        """
        # Construir key del patrón
        pattern_key = f"{morph}:{trigger.lower()[:50]}"
        
        # Ver cuántas veces ha aparecido este patrón
        pos_score = self.redis.zscore(self.PATTERNS_POS_KEY, pattern_key) or 0
        neg_score = self.redis.zscore(self.PATTERNS_NEG_KEY, pattern_key) or 0
        total_occurrences = pos_score + neg_score
        
        # Solo ajustar después de 5+ ocurrencias
        if total_occurrences >= 5:
            # Calcular tasa de éxito
            success_rate = pos_score / total_occurrences
            
            # Determinar ajuste basado en la tasa de éxito
            if success_rate < 0.3:  # Falla más del 70%
                adjustment = -0.2
            elif success_rate < 0.5:  # Falla más del 50%
                adjustment = -0.1
            elif success_rate > 0.8:  # Exitoso más del 80%
                adjustment = 0.1
            else:
                adjustment = 0
                
            if adjustment != 0:
                # Aplicar ajuste con límites
                current = float(self.redis.hget(self.CONFIDENCE_ADJ_KEY, pattern_key) or 0)
                new_adjustment = max(-0.5, min(0.5, current + adjustment * 0.1))
                pipe.hset(self.CONFIDENCE_ADJ_KEY, pattern_key, new_adjustment)
                
    def get_confidence_adjustment(self, morph: str, user_input: str) -> float:
        """
        Obtiene el ajuste de confianza aprendido para un morph y entrada.
        
        Returns:
            Ajuste de confianza a aplicar (-0.5 a 0.5)
        """
        if not self.enabled:
            return 0.0
            
        # Buscar ajustes relevantes
        adjustments = self.redis.hgetall(self.CONFIDENCE_ADJ_KEY)
        total_adjustment = 0.0
        matches = 0
        
        for pattern, adjustment in adjustments.items():
            pattern_morph, pattern_trigger = pattern.decode().split(":", 1)
            if pattern_morph == morph and pattern_trigger in user_input.lower():
                total_adjustment += float(adjustment)
                matches += 1
                
        # Promedio de ajustes encontrados
        return total_adjustment / matches if matches > 0 else 0.0
        
    def get_morph_stats(self, morph: str) -> Dict:
        """
        Obtiene estadísticas de un morph específico.
        """
        if not self.enabled:
            return {}
            
        stats_key = self.STATS_KEY.format(morph=morph)
        raw_stats = self.redis.hgetall(stats_key)
        
        if not raw_stats:
            return {"total": 0, "success_rate": 0, "avg_confidence": 0}
            
        total = int(raw_stats.get(b'total', 0))
        success = int(raw_stats.get(b'success', 0))
        total_conf = float(raw_stats.get(b'total_confidence', 0))
        
        return {
            "total": total,
            "success": success,
            "failed": total - success,
            "success_rate": (success / total * 100) if total > 0 else 0,
            "avg_confidence": (total_conf / total) if total > 0 else 0
        }
        
    def get_failed_patterns(self, limit: int = 10) -> List[Tuple[str, int]]:
        """
        Obtiene los patrones que más fallan.
        """
        if not self.enabled:
            return []
            
        patterns = self.redis.zrevrange(
            self.PATTERNS_NEG_KEY, 0, limit - 1, withscores=True
        )
        
        return [(p.decode(), int(score)) for p, score in patterns]
        
    def get_successful_patterns(self, limit: int = 10) -> List[Tuple[str, int]]:
        """
        Obtiene los patrones más exitosos.
        """
        if not self.enabled:
            return []
            
        patterns = self.redis.zrevrange(
            self.PATTERNS_POS_KEY, 0, limit - 1, withscores=True
        )
        
        return [(p.decode(), int(score)) for p, score in patterns]
        
    def get_learning_summary(self) -> Dict:
        """
        Obtiene un resumen del aprendizaje del sistema.
        """
        if not self.enabled:
            return {"enabled": False}
            
        # Obtener todos los morphs registrados
        all_keys = self.redis.keys("morphing:stats:*")
        morphs = [key.decode().split(":")[-1] for key in all_keys]
        
        summary = {
            "enabled": True,
            "morphs_performance": {},
            "top_failed_patterns": self.get_failed_patterns(5),
            "top_successful_patterns": self.get_successful_patterns(5),
            "total_feedback_processed": 0
        }
        
        # Performance por morph
        for morph in morphs:
            stats = self.get_morph_stats(morph)
            summary["morphs_performance"][morph] = stats
            summary["total_feedback_processed"] += stats["total"]
            
        # Ajustes de confianza activos
        adjustments = self.redis.hgetall(self.CONFIDENCE_ADJ_KEY)
        summary["active_adjustments"] = len(adjustments)
        
        return summary
        
    def detect_implicit_feedback(self, user_messages: List[str], 
                                current_morph: str) -> Optional[bool]:
        """
        Intenta detectar feedback implícito del usuario.
        
        Returns:
            True si parece positivo, False si negativo, None si no claro
        """
        if len(user_messages) < 2:
            return None
            
        last_message = user_messages[-1].lower()
        
        # Señales negativas
        negative_signals = [
            "no era eso", "no quiero", "mejor no", "olvídalo",
            "no entiendes", "me equivoqué", "cambiar de tema",
            "no es lo que busco", "otra cosa"
        ]
        
        # Señales positivas
        positive_signals = [
            "perfecto", "exacto", "genial", "gracias", "eso es",
            "correcto", "sí", "adelante", "continúa", "excelente"
        ]
        
        # Detectar señales
        for signal in negative_signals:
            if signal in last_message:
                return False
                
        for signal in positive_signals:
            if signal in last_message:
                return True
                
        # Si repite pregunta similar, probablemente no entendió
        if len(user_messages) >= 2:
            prev_message = user_messages[-2].lower()
            if self._similarity(last_message, prev_message) > 0.7:
                return False
                
        return None
        
    def _similarity(self, str1: str, str2: str) -> float:
        """
        Calcula similitud simple entre dos strings (0-1).
        """
        words1 = set(str1.split())
        words2 = set(str2.split())
        
        if not words1 or not words2:
            return 0.0
            
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)