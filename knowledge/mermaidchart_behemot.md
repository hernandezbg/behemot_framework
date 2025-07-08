# Diagrama de Flujo Actualizado - Behemot Framework con Morphing

```mermaid
graph TD
    subgraph "INICIALIZACIÓN DEL SISTEMA"
        A1[Arranque de la aplicación] --> A2[Carga de configuración]
        A2 --> A3[Inicialización de modelos]
        A2 --> A4[Inicialización de conectores]
        A2 --> A5[Carga de herramientas]
        A2 --> A6[Inicialización de RAG]
        A2 --> A11[Registro de comandos]
        A2 --> A12[Inicialización de Morphing]
        
        A3 --> A3A{Selección de modelo}
        A3A -->|OpenAI| A3B[GPT-4/GPT-3.5]
        A3A -->|Google| A3C[Gemini Pro/Flash]
        A3A -->|Vertex AI| A3D[Gemini en GCP]
        
        A6 --> A6A{RAG habilitado?}
        A6A -->|Sí| A7[Carga de documentos]
        A7 --> A7A{Fuente de documentos}
        A7A -->|Local| A7B[Archivos locales]
        A7A -->|GCP| A7C[Google Cloud Storage]
        
        A7B --> A8[División en chunks]
        A7C --> A8
        A8 --> A9[Generación de embeddings]
        
        A9 --> A9A{Proveedor embeddings}
        A9A -->|OpenAI| A9B[text-embedding-3]
        A9A -->|Google| A9C[embedding-001]
        A9A -->|HuggingFace| A9D[sentence-transformers]
        
        A9B --> A10[Almacenamiento en Chroma DB]
        A9C --> A10
        A9D --> A10
        
        A12 --> A12A{Morphing habilitado?}
        A12A -->|Sí| A12B[Cargar configuración morphs]
        A12B --> A12C[Inicializar triggers]
        A12B --> A12D[Inicializar analizador gradual]
        A12B --> A12E[Inicializar sistema feedback]
        A12B --> A12F[Inicializar A/B testing]
        
        A12E --> R3[(Redis para feedback)]
        A12F --> R3
    end
    
    subgraph "PROCESAMIENTO DE MENSAJE"
        B1(Mensaje del cliente) --> B2[API Endpoint]
        B2 --> B3[Extracción del mensaje]
        
        B3 --> B3A{¿Es comando especial?}
        B3A -->|Sí &comando| CM1[CommandHandler]
        
        CM1 --> CM2[Procesamiento de comandos]
        CM2 --> CM3{Selección de comando}
        
        CM3 -->|&status| CM4[Estado del sistema]
        CM3 -->|&monitor| CM5[Monitoreo en tiempo real]
        CM3 -->|&analyze_session| CM6[Análisis de sesión]
        CM3 -->|&clear_msg| CM7[Limpiar mensajes]
        CM3 -->|&help| CM8[Lista de comandos]
        CM3 -->|&reset_to_fabric| CM9[Reset completo]
        CM3 -->|&morphing_stats| CM10A[Estadísticas morphing]
        CM3 -->|&ab_results| CM10B[Resultados A/B test]
        
        CM4 --> CM10[Respuesta administrativa]
        CM5 --> CM10
        CM6 --> CM10
        CM7 --> CM10
        CM8 --> CM10
        CM9 --> CM10
        CM10A --> CM10
        CM10B --> CM10
        
        CM10 --> F6
        
        B3A -->|No| B4[Filtro de seguridad de entrada]
        B4 --> B5[Obtención del historial]
        B5 --> R1[(Redis)]
        R1 --> B6[Construcción de contexto inicial]
        
        B6 --> M1{Morphing activo?}
        M1 -->|Sí| M2[MorphingManager]
        M1 -->|No| B7
        
        M2 --> M2A[Aplicar config A/B test]
        M2A --> M3[Instant triggers check]
        M3 --> M3A{¿Trigger detectado?}
        M3A -->|Sí 0ms| M7[Ejecutar transformación]
        M3A -->|No| M4[Análisis gradual]
        
        M4 --> M4A[Análisis multi-dimensional]
        M4A --> M4B[Keywords + Intent + Context]
        M4B --> M4C{¿Confianza > umbral?}
        M4C -->|Sí 150ms| M5[Aplicar ajustes aprendidos]
        M5 --> M6{¿Anti-loop OK?}
        M6 -->|Sí| M7
        M6 -->|No| M8[Bloquear cambio]
        M4C -->|No| M8
        
        M7 --> M9[Cambiar personalidad]
        M9 --> M10[Preservar contexto]
        M10 --> M11[Transición suave]
        M11 --> M12[Registrar métricas]
        M12 --> M13[Actualizar contexto]
        M13 --> B7
        
        M8 --> B7
        
        B7 --> B7A{AUTO_RAG activo?}
        B7A -->|Sí| AR1[Búsqueda automática RAG]
        AR1 --> AR2[Enriquecer contexto]
        AR2 --> B8
        B7A -->|No| B8
        
        B8[Llamada al modelo IA] --> B8A{Respuesta con herramientas?}
        
        B8A -->|Requiere herramientas| D1[Flujo de herramientas]
        B8A -->|No requiere herramientas| E1[Respuesta directa]
        
        D1 --> D2[Selección de herramienta]
        
        D2 -->|Herramienta RAG| C1[Herramientas con RAG]
        D2 -->|Herramienta externa| D3[Herramientas con datos externos]
        
        C1 --> C2[RAG Manager]
        C2 --> C3[Convertir consulta a embedding]
        C3 --> C4[Búsqueda en Chroma DB]
        C4 --> C5[Recuperar documentos relevantes]
        C5 --> C6[Formatear documentos]
        C6 --> F1
        
        D3 --> D4[Ejecución de herramienta]
        D4 --> D5[Obtención de datos externos]
        D5 --> D6[Formateo de resultados]
        D6 --> F1
        
        F1[Enriquecimiento del contexto] --> F2
        E1 --> FB1
        
        F2[Segunda llamada al modelo] --> F3[Respuesta generada]
        F3 --> FB1
        
        FB1{Morphing activo?}
        FB1 -->|Sí| FB2[Detectar feedback implícito]
        FB2 --> FB3[Registrar feedback]
        FB3 --> FB4[Actualizar confianza]
        FB4 --> FB5[Registrar A/B metrics]
        FB5 --> F4
        FB1 -->|No| F4
        
        F4[Filtro de seguridad de salida]
        F4 --> F5[Guardado del historial]
        F5 --> R2[(Redis)]
        
        F5 --> F6[Formateo de respuesta API]
        F6 --> F7[Envío de respuesta al cliente]
    end
    
    subgraph "SISTEMA DE MEJORA CONTINUA"
        MC1[Feedback acumulado] --> MC2[Análisis de patrones]
        MC2 --> MC3[Ajustes de confianza]
        MC3 --> MC4[Aplicar a futuras decisiones]
        
        AB1[Resultados A/B test] --> AB2[Análisis estadístico]
        AB2 --> AB3[Identificar ganador]
        AB3 --> AB4[Aplicar config óptima]
        
        MC4 --> M5
        AB4 --> M2A
    end
    
    classDef initialNodes fill:#ffd,stroke:#aa3,stroke-width:2px
    classDef apiNodes fill:#bbf,stroke:#33f,stroke-width:2px
    classDef processingNodes fill:#afa,stroke:#3a3,stroke-width:2px
    classDef modelNodes fill:#aaf,stroke:#33a,stroke-width:2px
    classDef ragNodes fill:#faa,stroke:#a55,stroke-width:2px
    classDef toolNodes fill:#aca,stroke:#383,stroke-width:2px
    classDef storageNodes fill:#fea,stroke:#a83,stroke-width:2px
    classDef securityNodes fill:#fcc,stroke:#c55,stroke-width:2px
    classDef contextNodes fill:#cff,stroke:#3cc,stroke-width:3px
    classDef commandNodes fill:#fcf,stroke:#c5c,stroke-width:2px
    classDef morphingNodes fill:#e6f,stroke:#93c,stroke-width:3px
    classDef feedbackNodes fill:#def,stroke:#67a,stroke-width:2px
    classDef abTestNodes fill:#efd,stroke:#9a6,stroke-width:2px
    
    class A1,A2,A3,A4,A5,A6,A7,A8,A9,A10,A11,A12 initialNodes
    class A3A,A3B,A3C,A3D,A6A,A7A,A7B,A7C,A9A,A9B,A9C,A9D modelNodes
    class A12A,A12B,A12C,A12D,A12E,A12F morphingNodes
    class B1,B2,F6,F7 apiNodes
    class B3,B3A,B5,B6,F5 processingNodes
    class B7,B8,F2,F3 modelNodes
    class B7A,AR1,AR2 ragNodes
    class C1,C2,C3,C4,C5,C6 ragNodes
    class D1,D2,D3,D4,D5,D6 toolNodes
    class R1,R2,R3 storageNodes
    class B4,F4 securityNodes
    class F1 contextNodes
    class E1 processingNodes
    class CM1,CM2,CM3,CM4,CM5,CM6,CM7,CM8,CM9,CM10,CM10A,CM10B commandNodes
    class M1,M2,M2A,M3,M3A,M4,M4A,M4B,M4C,M5,M6,M7,M8,M9,M10,M11,M12,M13 morphingNodes
    class FB1,FB2,FB3,FB4,FB5 feedbackNodes
    class MC1,MC2,MC3,MC4 feedbackNodes
    class AB1,AB2,AB3,AB4 abTestNodes
```

## 📊 Leyenda de Colores

- 🟡 **Amarillo** (initialNodes): Inicialización del sistema
- 🔵 **Azul claro** (apiNodes): Endpoints API y comunicación
- 🟢 **Verde** (processingNodes): Procesamiento general
- 🔷 **Azul** (modelNodes): Modelos de IA y llamadas
- 🔴 **Rojo** (ragNodes): Sistema RAG
- 🟣 **Verde oscuro** (toolNodes): Herramientas externas
- 🟠 **Naranja** (storageNodes): Almacenamiento (Redis)
- 🔺 **Rosa** (securityNodes): Filtros de seguridad
- 🔵 **Cyan** (contextNodes): Enriquecimiento de contexto
- 🟪 **Púrpura** (commandNodes): Comandos administrativos
- 🟣 **Violeta** (morphingNodes): Sistema de Morphing
- 🔷 **Azul claro** (feedbackNodes): Sistema de Feedback
- 🟨 **Amarillo claro** (abTestNodes): A/B Testing

## 🔄 Nuevos Flujos Agregados

### 1. **Inicialización Morphing**
- Carga de configuración de morphs
- Inicialización de triggers instantáneos
- Configuración del analizador gradual
- Conexión con Redis para feedback y A/B testing

### 2. **Procesamiento Morphing**
- Aplicación de configuración A/B test
- Detección instantánea (0ms)
- Análisis gradual multi-dimensional (150ms)
- Anti-loop protection
- Preservación y transición de contexto

### 3. **Sistema de Feedback**
- Detección automática de feedback implícito
- Registro en Redis
- Actualización de confianza
- Métricas para A/B testing

### 4. **Mejora Continua**
- Análisis de patrones de feedback
- Optimización automática con A/B testing
- Aplicación de configuraciones ganadoras

### 5. **Comandos Nuevos**
- `&morphing_stats`: Estadísticas del sistema de morphing
- `&ab_results`: Resultados de tests A/B activos

### 6. **Multi-Provider Support**
- OpenAI (GPT-4, GPT-3.5)
- Google Gemini (Pro, Flash)
- Vertex AI
- Embeddings: OpenAI, Google, HuggingFace

### 7. **AUTO_RAG**
- Búsqueda automática antes de responder
- Enriquecimiento transparente del contexto