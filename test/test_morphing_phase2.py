#!/usr/bin/env python3
"""
Test avanzado para Live Agent Morphing - Fase 2
Prueba el sistema híbrido de instant + gradual triggers, métricas y anti-loop protection.
"""

import sys
import os
sys.path.append('/home/hernandezbg/proyectos/behemot_framework_package')

def test_gradual_analyzer():
    """Test del analizador gradual"""
    print("🧪 Test de GradualMorphAnalyzer")
    
    from behemot_framework.morphing.gradual_analyzer import GradualMorphAnalyzer
    
    # Configuración de prueba
    morphs_config = {
        "sales": {
            "gradual_triggers": {
                "keywords": ["producto", "comparar", "mejor opción"],
                "intents": ["purchase_inquiry"],
                "min_score": 2
            }
        },
        "support": {
            "gradual_triggers": {
                "keywords": ["lento", "instalación", "configuración"],
                "intents": ["support_request"],
                "min_score": 2
            }
        }
    }
    
    analyzer = GradualMorphAnalyzer(morphs_config)
    
    # Conversación de prueba
    conversation = [
        {"role": "system", "content": "Eres un asistente"},
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "¡Hola! ¿En qué puedo ayudarte?"},
        {"role": "user", "content": "Estoy buscando el mejor producto para mi negocio"}
    ]
    
    # Tests graduales
    test_cases = [
        {
            "input": "Necesito comparar productos para encontrar la mejor opción",
            "expected_morph": "sales",
            "should_detect": True
        },
        {
            "input": "Mi aplicación está muy lenta después de la instalación",
            "expected_morph": "support", 
            "should_detect": True
        },
        {
            "input": "¿Cómo estás hoy?",
            "expected_morph": None,
            "should_detect": False
        }
    ]
    
    passed = 0
    for i, test_case in enumerate(test_cases, 1):
        user_input = test_case["input"]
        expected_morph = test_case["expected_morph"]
        should_detect = test_case["should_detect"]
        
        result = analyzer.analyze(user_input, conversation, "general")
        
        if should_detect:
            detected = result is not None and result.get('morph_name') == expected_morph
        else:
            detected = result is None
        
        if detected:
            print(f"   ✅ Caso {i}: '{user_input[:30]}...' → {expected_morph if should_detect else 'Sin cambio'}")
            passed += 1
        else:
            print(f"   ❌ Caso {i}: '{user_input[:30]}...' → Esperaba: {expected_morph}, Obtuvo: {result.get('morph_name') if result else None}")
    
    print(f"GradualAnalyzer: {passed}/{len(test_cases)} tests pasaron")
    return passed == len(test_cases)

def test_hybrid_system():
    """Test del sistema híbrido completo"""
    print("\n🧪 Test del Sistema Híbrido (Instant + Gradual)")
    
    from behemot_framework.morphing.morphing_manager import MorphingManager
    
    # Configuración completa para pruebas
    morphing_config = {
        "enabled": True,
        "default_morph": "general",
        "settings": {
            "transition_style": "seamless"
        },
        "advanced": {
            "gradual_layer": {
                "enabled": True,
                "confidence_threshold": 0.3  # Umbral más bajo para testing
            },
            "transitions": {
                "prevent_morphing_loops": True
            }
        },
        "morphs": {
            "general": {
                "personality": "Asistente general"
            },
            "sales": {
                "instant_triggers": ["quiero comprar"],
                "gradual_triggers": {
                    "keywords": ["producto", "comparar"],
                    "min_score": 2
                }
            },
            "support": {
                "instant_triggers": ["no funciona"],
                "gradual_triggers": {
                    "keywords": ["lento", "problema"],
                    "min_score": 1
                }
            }
        }
    }
    
    manager = MorphingManager(morphing_config)
    conversation = [{"role": "system", "content": "Test"}]
    
    # Tests del sistema híbrido
    test_cases = [
        {
            "input": "Quiero comprar algo",
            "expected_morph": "sales",
            "expected_layer": "instant",
            "description": "Instant trigger para sales"
        },
        {
            "input": "Mi computadora no funciona",
            "expected_morph": "support",
            "expected_layer": "instant", 
            "description": "Instant trigger para support"
        },
        {
            "input": "Necesito comparar varios productos",
            "expected_morph": "sales",
            "expected_layer": "gradual",
            "description": "Gradual trigger para sales"
        },
        {
            "input": "Todo está muy lento",
            "expected_morph": "support",
            "expected_layer": "gradual",
            "description": "Gradual trigger para support"
        },
        {
            "input": "Hola, ¿cómo estás?",
            "expected_morph": "support",  # Debería mantener el anterior 
            "expected_layer": "none",
            "description": "Sin triggers, mantiene actual"
        }
    ]
    
    passed = 0
    for i, test_case in enumerate(test_cases, 1):
        user_input = test_case["input"]
        expected_morph = test_case["expected_morph"]
        description = test_case["description"]
        
        print(f"   🔬 Caso {i}: {description}")
        print(f"      Input: '{user_input}'")
        print(f"      Morph antes: {manager.get_current_morph()}")
        
        result = manager.process_message(user_input, conversation)
        actual_morph = result["target_morph"]
        
        print(f"      Morph después: {actual_morph}")
        
        if actual_morph == expected_morph:
            print(f"      ✅ PASS")
            passed += 1
        else:
            print(f"      ❌ FAIL - Esperaba: {expected_morph}")
    
    print(f"Sistema Híbrido: {passed}/{len(test_cases)} tests pasaron")
    return passed == len(test_cases)

def test_metrics():
    """Test del sistema de métricas"""
    print("\n🧪 Test de Métricas")
    
    from behemot_framework.morphing.metrics import MorphMetrics
    
    metrics = MorphMetrics()
    
    # Simulo algunas transformaciones
    metrics.record_transformation("general", "sales", "instant", 1.0, True, 50.0)
    metrics.record_transformation("sales", "support", "gradual", 0.7, True, 150.0)
    metrics.record_transformation("support", "sales", "instant", 0.9, False, 75.0)
    
    # Simulo anti-loop blocks
    metrics.record_anti_loop_block("sales")
    
    # Obtengo estadísticas
    stats = metrics.get_summary_stats()
    
    # Verificaciones
    checks = [
        stats['total_transformations'] == 3,
        stats['success_rate'] == 66.7,  # 2 de 3 exitosas
        stats['instant_vs_gradual']['instant'] == 2,
        stats['instant_vs_gradual']['gradual'] == 1,
        stats['anti_loop_blocks'] == 1,
        'sales' in stats['most_used_morphs']
    ]
    
    passed_checks = sum(checks)
    print(f"   ✅ {passed_checks}/6 verificaciones de métricas pasaron")
    
    # Test métricas por morph
    sales_stats = metrics.get_morph_stats("sales")
    morph_checks = [
        sales_stats['usage_count'] == 2,  # Usado como destino 2 veces
        sales_stats['total_attempts'] == 2
    ]
    
    passed_morph = sum(morph_checks)
    print(f"   ✅ {passed_morph}/2 verificaciones de morph específico pasaron")
    
    return passed_checks == 6 and passed_morph == 2

def test_anti_loop_protection():
    """Test de protección anti-loop"""
    print("\n🧪 Test de Anti-Loop Protection")
    
    from behemot_framework.morphing.morphing_manager import MorphingManager
    
    # Configuración que permitiría loops sin protección
    config = {
        "enabled": True,
        "default_morph": "general",
        "advanced": {
            "transitions": {
                "prevent_morphing_loops": True
            }
        },
        "morphs": {
            "general": {},
            "sales": {
                "instant_triggers": ["test"]
            }
        }
    }
    
    manager = MorphingManager(config)
    conversation = [{"role": "system", "content": "Test"}]
    
    # Intento causar un loop
    loop_attempts = 0
    for i in range(5):
        result = manager.process_message("test", conversation)
        if result["should_morph"]:
            loop_attempts += 1
    
    # Verifico que el anti-loop funcionó
    if loop_attempts < 5:
        print(f"   ✅ Anti-loop protection funcionó: solo {loop_attempts}/5 cambios permitidos")
        return True
    else:
        print(f"   ❌ Anti-loop protection falló: {loop_attempts}/5 cambios permitidos")
        return False

def main():
    """Ejecuta todos los tests de Fase 2"""
    print("🎭 Live Agent Morphing - Tests Fase 2 (Análisis Inteligente)")
    print("=" * 70)
    
    tests_passed = 0
    total_tests = 4
    
    if test_gradual_analyzer():
        tests_passed += 1
    
    if test_hybrid_system():
        tests_passed += 1
    
    if test_metrics():
        tests_passed += 1
    
    if test_anti_loop_protection():
        tests_passed += 1
    
    print("\n" + "=" * 70)
    print(f"🏁 Resultados Fase 2: {tests_passed}/{total_tests} sistemas funcionan correctamente")
    
    if tests_passed == total_tests:
        print("🎉 ¡Fase 2 del Live Agent Morphing implementada exitosamente!")
        print("✨ Sistema híbrido con análisis inteligente funcionando")
        return True
    else:
        print("❌ Algunos sistemas de Fase 2 necesitan revisión")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)