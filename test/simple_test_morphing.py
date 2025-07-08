#!/usr/bin/env python3
"""
Test simple del sistema de morphing sin dependencias externas
"""

import sys
import os
sys.path.append('/home/hernandezbg/proyectos/behemot_framework_package')

# Test directo de los componentes básicos
def test_instant_triggers():
    """Test del componente InstantMorphTriggers"""
    print("🧪 Test de InstantMorphTriggers")
    
    # Configuración de prueba
    morphs_config = {
        "sales": {
            "instant_triggers": ["quiero comprar", "precio", "oferta"]
        },
        "support": {
            "instant_triggers": ["no funciona", "error", "problema"]
        }
    }
    
    # Importar la clase directamente
    from behemot_framework.morphing.instant_triggers import InstantMorphTriggers
    
    triggers = InstantMorphTriggers(morphs_config)
    
    # Tests
    test_cases = [
        ("Hola", None),  # No debería triggear nada
        ("Quiero comprar algo", "sales"),  # Debería triggear sales
        ("Mi laptop no funciona", "support"),  # Debería triggear support
        ("¿Cuál es el precio?", "sales"),  # Debería triggear sales
        ("Tengo un problema", "support"),  # Debería triggear support
    ]
    
    passed = 0
    for input_text, expected in test_cases:
        result = triggers.check(input_text)
        actual = result.morph_name if result else None
        
        if actual == expected:
            print(f"   ✅ '{input_text}' → {actual}")
            passed += 1
        else:
            print(f"   ❌ '{input_text}' → esperaba: {expected}, obtuvo: {actual}")
    
    print(f"InstantTriggers: {passed}/{len(test_cases)} tests pasaron")
    return passed == len(test_cases)

def test_state_manager():
    """Test del MorphStateManager"""
    print("\n🧪 Test de MorphStateManager")
    
    from behemot_framework.morphing.state_manager import MorphStateManager
    
    manager = MorphStateManager()
    
    # Conversación de prueba
    conversation = [
        {"role": "system", "content": "Eres un asistente"},
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "¡Hola!"}
    ]
    
    # Preservar estado
    state = manager.preserve_state(conversation, "general")
    
    # Verificar que se preservó correctamente
    checks = [
        state.get('current_morph') == 'general',
        state.get('conversation_length') == 3,
        len(state.get('conversation_history', [])) == 3,
        'last_user_message' in state
    ]
    
    passed = sum(checks)
    print(f"   ✅ {passed}/4 verificaciones de preservación de estado pasaron")
    
    # Restaurar estado
    context = manager.restore_state(state, "sales")
    
    # Verificar restauración
    restore_checks = [
        'conversation' in context,
        context.get('previous_morph') == 'general',
        len(context.get('conversation', [])) == 3
    ]
    
    restore_passed = sum(restore_checks)
    print(f"   ✅ {restore_passed}/3 verificaciones de restauración pasaron")
    
    return passed == 4 and restore_passed == 3

def main():
    """Ejecuta todos los tests"""
    print("🎭 Live Agent Morphing - Tests de Componentes Básicos")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 2
    
    if test_instant_triggers():
        tests_passed += 1
    
    if test_state_manager():
        tests_passed += 1
    
    print("\n" + "=" * 60)
    print(f"🏁 Resultados: {tests_passed}/{total_tests} componentes funcionan correctamente")
    
    if tests_passed == total_tests:
        print("🎉 ¡Implementación básica del Live Agent Morphing funciona!")
        return True
    else:
        print("❌ Algunos componentes necesitan revisión")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)