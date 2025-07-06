#!/usr/bin/env python3
"""
Script de prueba básica para Live Agent Morphing - Fase 1
Valida que el sistema detecta triggers y cambia de morph correctamente.
"""

import sys
import os
sys.path.append('/home/hernandezbg/proyectos/behemot_framework_package')

from behemot_framework.config import Config
from behemot_framework.morphing import MorphingManager

def test_morphing_basic():
    """Prueba básica del sistema de morphing"""
    print("🧪 Iniciando pruebas de Live Agent Morphing - Fase 1")
    print("=" * 60)
    
    # Cargar configuración de prueba
    Config.initialize('/home/hernandezbg/proyectos/behemot_framework_package/ejemplo_morphing.yaml')
    
    # Crear manager de morphing
    morphing_config = Config.get("MORPHING", {})
    manager = MorphingManager(morphing_config)
    
    print(f"✅ MorphingManager creado")
    print(f"📋 Morphs disponibles: {manager.get_available_morphs()}")
    print(f"🎭 Morph actual: {manager.get_current_morph()}")
    print(f"🔛 Morphing habilitado: {manager.is_enabled()}")
    print()
    
    # Conversación de prueba inicial
    conversation = [
        {"role": "system", "content": "Eres un asistente útil"},
        {"role": "user", "content": "Hola, ¿cómo estás?"},
        {"role": "assistant", "content": "¡Hola! Estoy bien, ¿en qué puedo ayudarte?"}
    ]
    
    # Casos de prueba
    test_cases = [
        {
            "input": "Hola, ¿cómo estás?",
            "expected_morph": "general",
            "should_change": False
        },
        {
            "input": "Quiero comprar una laptop",
            "expected_morph": "sales",
            "should_change": True
        },
        {
            "input": "¿Cuánto cuesta ese producto?",
            "expected_morph": "sales", 
            "should_change": False  # Ya está en sales
        },
        {
            "input": "Mi computadora no funciona",
            "expected_morph": "support",
            "should_change": True
        },
        {
            "input": "Tengo un error en el sistema",
            "expected_morph": "support",
            "should_change": False  # Ya está en support
        },
        {
            "input": "Necesito ideas creativas",
            "expected_morph": "creative",
            "should_change": True
        },
        {
            "input": "Hola de nuevo",
            "expected_morph": "creative",
            "should_change": False  # No hay trigger, mantiene creative
        }
    ]
    
    print("🧪 Ejecutando casos de prueba:")
    print("-" * 40)
    
    passed = 0
    total = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        user_input = test_case["input"]
        expected_morph = test_case["expected_morph"]
        should_change = test_case["should_change"]
        
        print(f"\n🔬 Caso {i}: '{user_input}'")
        print(f"   Morph antes: {manager.get_current_morph()}")
        
        # Procesar mensaje
        result = manager.process_message(user_input, conversation)
        
        actual_morph = result["target_morph"]
        did_change = result["should_morph"]
        
        print(f"   Morph después: {actual_morph}")
        print(f"   ¿Cambió?: {did_change}")
        
        # Verificar resultados
        morph_correct = actual_morph == expected_morph
        change_correct = did_change == should_change
        
        if morph_correct and change_correct:
            print(f"   ✅ PASS")
            passed += 1
        else:
            print(f"   ❌ FAIL")
            if not morph_correct:
                print(f"      Esperaba morph: {expected_morph}, obtuvo: {actual_morph}")
            if not change_correct:
                print(f"      Esperaba cambio: {should_change}, obtuvo: {did_change}")
    
    print("\n" + "=" * 60)
    print(f"🏁 Resultados: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡Todas las pruebas pasaron! Live Agent Morphing Fase 1 funciona correctamente.")
        return True
    else:
        print(f"❌ {total - passed} pruebas fallaron. Revisar implementación.")
        return False

if __name__ == "__main__":
    success = test_morphing_basic()
    sys.exit(0 if success else 1)