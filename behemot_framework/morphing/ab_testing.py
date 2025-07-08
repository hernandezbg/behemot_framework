"""
Sistema de Testing A/B para Live Agent Morphing
Permite probar diferentes configuraciones automáticamente y optimizar parámetros.
"""

import json
import time
import random
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


@dataclass
class ABTestConfig:
    """Configuración de un test A/B"""
    test_id: str
    name: str
    description: str
    variants: List[Dict[str, Any]]  # Lista de configuraciones diferentes
    metrics: List[str]  # Métricas a medir
    duration_days: int
    min_samples: int  # Mínimo de muestras por variante
    confidence_level: float = 0.95
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


class MorphingABTesting:
    """
    Sistema de Testing A/B para configuraciones de morphing.
    Permite probar automáticamente diferentes parámetros y encontrar la configuración óptima.
    """
    
    def __init__(self, redis_client=None):
        """
        Inicializa el sistema de A/B testing.
        
        Args:
            redis_client: Cliente Redis para almacenamiento
        """
        self.redis = redis_client
        self.enabled = redis_client is not None
        
        # Prefijos de keys para Redis
        self.TESTS_KEY = "morphing:ab_tests"
        self.ASSIGNMENTS_KEY = "morphing:ab_assignments:{user_id}"
        self.RESULTS_KEY = "morphing:ab_results:{test_id}:{variant}"
        self.ACTIVE_TESTS_KEY = "morphing:ab_active"
        
    def create_test(self, test_config: ABTestConfig) -> bool:
        """
        Crea un nuevo test A/B.
        
        Args:
            test_config: Configuración del test
            
        Returns:
            True si se creó exitosamente
        """
        if not self.enabled:
            return False
            
        try:
            # Guardar configuración del test
            test_data = asdict(test_config)
            self.redis.hset(
                self.TESTS_KEY, 
                test_config.test_id, 
                json.dumps(test_data)
            )
            
            # Agregar a tests activos
            end_time = time.time() + (test_config.duration_days * 24 * 3600)
            self.redis.zadd(
                self.ACTIVE_TESTS_KEY, 
                {test_config.test_id: end_time}
            )
            
            # Inicializar contadores de resultados para cada variante
            for i, variant in enumerate(test_config.variants):
                variant_id = f"variant_{i}"
                result_key = self.RESULTS_KEY.format(
                    test_id=test_config.test_id, 
                    variant=variant_id
                )
                
                # Inicializar métricas
                initial_metrics = {
                    "total_users": 0,
                    "total_interactions": 0,
                    "success_count": 0,
                    "avg_confidence": 0.0,
                    "transformation_time_ms": 0.0
                }
                
                for metric in test_config.metrics:
                    initial_metrics[metric] = 0
                    
                self.redis.hmset(result_key, initial_metrics)
            
            return True
            
        except Exception as e:
            print(f"Error creando test A/B: {e}")
            return False
    
    def get_variant_for_user(self, user_id: str, test_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene la variante asignada a un usuario para un test específico.
        
        Args:
            user_id: ID del usuario
            test_id: ID del test
            
        Returns:
            Configuración de la variante o None
        """
        if not self.enabled:
            return None
            
        try:
            # Verificar si el test está activo
            if not self._is_test_active(test_id):
                return None
                
            assignment_key = self.ASSIGNMENTS_KEY.format(user_id=user_id)
            
            # Verificar si ya tiene asignación
            existing_assignment = self.redis.hget(assignment_key, test_id)
            
            if existing_assignment:
                variant_id = existing_assignment.decode()
            else:
                # Asignar nueva variante (distribución uniforme)
                test_config = self._get_test_config(test_id)
                if not test_config:
                    return None
                    
                variant_count = len(test_config.variants)
                variant_index = hash(f"{user_id}_{test_id}") % variant_count
                variant_id = f"variant_{variant_index}"
                
                # Guardar asignación
                self.redis.hset(assignment_key, test_id, variant_id)
                
                # Incrementar contador de usuarios
                result_key = self.RESULTS_KEY.format(
                    test_id=test_id, variant=variant_id
                )
                self.redis.hincrby(result_key, "total_users", 1)
            
            # Obtener configuración de la variante
            test_config = self._get_test_config(test_id)
            if test_config:
                variant_index = int(variant_id.split("_")[1])
                return {
                    "variant_id": variant_id,
                    "config": test_config.variants[variant_index]
                }
                
            return None
            
        except Exception as e:
            print(f"Error obteniendo variante: {e}")
            return None
    
    def record_interaction(self, user_id: str, test_id: str, 
                          success: bool, confidence: float, 
                          transformation_time_ms: float,
                          custom_metrics: Dict[str, float] = None):
        """
        Registra una interacción para el análisis A/B.
        
        Args:
            user_id: ID del usuario
            test_id: ID del test
            success: Si la interacción fue exitosa
            confidence: Nivel de confianza
            transformation_time_ms: Tiempo de transformación
            custom_metrics: Métricas adicionales
        """
        if not self.enabled:
            return
            
        try:
            # Obtener variante del usuario
            variant_info = self.get_variant_for_user(user_id, test_id)
            if not variant_info:
                return
                
            variant_id = variant_info["variant_id"]
            result_key = self.RESULTS_KEY.format(
                test_id=test_id, variant=variant_id
            )
            
            # Usar pipeline para atomicidad
            pipe = self.redis.pipeline()
            
            # Actualizar métricas básicas
            pipe.hincrby(result_key, "total_interactions", 1)
            
            if success:
                pipe.hincrby(result_key, "success_count", 1)
            
            # Actualizar promedio de confianza
            current_interactions = int(self.redis.hget(result_key, "total_interactions") or 1)
            current_avg_conf = float(self.redis.hget(result_key, "avg_confidence") or 0)
            new_avg_conf = ((current_avg_conf * (current_interactions - 1)) + confidence) / current_interactions
            pipe.hset(result_key, "avg_confidence", new_avg_conf)
            
            # Actualizar promedio de tiempo de transformación
            current_avg_time = float(self.redis.hget(result_key, "transformation_time_ms") or 0)
            new_avg_time = ((current_avg_time * (current_interactions - 1)) + transformation_time_ms) / current_interactions
            pipe.hset(result_key, "transformation_time_ms", new_avg_time)
            
            # Métricas personalizadas
            if custom_metrics:
                for metric, value in custom_metrics.items():
                    pipe.hincrbyfloat(result_key, metric, value)
            
            pipe.execute()
            
        except Exception as e:
            print(f"Error registrando interacción A/B: {e}")
    
    def get_test_results(self, test_id: str) -> Dict[str, Any]:
        """
        Obtiene los resultados de un test A/B.
        
        Args:
            test_id: ID del test
            
        Returns:
            Resultados del test con análisis estadístico
        """
        if not self.enabled:
            return {}
            
        try:
            test_config = self._get_test_config(test_id)
            if not test_config:
                return {}
            
            results = {
                "test_id": test_id,
                "test_config": asdict(test_config),
                "variants": [],
                "analysis": {},
                "status": "running" if self._is_test_active(test_id) else "completed"
            }
            
            # Recopilar resultados de cada variante
            for i, variant_config in enumerate(test_config.variants):
                variant_id = f"variant_{i}"
                result_key = self.RESULTS_KEY.format(
                    test_id=test_id, variant=variant_id
                )
                
                raw_metrics = self.redis.hgetall(result_key)
                metrics = {k.decode(): float(v.decode()) for k, v in raw_metrics.items()}
                
                # Calcular métricas derivadas
                total_interactions = metrics.get("total_interactions", 0)
                success_count = metrics.get("success_count", 0)
                success_rate = (success_count / total_interactions * 100) if total_interactions > 0 else 0
                
                variant_result = {
                    "variant_id": variant_id,
                    "config": variant_config,
                    "metrics": metrics,
                    "derived_metrics": {
                        "success_rate": success_rate,
                        "total_interactions": int(total_interactions),
                        "total_users": int(metrics.get("total_users", 0))
                    }
                }
                
                results["variants"].append(variant_result)
            
            # Análisis estadístico básico
            if len(results["variants"]) >= 2:
                results["analysis"] = self._perform_statistical_analysis(results["variants"])
            
            return results
            
        except Exception as e:
            print(f"Error obteniendo resultados: {e}")
            return {}
    
    def get_optimal_config(self, test_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene la configuración óptima basada en los resultados del test.
        
        Args:
            test_id: ID del test
            
        Returns:
            Configuración de la variante ganadora
        """
        results = self.get_test_results(test_id)
        analysis = results.get("analysis", {})
        
        if "winner" in analysis:
            winner_variant_id = analysis["winner"]["variant_id"]
            for variant in results["variants"]:
                if variant["variant_id"] == winner_variant_id:
                    return variant["config"]
        
        return None
    
    def cleanup_expired_tests(self):
        """
        Limpia tests expirados y mueve resultados a archivo histórico.
        """
        if not self.enabled:
            return
            
        try:
            current_time = time.time()
            
            # Obtener tests expirados
            expired_tests = self.redis.zrangebyscore(
                self.ACTIVE_TESTS_KEY, 0, current_time
            )
            
            for test_id in expired_tests:
                test_id = test_id.decode()
                
                # Marcar como completado
                self.redis.zrem(self.ACTIVE_TESTS_KEY, test_id)
                
                # Opcional: Mover resultados a storage histórico
                # (implementar según necesidades de negocio)
                
        except Exception as e:
            print(f"Error limpiando tests expirados: {e}")
    
    def _is_test_active(self, test_id: str) -> bool:
        """Verifica si un test está activo"""
        if not self.enabled:
            return False
        return self.redis.zscore(self.ACTIVE_TESTS_KEY, test_id) is not None
    
    def _get_test_config(self, test_id: str) -> Optional[ABTestConfig]:
        """Obtiene la configuración de un test"""
        if not self.enabled:
            return None
            
        test_data = self.redis.hget(self.TESTS_KEY, test_id)
        if test_data:
            config_dict = json.loads(test_data.decode())
            return ABTestConfig(**config_dict)
        return None
    
    def _perform_statistical_analysis(self, variants: List[Dict]) -> Dict[str, Any]:
        """
        Realiza análisis estadístico básico de los resultados.
        Para análisis más sofisticado se podrían usar librerías como scipy.
        """
        analysis = {
            "sample_size_sufficient": True,
            "winner": None,
            "confidence_level": 0.0,
            "recommendations": []
        }
        
        # Verificar tamaño de muestra mínimo
        min_interactions = 30  # Mínimo estadísticamente significativo
        for variant in variants:
            if variant["derived_metrics"]["total_interactions"] < min_interactions:
                analysis["sample_size_sufficient"] = False
                analysis["recommendations"].append(
                    f"Variante {variant['variant_id']} necesita más datos "
                    f"({variant['derived_metrics']['total_interactions']}/{min_interactions})"
                )
        
        if not analysis["sample_size_sufficient"]:
            return analysis
        
        # Encontrar la variante con mejor success_rate
        best_variant = max(variants, key=lambda v: v["derived_metrics"]["success_rate"])
        
        # Calcular diferencia con la segunda mejor
        sorted_variants = sorted(variants, 
                               key=lambda v: v["derived_metrics"]["success_rate"], 
                               reverse=True)
        
        if len(sorted_variants) >= 2:
            best_rate = sorted_variants[0]["derived_metrics"]["success_rate"]
            second_rate = sorted_variants[1]["derived_metrics"]["success_rate"]
            improvement = best_rate - second_rate
            
            # Análisis simple: si mejora >5% con suficientes datos, es significativo
            if improvement > 5.0 and sorted_variants[0]["derived_metrics"]["total_interactions"] > 50:
                analysis["winner"] = {
                    "variant_id": sorted_variants[0]["variant_id"],
                    "success_rate": best_rate,
                    "improvement": improvement
                }
                analysis["confidence_level"] = 0.85  # Simplified confidence
                analysis["recommendations"].append(
                    f"Variante {sorted_variants[0]['variant_id']} muestra mejora "
                    f"significativa del {improvement:.1f}%"
                )
            else:
                analysis["recommendations"].append(
                    "No hay diferencia estadísticamente significativa entre variantes"
                )
        
        return analysis


# Configuraciones predefinidas para tests comunes
class PredefinedABTests:
    """Configuraciones predefinidas de tests A/B comunes"""
    
    @staticmethod
    def confidence_threshold_test() -> ABTestConfig:
        """Test A/B para encontrar el umbral de confianza óptimo"""
        return ABTestConfig(
            test_id="confidence_threshold_test",
            name="Optimización de Umbral de Confianza",
            description="Prueba diferentes umbrales para análisis gradual",
            variants=[
                {"gradual_layer": {"confidence_threshold": 0.4}},
                {"gradual_layer": {"confidence_threshold": 0.6}},
                {"gradual_layer": {"confidence_threshold": 0.8}}
            ],
            metrics=["transformation_success", "user_satisfaction", "precision"],
            duration_days=7,
            min_samples=100
        )
    
    @staticmethod
    def sensitivity_test() -> ABTestConfig:
        """Test A/B para encontrar la sensibilidad óptima"""
        return ABTestConfig(
            test_id="sensitivity_test",
            name="Optimización de Sensibilidad",
            description="Prueba diferentes niveles de sensibilidad",
            variants=[
                {"settings": {"sensitivity": "low"}},
                {"settings": {"sensitivity": "medium"}},
                {"settings": {"sensitivity": "high"}}
            ],
            metrics=["transformation_frequency", "accuracy", "user_experience"],
            duration_days=5,
            min_samples=75
        )
    
    @staticmethod
    def anti_loop_test() -> ABTestConfig:
        """Test A/B para configuración de anti-loop protection"""
        return ABTestConfig(
            test_id="anti_loop_test",
            name="Optimización Anti-Loop",
            description="Prueba diferentes configuraciones de protección anti-loop",
            variants=[
                {"transitions": {"prevent_morphing_loops": True, "loop_threshold": 3}},
                {"transitions": {"prevent_morphing_loops": True, "loop_threshold": 5}},
                {"transitions": {"prevent_morphing_loops": False}}
            ],
            metrics=["loop_incidents", "user_frustration", "conversation_flow"],
            duration_days=10,
            min_samples=150
        )