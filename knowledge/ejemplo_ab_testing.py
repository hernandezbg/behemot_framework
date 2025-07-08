#!/usr/bin/env python3
"""
Ejemplo de uso del Sistema de A/B Testing para Live Agent Morphing
Muestra cómo configurar y usar tests A/B en producción.
"""

import sys
sys.path.append('/home/hernandezbg/proyectos/behemot_framework_package')

from behemot_framework.morphing.ab_testing import ABTestConfig, PredefinedABTests

def ejemplo_configuracion_ab_test():
    """Ejemplo de cómo configurar un test A/B personalizado"""
    
    print("🔬 Ejemplo: Configuración de Test A/B Personalizado")
    print("=" * 60)
    
    # Ejemplo 1: Test de umbrales de confianza
    confidence_test = ABTestConfig(
        test_id="confidence_optimization_2024",
        name="Optimización de Umbral de Confianza",
        description="Encuentra el umbral óptimo para transformaciones graduales",
        variants=[
            {
                "name": "Conservative",
                "gradual_layer": {"confidence_threshold": 0.8},
                "description": "Umbral alto - solo transformaciones muy seguras"
            },
            {
                "name": "Balanced", 
                "gradual_layer": {"confidence_threshold": 0.6},
                "description": "Umbral medio - balance entre precisión y cobertura"
            },
            {
                "name": "Aggressive",
                "gradual_layer": {"confidence_threshold": 0.4},
                "description": "Umbral bajo - más transformaciones, posible menor precisión"
            }
        ],
        metrics=["transformation_success", "user_satisfaction", "precision", "coverage"],
        duration_days=14,
        min_samples=200,
        confidence_level=0.95
    )
    
    print(f"📋 Test ID: {confidence_test.test_id}")
    print(f"🎯 Objetivo: {confidence_test.description}")
    print(f"📊 Variantes: {len(confidence_test.variants)}")
    print(f"⏱️  Duración: {confidence_test.duration_days} días")
    print(f"📈 Métricas: {', '.join(confidence_test.metrics)}")
    
    for i, variant in enumerate(confidence_test.variants):
        threshold = variant["gradual_layer"]["confidence_threshold"]
        print(f"   Variante {i+1}: {variant['name']} (umbral: {threshold})")
        print(f"   └─ {variant['description']}")
    
    return confidence_test

def ejemplo_test_sensibilidad():
    """Ejemplo de test de sensibilidad del sistema"""
    
    print("\n🔬 Ejemplo: Test de Sensibilidad del Sistema")
    print("=" * 60)
    
    sensitivity_test = ABTestConfig(
        test_id="sensitivity_optimization_2024",
        name="Optimización de Sensibilidad del Morphing",
        description="Encuentra el nivel de sensibilidad óptimo para diferentes tipos de usuarios",
        variants=[
            {
                "name": "Low_Sensitivity",
                "settings": {"sensitivity": "low"},
                "gradual_layer": {"confidence_threshold": 0.8},
                "advanced": {
                    "instant_layer": {"case_sensitive": False},
                    "gradual_layer": {"analyze_last_messages": 2}
                },
                "target_users": "usuarios_conservadores"
            },
            {
                "name": "Medium_Sensitivity", 
                "settings": {"sensitivity": "medium"},
                "gradual_layer": {"confidence_threshold": 0.6},
                "advanced": {
                    "instant_layer": {"case_sensitive": False},
                    "gradual_layer": {"analyze_last_messages": 3}
                },
                "target_users": "usuarios_generales"
            },
            {
                "name": "High_Sensitivity",
                "settings": {"sensitivity": "high"},
                "gradual_layer": {"confidence_threshold": 0.4},
                "advanced": {
                    "instant_layer": {"case_sensitive": True},
                    "gradual_layer": {"analyze_last_messages": 5}
                },
                "target_users": "usuarios_power"
            }
        ],
        metrics=["transformation_frequency", "accuracy", "user_experience", "conversation_flow"],
        duration_days=21,
        min_samples=300
    )
    
    print(f"📋 Test ID: {sensitivity_test.test_id}")
    print(f"🎯 Objetivo: {sensitivity_test.description}")
    print(f"👥 Segmentación: Por tipo de usuario")
    
    for variant in sensitivity_test.variants:
        sens = variant["settings"]["sensitivity"]
        threshold = variant["gradual_layer"]["confidence_threshold"]
        target = variant["target_users"]
        print(f"   • {variant['name']}: sensibilidad {sens}, umbral {threshold}")
        print(f"     └─ Target: {target}")
    
    return sensitivity_test

def ejemplo_configuracion_yaml():
    """Ejemplo de cómo configurar A/B testing en YAML"""
    
    print("\n📄 Ejemplo: Configuración YAML con A/B Testing")
    print("=" * 60)
    
    yaml_example = """
# config/mi_asistente.yaml
MODEL_PROVIDER: "openai"
MODEL_NAME: "gpt-4o-mini"

PROMPT_SISTEMA: |
  Eres un asistente inteligente con capacidades de transformación.

# MORPHING con A/B Testing
MORPHING:
  enabled: true
  default_morph: "general"
  
  # A/B Testing Configuration
  ab_testing:
    enabled: true
    active_tests:
      - "confidence_optimization_2024"
      - "sensitivity_optimization_2024"
    
    # Tests automáticos
    auto_tests:
      confidence_threshold:
        enabled: true
        variants: [0.4, 0.6, 0.8]
        duration_days: 14
        min_samples: 200
        
      sensitivity:
        enabled: true
        variants: ["low", "medium", "high"] 
        duration_days: 21
        min_samples: 300
  
  morphs:
    general:
      personality: "Asistente general amigable"
      
    sales:
      personality: "Asesor de ventas entusiasta"
      instant_triggers: ["comprar", "precio"]
      gradual_triggers:
        keywords: ["producto", "oferta"]
        min_score: 2
      
    support:
      personality: "Técnico paciente y metódico"
      instant_triggers: ["no funciona", "error"]
      gradual_triggers:
        keywords: ["problema", "lento"]
        min_score: 1
"""
    
    print(yaml_example)

def ejemplo_flujo_produccion():
    """Ejemplo del flujo completo en producción"""
    
    print("\n🚀 Ejemplo: Flujo en Producción")
    print("=" * 60)
    
    flujo = """
1. 📋 CONFIGURACIÓN INICIAL
   ┌─ Crear test A/B con PredefinedABTests.confidence_threshold_test()
   ├─ Configurar duración y métricas objetivo
   └─ Activar test en producción

2. 👥 ASIGNACIÓN DE USUARIOS
   ┌─ Usuario A → Variante 1 (umbral 0.4)
   ├─ Usuario B → Variante 2 (umbral 0.6)  
   └─ Usuario C → Variante 3 (umbral 0.8)

3. 📊 RECOLECCIÓN DE DATOS
   ┌─ Cada interacción registra:
   │  ├─ Éxito/fallo de la transformación
   │  ├─ Nivel de confianza
   │  ├─ Tiempo de transformación
   │  └─ Métricas personalizadas
   └─ Almacenamiento automático en Redis

4. 📈 ANÁLISIS AUTOMÁTICO
   ┌─ Análisis estadístico en tiempo real
   ├─ Identificación de variante ganadora
   ├─ Cálculo de significancia estadística
   └─ Recomendaciones automáticas

5. 🏆 OPTIMIZACIÓN
   ┌─ Aplicar configuración ganadora
   ├─ Gradual rollout de la configuración óptima
   └─ Nuevo test A/B para siguiente optimización

6. 🔄 MEJORA CONTINUA
   └─ Ciclo automático de optimización
      ├─ Test semanal/mensual automático
      ├─ Métricas de negocio integradas
      └─ Aprendizaje continuo del sistema
"""
    
    print(flujo)

def ejemplo_metricas_negocio():
    """Ejemplo de métricas de negocio relevantes"""
    
    print("\n📊 Ejemplo: Métricas de Negocio")
    print("=" * 60)
    
    metricas = {
        "Precisión del Morphing": {
            "descripción": "% de transformaciones correctas",
            "objetivo": "> 90%",
            "impacto": "Experiencia de usuario"
        },
        "Tiempo de Respuesta": {
            "descripción": "Latencia promedio de transformación",
            "objetivo": "< 200ms",
            "impacto": "Performance percibida"
        },
        "Satisfacción del Usuario": {
            "descripción": "Rating implícito de satisfacción",
            "objetivo": "> 4.5/5.0",
            "impacto": "Retención de usuarios"
        },
        "Cobertura de Transformaciones": {
            "descripción": "% de mensajes que activan morphing",
            "objetivo": "30-50%",
            "impacto": "Utilidad del sistema"
        },
        "Reducción de Escalaciones": {
            "descripción": "% menos derivaciones a humanos",
            "objetivo": "> 25%",
            "impacto": "Costo operativo"
        },
        "Tiempo de Resolución": {
            "descripción": "Promedio de mensajes para resolver",
            "objetivo": "< 3 mensajes",
            "impacto": "Eficiencia conversacional"
        }
    }
    
    for metrica, info in metricas.items():
        print(f"📊 {metrica}")
        print(f"   └─ {info['descripción']}")
        print(f"   └─ Objetivo: {info['objetivo']}")
        print(f"   └─ Impacto: {info['impacto']}")
        print()

def main():
    """Ejecuta todos los ejemplos"""
    print("🧪 Live Agent Morphing - Ejemplos de A/B Testing")
    print("=" * 70)
    
    # Ejemplos de configuración
    confidence_test = ejemplo_configuracion_ab_test()
    sensitivity_test = ejemplo_test_sensibilidad()
    
    # Configuración YAML
    ejemplo_configuracion_yaml()
    
    # Flujo de producción
    ejemplo_flujo_produccion()
    
    # Métricas de negocio
    ejemplo_metricas_negocio()
    
    print("\n🎯 Tests Predefinidos Disponibles:")
    print("=" * 60)
    
    predefined = [
        ("Umbral de Confianza", PredefinedABTests.confidence_threshold_test()),
        ("Sensibilidad", PredefinedABTests.sensitivity_test()),
        ("Anti-Loop Protection", PredefinedABTests.anti_loop_test())
    ]
    
    for name, test in predefined:
        print(f"🔬 {name}")
        print(f"   └─ ID: {test.test_id}")
        print(f"   └─ Variantes: {len(test.variants)}")
        print(f"   └─ Duración: {test.duration_days} días")
        print(f"   └─ Métricas: {', '.join(test.metrics)}")
        print()
    
    print("✨ ¡A/B Testing listo para optimizar tu morphing automáticamente!")

if __name__ == "__main__":
    main()