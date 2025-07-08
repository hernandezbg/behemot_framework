# Ejemplo AUTO_RAG

## Configuración
Para habilitar AUTO_RAG, agregar en tu archivo de configuración YAML:

```yaml
# Habilitar RAG
ENABLE_RAG: true

# Habilitar AUTO_RAG
AUTO_RAG: true

# Configuración de AUTO_RAG
RAG_MAX_RESULTS: 3
RAG_SIMILARITY_THRESHOLD: 0.6

# Configuración de embeddings
RAG_EMBEDDING_PROVIDER: "google"  # o "openai", "huggingface"
RAG_EMBEDDING_MODEL: "models/embedding-001"

# Carpetas a indexar
RAG_FOLDERS: ["docs", "knowledge"]
```

## Variables de entorno
```bash
AUTO_RAG=true
RAG_MAX_RESULTS=3
RAG_SIMILARITY_THRESHOLD=0.6
```

## Funcionamiento

Cuando AUTO_RAG está habilitado:

1. **Usuario envía pregunta**: "¿Cómo configuro un webhook?"
2. **Sistema busca automáticamente** en documentos indexados usando la pregunta
3. **Encuentra documentos relevantes** sobre webhooks
4. **Agrega contexto al prompt** antes de generar respuesta
5. **El asistente responde** enriquecido con información de documentos

## Ventajas

- **Sin herramientas manuales**: No necesitas crear tools de búsqueda
- **Automático**: El framework decide cuándo buscar información
- **Transparente**: Se ejecuta en background sin interrumpir el flujo
- **Configurable**: Puedes ajustar número de resultados y umbral de similitud

## Comparación

### Sin AUTO_RAG (antes)
```python
@tool(name="buscar_docs", description="Busca información")
async def buscar_docs(params):
    # El desarrollador debe crear esta tool manualmente
    pass
```

### Con AUTO_RAG (ahora)
```yaml
AUTO_RAG: true
```
¡No necesitas código adicional!