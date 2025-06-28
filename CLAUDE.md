# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Comandos de Desarrollo

### Instalación
```bash
# Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.\.venv\Scripts\activate   # Windows

# Instalar el framework en modo desarrollo
pip install -e .
```

### Pruebas
```bash
# Ejecutar todas las pruebas (cuando se implementen)
pytest

# Ejecutar pruebas asíncronas
pytest -s -v --tb=short
```

### Desarrollo de Asistentes
```bash
# Crear nuevo proyecto de asistente
mkdir mi_asistente
cd mi_asistente
pip install -e ../behemot_framework

# Ejecutar asistente
uvicorn main:app --reload
```

## Arquitectura del Framework

### Estructura Principal
- **`factory.py`**: Punto de entrada principal. La `BehemotFactory` ensambla todos los componentes según la configuración.
- **`assistants/assistant.py`**: Núcleo que procesa las interacciones, gestiona contexto y orquesta herramientas.
- **`connectors/`**: Adaptadores para diferentes plataformas (API REST, Telegram, WhatsApp, Google Chat).
- **`rag/`**: Sistema completo de RAG con pipeline de procesamiento, embeddings y almacenamiento vectorial.
- **`tooling.py`**: Sistema de herramientas extensibles mediante decorador `@tool`.

### Flujo de Datos
1. **Conector** recibe mensaje → extrae datos → invoca **Assistant**
2. **Assistant** recupera contexto (Redis) → construye prompt → invoca **Model**
3. **Model** responde con texto o solicita ejecutar **Tool**
4. Si hay tool call → **Assistant** ejecuta → vuelve a invocar **Model**
5. Respuesta final → **Conector** formatea → envía a plataforma

### Sistema de Configuración
- Basado en archivos YAML con sobreescritura por variables de entorno
- Configuración típica incluye: modelo, prompt del sistema, herramientas, RAG, canales

### Extensibilidad
- **Nuevas herramientas**: Crear función con `@tool` en `tools/` del proyecto del asistente
- **Nuevos canales**: Activar en `create_behemot_app()` con credenciales correspondientes
- **RAG**: Activar con `ENABLE_RAG: true` y configurar fuentes de documentos

## Convenciones del Código

### Imports y Dependencias
- Verificar siempre que las librerías estén en `setup.py` antes de usarlas
- Usar imports relativos dentro del framework: `from behemot_framework.module import ...`

### Estilo de Código
- Seguir PEP 8 para Python
- Nombres descriptivos en español para configuración y documentación
- Nombres en inglés para código (clases, funciones, variables)
- Tipo hints cuando sea posible

### Seguridad
- No incluir API keys o tokens en el código
- Usar variables de entorno para credenciales (archivo `.env`)
- Validar entrada de usuarios antes de procesarla

### Herramientas (Tools)
- Usar decorador `@tool` con descripción clara
- Definir parámetros con `Param` incluyendo tipo y descripción
- Manejar casos de error y retornar mensajes útiles

## Patrones de Diseño

- **Factory Pattern**: `BehemotFactory` para construcción de aplicaciones
- **Adapter Pattern**: Conectores adaptan diferentes plataformas a interfaz común
- **Pipeline Pattern**: Sistema RAG procesa documentos en etapas
- **Dependency Injection**: Factory inyecta dependencias en componentes
- **Strategy Pattern**: ModelFactory permite cambiar proveedores de IA dinámicamente

## Integración de Múltiples Modelos

El framework ahora soporta múltiples proveedores de IA:

### Modelos Soportados
- **OpenAI**: GPT-4, GPT-4o, GPT-3.5-turbo
- **Google Gemini**: gemini-1.5-pro, gemini-1.5-flash

### Configuración de Modelo
```yaml
MODEL_PROVIDER: "gemini"  # openai, gemini
MODEL_NAME: "gemini-1.5-pro"
```

### Variables de Entorno
```bash
# OpenAI
GPT_API_KEY="sk-..."

# Gemini
GEMINI_API_KEY="AI..."
```

### Agregar Nuevo Proveedor
1. Crear clase que extienda `BaseModel` en `models/`
2. Implementar los 3 métodos: `generar_respuesta`, `generar_respuesta_con_functions`, `generar_respuesta_desde_contexto`
3. Registrar en ModelFactory: `ModelFactory.register_model("provider_name", ModelClass)`

## Sistema RAG con Múltiples Proveedores

El sistema RAG ahora soporta embeddings de múltiples proveedores:

### Proveedores de Embeddings Soportados
- **OpenAI**: `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`
- **Google**: `models/embedding-001`, `models/text-embedding-004`
- **HuggingFace**: Cualquier modelo de sentence-transformers

### Configuración RAG
```yaml
# Configuración RAG
ENABLE_RAG: true
RAG_EMBEDDING_PROVIDER: "google"  # openai, google, huggingface
RAG_EMBEDDING_MODEL: "models/embedding-001"

# Variables de entorno
GEMINI_API_KEY="AI..."  # Para embeddings de Google
```

### Combinaciones Recomendadas
- **Gemini + Google Embeddings**: `MODEL_PROVIDER: "gemini"` + `RAG_EMBEDDING_PROVIDER: "google"`
- **GPT + OpenAI Embeddings**: `MODEL_PROVIDER: "openai"` + `RAG_EMBEDDING_PROVIDER: "openai"`
- **Local**: `MODEL_PROVIDER: "cualquiera"` + `RAG_EMBEDDING_PROVIDER: "huggingface"`