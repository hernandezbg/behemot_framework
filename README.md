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
behemot-admin startia mi_asistente
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
MODEL_PROVIDER: "openai"  # openai, gemini
MODEL_NAME: "gpt-4o-mini"

# Prompt del sistema - Define la personalidad de tu asistente
PROMPT_SISTEMA: |
  Eres un asistente especializado en [tu dominio].
  Siempre eres amable, preciso y útil.
  
# Configuración de seguridad
SAFETY_LEVEL: "medium"  # low, medium, high

# RAG (Retrieval Augmented Generation)
ENABLE_RAG: false
RAG_FOLDERS: []  # Carpetas con documentos para RAG
RAG_EMBEDDING_PROVIDER: "openai"
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

### Habilitar Canales de Comunicación

En `main.py`, activa los canales que necesites:

```python
app = create_behemot_app(
    enable_api=True,          # API REST
    enable_telegram=True,     # Bot de Telegram
    enable_whatsapp=True,     # WhatsApp Business
    enable_google_chat=True,  # Google Chat
    enable_voice=True,        # Procesamiento de voz
    config_path="config/mi_asistente.yaml",
)
```

### Configurar Variables de Entorno

Edita tu archivo `.env`:

```bash
# OpenAI
GPT_API_KEY=sk-...

# Google Gemini (opcional)
GEMINI_API_KEY=AI...

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

- **🤖 Múltiples Modelos IA**: OpenAI GPT y Google Gemini
- **📱 Múltiples Canales**: API REST, Telegram, WhatsApp, Google Chat
- **🧠 RAG Integrado**: Conocimiento personalizado desde documentos
- **🔧 Herramientas Extensibles**: Sistema de plugins simple
- **🎤 Procesamiento de Voz**: Transcripción automática de audio
- **🔒 Filtros de Seguridad**: Contenido seguro por defecto
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