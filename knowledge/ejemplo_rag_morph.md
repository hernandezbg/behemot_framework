# RAG + Morphing: Guía de Integración

## Cómo funciona RAG con Morphing

El sistema RAG (Retrieval Augmented Generation) puede configurarse de forma **global** o **por morph específico**.

### 1. Configuración Global de RAG

```yaml
# RAG global - afecta a TODOS los morphs
ENABLE_RAG: true
RAG_FOLDERS: ["docs", "knowledge_base", "manuales"]
RAG_EMBEDDING_PROVIDER: "openai"
RAG_EMBEDDING_MODEL: "text-embedding-3-small"
AUTO_RAG: true  # Búsqueda automática en cada consulta
```

### 2. Configuración por Morph

Cada morph puede tener su propia configuración RAG:

```yaml
morphs:
  support:
    # Configuración específica de RAG para este morph
    rag_config:
      enabled: true                    # RAG activo para support
      search_before_response: true     # Buscar siempre antes de responder
      min_confidence_score: 0.7        # Umbral de confianza
      max_results: 5                   # Máximo de resultados
      
  sales:
    # RAG deshabilitado para ventas
    rag_config:
      enabled: false  # Ventas usa solo herramientas, no RAG
```

### 3. Casos de Uso Típicos

#### Soporte Técnico con RAG
- **Busca automáticamente** en manuales y documentación
- **Respuestas precisas** basadas en información oficial
- **Cita fuentes** cuando encuentra información relevante

#### Ventas sin RAG
- Usa **herramientas específicas** (catálogo de productos)
- **Información dinámica** (precios, stock)
- No necesita buscar en documentos estáticos

#### Knowledge Expert (nuevo morph)
```yaml
knowledge_expert:
  personality: |
    Soy un experto en conocimiento corporativo.
    Mi especialidad es buscar y sintetizar información de nuestra base de conocimientos.
    Siempre cito mis fuentes y te indico de dónde proviene la información.
  
  rag_config:
    enabled: true
    search_before_response: true
    min_confidence_score: 0.8    # Más estricto
    max_results: 10              # Más resultados
    cite_sources: true           # Siempre citar fuentes
  
  instant_triggers:
    - "política de"
    - "procedimiento para"
    - "documentación sobre"
    - "manual de"
```

### 4. Flujo de Ejecución con RAG

```
1. Usuario: "Mi impresora no imprime"
2. Sistema detecta trigger → Support Morph
3. Support Morph tiene rag_config.enabled = true
4. Sistema busca automáticamente en:
   - /manuales/impresoras/
   - /knowledge_base/troubleshooting/
5. Encuentra: "Guía de solución de problemas HP"
6. Support Morph responde usando la información encontrada
```

### 5. Configuración de Carpetas por Morph

También puedes tener carpetas específicas por morph:

```yaml
# Configuración global
RAG_FOLDERS: ["docs/general"]

morphs:
  support:
    rag_config:
      enabled: true
      folders: ["docs/technical", "manuales", "troubleshooting"]
      
  legal:
    rag_config:
      enabled: true
      folders: ["docs/legal", "contratos", "políticas"]
      
  hr:
    rag_config:
      enabled: true
      folders: ["docs/hr", "procedimientos", "beneficios"]
```

### 6. Optimización de Performance

Para morphs que usan RAG intensivamente:

```yaml
support:
  model: "gpt-3.5-turbo"  # Modelo económico
  temperature: 0.3        # Respuestas precisas
  
  rag_config:
    enabled: true
    cache_results: true              # Cachear búsquedas frecuentes
    cache_ttl_minutes: 60           # Tiempo de vida del cache
    parallel_search: true           # Búsquedas paralelas
    chunk_overlap: 100              # Overlap entre chunks
```

### 7. Ejemplo Completo: Asistente Corporativo

```yaml
MORPHING:
  enabled: true
  morphs:
    # Morph general - Sin RAG
    general:
      rag_config:
        enabled: false
    
    # IT Support - RAG técnico
    it_support:
      rag_config:
        enabled: true
        folders: ["docs/it", "manuales/software"]
        search_before_response: true
    
    # HR Assistant - RAG de políticas
    hr:
      rag_config:
        enabled: true
        folders: ["docs/hr", "políticas"]
        cite_sources: true
    
    # Sales - Sin RAG, usa API de productos
    sales:
      rag_config:
        enabled: false
      tools: ["product_api", "pricing_api"]
```

## Mejores Prácticas

1. **No todos los morphs necesitan RAG**
   - Ventas: Mejor con APIs de productos
   - Creativo: Mejor sin restricciones de documentos
   - Soporte/Legal/HR: Ideal para RAG

2. **Ajusta el umbral de confianza**
   - Legal/Medical: 0.8-0.9 (alta precisión)
   - Support: 0.6-0.7 (balance)
   - General: 0.5 (más flexible)

3. **Organiza las carpetas por dominio**
   ```
   docs/
   ├── technical/
   ├── legal/
   ├── hr/
   ├── sales/
   └── general/
   ```

4. **Considera el costo**
   - RAG usa embeddings (costo adicional)
   - Configura `AUTO_RAG: false` si quieres control manual
   - Usa cache para consultas frecuentes