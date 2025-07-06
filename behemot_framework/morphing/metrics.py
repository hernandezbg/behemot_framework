# morphing/metrics.py
import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)

class MorphMetrics:
    """
    Sistema básico de métricas para Live Agent Morphing.
    Rastrea transformaciones, precisión y patrones de uso.
    """
    
    def __init__(self):
        """Inicializo el sistema de métricas"""
        # Contadores básicos
        self.total_transformations = 0
        self.successful_transformations = 0
        self.instant_triggers_used = 0
        self.gradual_triggers_used = 0
        self.anti_loop_blocks = 0
        
        # Estadísticas por morph
        self.morph_usage_count = defaultdict(int)
        self.morph_success_rate = defaultdict(list)  # Lista de éxitos/fallos por morph
        
        # Historial reciente (últimas 24 horas)
        self.recent_transformations = []
        
        # Tiempos de respuesta
        self.transformation_times = []
        
        logger.info("📊 MorphMetrics inicializado")
    
    def record_transformation(self, from_morph: str, to_morph: str, trigger_type: str, 
                            confidence: float, success: bool, time_ms: float):
        """
        Registro una transformación de morph.
        
        Args:
            from_morph: Morph de origen
            to_morph: Morph destino
            trigger_type: "instant" o "gradual"
            confidence: Nivel de confianza (0-1)
            success: Si la transformación fue exitosa
            time_ms: Tiempo de procesamiento en milisegundos
        """
        # Actualizo contadores básicos
        self.total_transformations += 1
        if success:
            self.successful_transformations += 1
        
        if trigger_type == "instant":
            self.instant_triggers_used += 1
        elif trigger_type == "gradual":
            self.gradual_triggers_used += 1
        
        # Actualizo estadísticas por morph
        self.morph_usage_count[to_morph] += 1
        self.morph_success_rate[to_morph].append(success)
        
        # Registro en historial reciente
        transformation_record = {
            'timestamp': datetime.now(),
            'from_morph': from_morph,
            'to_morph': to_morph,
            'trigger_type': trigger_type,
            'confidence': confidence,
            'success': success,
            'time_ms': time_ms
        }
        self.recent_transformations.append(transformation_record)
        
        # Limpio registros antiguos (más de 24 horas)
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.recent_transformations = [
            record for record in self.recent_transformations 
            if record['timestamp'] > cutoff_time
        ]
        
        # Registro tiempo de transformación
        self.transformation_times.append(time_ms)
        if len(self.transformation_times) > 100:  # Mantengo solo las últimas 100
            self.transformation_times = self.transformation_times[-100:]
        
        logger.debug(f"📈 Transformación registrada: {from_morph} → {to_morph} ({trigger_type}, {confidence:.2f})")
    
    def record_anti_loop_block(self, blocked_morph: str):
        """Registro cuando se bloquea una transformación por anti-loop protection"""
        self.anti_loop_blocks += 1
        logger.debug(f"🚫 Anti-loop block registrado para: {blocked_morph}")
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Retorno un resumen de estadísticas actuales"""
        # Calculo promedios
        avg_transformation_time = (
            sum(self.transformation_times) / len(self.transformation_times)
            if self.transformation_times else 0
        )
        
        success_rate = (
            self.successful_transformations / self.total_transformations
            if self.total_transformations > 0 else 0
        )
        
        # Top morphs más usados
        most_used_morphs = dict(Counter(self.morph_usage_count).most_common(5))
        
        # Transformaciones en las últimas 24h
        recent_count = len(self.recent_transformations)
        
        return {
            'total_transformations': self.total_transformations,
            'success_rate': round(success_rate * 100, 1),  # Como porcentaje
            'avg_transformation_time_ms': round(avg_transformation_time, 2),
            'instant_vs_gradual': {
                'instant': self.instant_triggers_used,
                'gradual': self.gradual_triggers_used
            },
            'anti_loop_blocks': self.anti_loop_blocks,
            'most_used_morphs': most_used_morphs,
            'transformations_24h': recent_count
        }
    
    def get_morph_stats(self, morph_name: str) -> Dict[str, Any]:
        """Retorno estadísticas específicas de un morph"""
        usage_count = self.morph_usage_count.get(morph_name, 0)
        success_records = self.morph_success_rate.get(morph_name, [])
        
        if success_records:
            success_rate = sum(success_records) / len(success_records)
        else:
            success_rate = 0
        
        return {
            'usage_count': usage_count,
            'success_rate': round(success_rate * 100, 1),
            'total_attempts': len(success_records)
        }
    
    def get_recent_activity(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Retorno actividad reciente en las últimas N horas"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent = [
            record for record in self.recent_transformations
            if record['timestamp'] > cutoff_time
        ]
        
        # Convierto timestamp a string para serialización
        for record in recent:
            record['timestamp'] = record['timestamp'].isoformat()
        
        return recent
    
    def reset_metrics(self):
        """Reinicio todas las métricas (útil para testing)"""
        self.__init__()
        logger.info("📊 Métricas reiniciadas")
    
    def log_summary(self):
        """Registro un resumen en los logs"""
        stats = self.get_summary_stats()
        logger.info(f"📊 MÉTRICAS MORPHING:")
        logger.info(f"   Transformaciones: {stats['total_transformations']}")
        logger.info(f"   Tasa de éxito: {stats['success_rate']}%")
        logger.info(f"   Tiempo promedio: {stats['avg_transformation_time_ms']}ms")
        logger.info(f"   Instant/Gradual: {stats['instant_vs_gradual']['instant']}/{stats['instant_vs_gradual']['gradual']}")
        logger.info(f"   Morphs más usados: {stats['most_used_morphs']}")


# Instancia global para uso en todo el sistema
morph_metrics = MorphMetrics()