# Behemot Framework

**Framework modular para crear asistentes IA multimodales**

La filosofía es simple: **el framework proporciona el motor; tú proporcionas la personalidad (configuración) y las habilidades (herramientas).**

## 🚀 Inicio Rápido

### Paso 1: Crear el Proyecto

```bash
# Crear directorio del proyecto
mkdir mi_asistente
cd mi_asistente

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### Paso 2: Instalar Behemot Framework

```bash
pip install git+https://github.com/hernandezbg/behemot_framework.git
```

### Paso 3: Generar Estructura del Proyecto

```bash
behemot-admin create-agent mi_asistente
```

Este comando crea automáticamente:
- `config/mi_asistente.yaml` - Configuración del asistente
- `tools/` - Directorio para herramientas personalizadas
- `main.py` - Punto de entrada principal
- `.env.example` - Plantilla de variables de entorno
- `README.md` - Documentación del proyecto

### Paso 4: Configurar Variables de Entorno

```bash
cp .env.example .env
# Editar .env con tus API keys
```

### Paso 5: Ejecutar tu Asistente

```bash
python main.py
```

¡Tu asistente estará corriendo en http://localhost:8000!

## 🛠️ Personalización Avanzada

### Configuración del Asistente

Edita `config/mi_asistente.yaml` para personalizar tu asistente:

```yaml
# Configuración del modelo
MODEL_PROVIDER: "openai"  # openai, gemini, vertex
MODEL_NAME: "gpt-4o-mini"

# Prompt del sistema - Define la personalidad de tu asistente
PROMPT_SISTEMA: |
  Eres un asistente especializado en [tu dominio].
  Siempre eres amable, preciso y útil.
  
# Configuración de seguridad
SAFETY_LEVEL: "medium"  # low, medium, high

# RAG (Retrieval Augmented Generation) - Conocimiento personalizado
ENABLE_RAG: true
RAG_FOLDERS: ["./docs"]  # Carpetas locales, gcp://bucket/path, s3://bucket/key
RAG_EMBEDDING_PROVIDER: "openai"  # openai, google, huggingface
```

### Crear Herramientas Personalizadas

Las herramientas son las "habilidades" de tu asistente. Créalas en el directorio `tools/`:

**`tools/mi_herramienta.py`:**
```python
from behemot_framework.tooling import tool, Param

@tool(
    "mi_herramienta",
    "Descripción de lo que hace la herramienta",
    [
        Param("parametro", "string", "Descripción del parámetro", required=True)
    ]
)
async def mi_herramienta(parametro: str):
    # Tu lógica aquí
    return f"Resultado procesando: {parametro}"
```

Luego agrégala a `main.py`:
```python
app = create_behemot_app(
    # ... otras configuraciones
    use_tools=["mi_herramienta"],  # Agregar aquí
)
```

### Habilitar RAG (Conocimiento Personalizado)

Agrega documentos a tu asistente para que responda basándose en tu contenido:

```yaml
# En config/mi_asistente.yaml
ENABLE_RAG: true
RAG_FOLDERS: ["./docs", "gcp://mi-bucket/documentos", "s3://bucket/archivos"]
```

**Formatos soportados**: PDF, TXT, Markdown, CSV, URLs
**El asistente leerá automáticamente** todo el contenido y podrá responder preguntas sobre tus documentos.

### Habilitar Canales de Comunicación

En `main.py`, activa los canales que necesites:

```python
app = create_behemot_app(
    enable_api=True,          # API REST
    enable_telegram=True,     # Bot de Telegram
    enable_whatsapp=True,     # WhatsApp Business
    enable_google_chat=True,  # Google Chat
    enable_voice=True,        # Procesamiento de voz
    enable_test_local=True,   # Interfaz de prueba local con Gradio
    config_path="config/mi_asistente.yaml",
)
```

### Interfaz de Prueba Local

Para probar tu asistente de forma visual antes de desplegarlo:

```python
# En main.py
app = create_behemot_app(
    enable_test_local=True,   # Activar interfaz visual
    config_path="config/mi_asistente.yaml",
)
```

Esto creará una interfaz web en http://localhost:7860 con:
- 💬 **Chat interactivo con tema oscuro** - Interfaz moderna y elegante
- 🎤 **Entrada de voz** - Si `enable_voice=True`
- 🔧 **Panel de herramientas** - Ve las herramientas disponibles
- ⚙️ **Configuración** - Revisa la configuración actual
- 🌐 **Compartir públicamente** - Configura `GRADIO_SHARE=true` para obtener URL pública

#### Configurar acceso público (opcional)

```yaml
# En config/mi_asistente.yaml
GRADIO_SHARE: true
```

O con variable de entorno:
```bash
export GRADIO_SHARE=true
python main.py
```

### Configurar Filtro de Seguridad

El framework incluye un filtro de seguridad configurable para proteger contra contenido inapropiado:

```yaml
# En config/mi_asistente.yaml
SAFETY_LEVEL: "medium"  # off, low, medium, high
```

**Niveles disponibles:**
- `"off"` - **Filtro deshabilitado** - Permite todo el contenido
- `"low"` - **Muy permisivo** - Solo bloquea contenido extremadamente peligroso
- `"medium"` - **Equilibrado** *(recomendado)* - Bloquea contenido inapropiado, permite conversación normal
- `"high"` - **Estricto** - Filtrado más riguroso para entornos sensibles

**Nota**: El filtro permite automáticamente conversaciones normales como preguntas sobre nombres, edad, fechas, etc.

### Configurar Sistema de Permisos

El framework incluye un sistema de permisos granular para comandos administrativos:

```yaml
# En config/mi_asistente.yaml
ADMIN_MODE: "production"  # dev, production

ADMIN_USERS:
  - user_id: "1069636329"        # Tu ID de usuario
    platform: "telegram"        # telegram, whatsapp, google_chat, api
    permissions: ["super_admin"] # super_admin, broadcast, user_management, system
```

**Modos disponibles:**
- `"dev"` - **Desarrollo** - Todos los usuarios tienen permisos de admin
- `"production"` - **Producción** - Solo usuarios configurados tienen permisos

**Permisos disponibles:**
- `"user_info"` - Ver información propia (`&whoami`)
- `"broadcast"` - Envío masivo (`&sendmsg`, `&list_users`)
- `"user_management"` - Gestión de usuarios (`&delete_session`, `&list_sessions`)
- `"system"` - Comandos de sistema (`&status`, `&monitor`, `&clear_msg`)
- `"super_admin"` - **Todos los comandos** (acceso total)

**Comandos útiles:**
- `&whoami` - Ver tu ID de usuario y permisos actuales
- `&help` - Lista completa de comandos disponibles

### Configurar Variables de Entorno

Edita tu archivo `.env`:

```bash
# OpenAI
GPT_API_KEY=sk-...

# Google Gemini (opcional)
GEMINI_API_KEY=AI...

# Google Vertex AI (opcional)
VERTEX_PROJECT_ID=mi-proyecto-gcp
VERTEX_LOCATION=us-central1

# Redis para persistencia (opcional)
REDIS_PUBLIC_URL=redis://localhost:6379

# Telegram (opcional)
TELEGRAM_TOKEN=...
TELEGRAM_WEBHOOK_URL=https://tu-dominio.com/webhook

# WhatsApp Business (opcional)
WHATSAPP_TOKEN=...
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_WEBHOOK_URL=https://tu-dominio.com/whatsapp-webhook

# API REST - Para plataformas web personalizadas (opcional)
API_WEBHOOK_URL=https://tu-plataforma-web.com/api

# Google Chat (opcional)
GC_PROJECT_ID=...
GC_PRIVATE_KEY=...
GC_CLIENT_EMAIL=...
```

## 🌟 Características

- **🤖 Múltiples Modelos IA**: OpenAI GPT, Google Gemini y Vertex AI
- **📱 Múltiples Canales**: API REST, Telegram, WhatsApp, Google Chat
- **🧠 RAG Integrado**: Lee carpetas locales, GCP, S3, Google Drive automáticamente
- **🔧 Herramientas Extensibles**: Sistema de plugins simple
- **🎤 Procesamiento de Voz**: Transcripción automática de audio
- **🔒 Filtros de Seguridad**: Contenido seguro por defecto (configurable)
- **👥 Sistema de Permisos**: Control granular de acceso a comandos administrativos
- **📨 Mensajería Masiva**: Envío de mensajes a todos los usuarios activos
- **💾 Persistencia de Contexto**: Conversaciones continuas con Redis
- **📊 Diagnósticos**: Monitoreo automático de componentes

## 📚 Documentación Adicional

Para casos de uso avanzados, configuraciones especiales y ejemplos completos, consulta la documentación en el repositorio.

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Por favor:

1. Haz fork del repositorio
2. Crea una rama para tu feature
3. Haz commit de tus cambios
4. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.