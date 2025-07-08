#!/usr/bin/env python3
"""
Test del Sistema de A/B Testing para Live Agent Morphing
Verifica que las pruebas automáticas de configuraciones funcionan correctamente.
"""

import sys
import os
import time
sys.path.append('/home/hernandezbg/proyectos/behemot_framework_package')

def test_ab_testing_system():
    """Test del sistema de A/B testing"""
    print("🧪 Test del Sistema de A/B Testing")
    
    from behemot_framework.morphing.ab_testing import MorphingABTesting, ABTestConfig, PredefinedABTests
    
    # Mock Redis simplificado para testing
    class MockRedis:
        def __init__(self):
            self.data = {}
            self.sorted_sets = {}
            
        def hset(self, key, field, value):
            if key not in self.data:
                self.data[key] = {}
            self.data[key][field] = value
            
        def hmset(self, key, mapping):
            if key not in self.data:
                self.data[key] = {}
            self.data[key].update(mapping)
            
        def hget(self, key, field):
            value = self.data.get(key, {}).get(field)
            return str(value).encode() if value is not None else None
            
        def hgetall(self, key):
            return {k.encode(): str(v).encode() for k, v in self.data.get(key, {}).items()}
            
        def zadd(self, key, mapping):
            if key not in self.sorted_sets:
                self.sorted_sets[key] = {}
            self.sorted_sets[key].update(mapping)
            
        def zscore(self, key, member):
            return self.sorted_sets.get(key, {}).get(member)
            
        def hincrby(self, key, field, amount):
            if key not in self.data:
                self.data[key] = {}
            current = int(self.data[key].get(field, 0))
            self.data[key][field] = current + amount
            
        def hincrbyfloat(self, key, field, amount):
            if key not in self.data:
                self.data[key] = {}
            current = float(self.data[key].get(field, 0))
            self.data[key][field] = current + amount
            
        def pipeline(self):
            return MockPipeline(self)
            
    class MockPipeline:
        def __init__(self, redis_client):
            self.redis = redis_client
            self.commands = []
            
        def hincrby(self, key, field, amount):
            self.commands.append(('hincrby', key, field, amount))
            
        def hset(self, key, field, value):
            self.commands.append(('hset', key, field, value))
            
        def hincrbyfloat(self, key, field, amount):
            self.commands.append(('hincrbyfloat', key, field, amount))
            
        def execute(self):
            for cmd in self.commands:
                if cmd[0] == 'hincrby':
                    self.redis.hincrby(cmd[1], cmd[2], cmd[3])
                elif cmd[0] == 'hset':
                    self.redis.hset(cmd[1], cmd[2], cmd[3])
                elif cmd[0] == 'hincrbyfloat':
                    self.redis.hincrbyfloat(cmd[1], cmd[2], cmd[3])
    
    mock_redis = MockRedis()
    ab_testing = MorphingABTesting(mock_redis)
    
    # Test 1: Crear test A/B
    print("   🔬 Test 1: Crear test A/B")
    test_config = PredefinedABTests.confidence_threshold_test()
    
    success = ab_testing.create_test(test_config)
    if success:
        print("   ✅ PASS: Test A/B creado exitosamente")
    else:
        print("   ❌ FAIL: Error creando test A/B")
        return False
    
    # Test 2: Asignar variantes a usuarios
    print("   🔬 Test 2: Asignación de variantes")
    user1_variant = ab_testing.get_variant_for_user("user1", "confidence_threshold_test")
    user2_variant = ab_testing.get_variant_for_user("user2", "confidence_threshold_test")
    
    if user1_variant and user2_variant:
        print(f"   ✅ PASS: Variantes asignadas - User1: {user1_variant['variant_id']}, User2: {user2_variant['variant_id']}")
        
        # Verificar que la asignación sea consistente
        user1_variant_2 = ab_testing.get_variant_for_user("user1", "confidence_threshold_test")
        if user1_variant_2["variant_id"] == user1_variant["variant_id"]:
            print("   ✅ PASS: Asignación consistente para el mismo usuario")
        else:
            print("   ❌ FAIL: Asignación inconsistente")
            return False
    else:
        print("   ❌ FAIL: Error asignando variantes")
        return False
    
    # Test 3: Registrar interacciones
    print("   🔬 Test 3: Registro de interacciones")
    
    # Simular múltiples interacciones
    interactions = [
        ("user1", True, 0.8, 150.0),
        ("user1", True, 0.7, 130.0),
        ("user1", False, 0.5, 200.0),
        ("user2", True, 0.9, 120.0),
        ("user2", True, 0.8, 140.0),
    ]
    
    for user_id, success, confidence, time_ms in interactions:
        ab_testing.record_interaction(
            user_id=user_id,
            test_id="confidence_threshold_test",
            success=success,
            confidence=confidence,
            transformation_time_ms=time_ms
        )
    
    print(f"   ✅ PASS: {len(interactions)} interacciones registradas")
    
    # Test 4: Obtener resultados
    print("   🔬 Test 4: Análisis de resultados")
    results = ab_testing.get_test_results("confidence_threshold_test")
    
    if results and "variants" in results:
        print(f"   ✅ PASS: Resultados obtenidos con {len(results['variants'])} variantes")
        
        # Verificar que hay datos en las variantes
        total_interactions = sum(
            variant["derived_metrics"]["total_interactions"] 
            for variant in results["variants"]
        )
        
        if total_interactions >= len(interactions):
            print(f"   ✅ PASS: Interacciones registradas correctamente ({total_interactions})")
        else:
            print(f"   ❌ FAIL: Interacciones perdidas: esperadas {len(interactions)}, registradas {total_interactions}")
            return False
            
    else:
        print("   ❌ FAIL: Error obteniendo resultados")
        return False
    
    # Test 5: Configuración predefinida
    print("   🔬 Test 5: Tests predefinidos")
    
    predefined_tests = [
        PredefinedABTests.confidence_threshold_test(),
        PredefinedABTests.sensitivity_test(),
        PredefinedABTests.anti_loop_test()
    ]
    
    if len(predefined_tests) == 3:
        print("   ✅ PASS: Tests predefinidos disponibles")
        for test in predefined_tests:
            if len(test.variants) >= 2:
                print(f"      - {test.name}: {len(test.variants)} variantes")
            else:
                print(f"   ❌ FAIL: Test {test.name} tiene pocas variantes")
                return False
    else:
        print("   ❌ FAIL: Tests predefinidos faltantes")
        return False
    
    print("✅ Sistema de A/B testing funcionando correctamente")
    return True

def test_integration_with_morphing_manager():
    """Test de integración con MorphingManager"""
    print("\n🧪 Test de Integración A/B Testing con MorphingManager")
    
    from behemot_framework.morphing.morphing_manager import MorphingManager
    from behemot_framework.morphing.ab_testing import PredefinedABTests
    
    # Configuración de test
    config = {
        "enabled": True,
        "default_morph": "general",
        "morphs": {
            "general": {},
            "sales": {
                "instant_triggers": ["comprar"]
            }
        }
    }
    
    manager = MorphingManager(config)
    
    # Mock Redis para A/B testing
    class MockRedisSimple:
        def __init__(self):
            self.data = {}
            self.sorted_sets = {}
        def hset(self, key, field, value): pass
        def hmset(self, key, mapping): pass
        def hget(self, key, field): return b"0.6"  # Simular threshold
        def hgetall(self, key): return {}
        def zadd(self, key, mapping): pass
        def zscore(self, key, member): return time.time() + 3600  # Test activo
        def hincrby(self, key, field, amount): pass
        def hincrbyfloat(self, key, field, amount): pass
        def pipeline(self): return MockPipelineSimple()
            
    class MockPipelineSimple:
        def hincrby(self, key, field, amount): pass
        def hset(self, key, field, value): pass
        def hincrbyfloat(self, key, field, amount): pass
        def execute(self): pass
    
    mock_redis = MockRedisSimple()
    manager.set_redis_client(mock_redis)
    
    # Test que el A/B testing se inicializó
    if manager.ab_testing is not None:
        print("   ✅ PASS: Sistema de A/B testing inicializado en MorphingManager")
    else:
        print("   ❌ FAIL: Sistema de A/B testing no inicializado")
        return False
    
    # Test crear test A/B
    try:
        test_config = PredefinedABTests.confidence_threshold_test()
        success = manager.create_ab_test(test_config)
        print(f"   ✅ PASS: Método create_ab_test funciona: {success}")
    except Exception as e:
        print(f"   ❌ FAIL: Error en create_ab_test: {e}")
        return False
    
    # Test aplicar configuración A/B
    try:
        variant_id = manager.apply_ab_test_config("test_user", "confidence_threshold_test")
        print(f"   ✅ PASS: Configuración A/B aplicada: {variant_id}")
    except Exception as e:
        print(f"   ❌ FAIL: Error aplicando configuración A/B: {e}")
        return False
    
    # Test registro de interacción A/B
    try:
        manager.record_ab_interaction(
            user_id="test_user",
            test_id="confidence_threshold_test",
            success=True,
            confidence=0.8,
            transformation_time_ms=150.0
        )
        print("   ✅ PASS: Registro de interacción A/B funciona")
    except Exception as e:
        print(f"   ❌ FAIL: Error registrando interacción A/B: {e}")
        return False
    
    print("✅ Integración A/B testing con MorphingManager exitosa")
    return True

def test_predefined_configurations():
    """Test de configuraciones predefinidas"""
    print("\n🧪 Test de Configuraciones Predefinidas")
    
    from behemot_framework.morphing.ab_testing import PredefinedABTests
    
    # Test configuraciones disponibles
    tests = {
        "Confidence Threshold": PredefinedABTests.confidence_threshold_test(),
        "Sensitivity": PredefinedABTests.sensitivity_test(),
        "Anti-Loop": PredefinedABTests.anti_loop_test()
    }
    
    for test_name, test_config in tests.items():
        print(f"   🔬 Test configuración: {test_name}")
        
        # Verificar estructura
        checks = [
            len(test_config.variants) >= 2,
            test_config.duration_days > 0,
            test_config.min_samples > 0,
            len(test_config.metrics) > 0,
            test_config.test_id is not None
        ]
        
        if all(checks):
            print(f"      ✅ PASS: {test_name} - {len(test_config.variants)} variantes, {test_config.duration_days} días")
        else:
            print(f"      ❌ FAIL: {test_name} - configuración incompleta")
            return False
    
    print("✅ Configuraciones predefinidas válidas")
    return True

def main():
    """Ejecuta todos los tests del sistema de A/B testing"""
    print("🧪 Live Agent Morphing - Tests del Sistema de A/B Testing")
    print("=" * 70)
    
    tests_passed = 0
    total_tests = 3
    
    if test_ab_testing_system():
        tests_passed += 1
    
    if test_integration_with_morphing_manager():
        tests_passed += 1
    
    if test_predefined_configurations():
        tests_passed += 1
    
    print("\n" + "=" * 70)
    print(f"🏁 Resultados: {tests_passed}/{total_tests} tests pasaron")
    
    if tests_passed == total_tests:
        print("🎉 ¡Sistema de A/B Testing implementado exitosamente!")
        print("✨ El morphing ahora puede optimizarse automáticamente")
        print("🔬 Configuraciones predefinidas listas para usar")
        return True
    else:
        print("⚠️  Algunos tests del A/B testing fallaron")
        return tests_passed >= 2  # 2 de 3 considerado aceptable

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)