# Changelog

Todas las mejoras y cambios importantes de Behemot Framework se documentan en este archivo.

## [0.5.2] - 2026-05-19

### ⚠️ Breaking change: extra `[voice]` ahora vacío

El extra `[voice]` declaraba 7 paquetes (`openai-whisper`, `faster-whisper`,
`deepgram-sdk`, `SpeechRecognition`, `pydub`, `ffmpeg-python`,
`soundfile`) que **nunca se importan en el código del framework**. El
`TranscriptionService` solo usa `openai.audio.transcriptions`, ya
cubierto por `openai` en `CORE_REQUIRES`. El extra arrastraba ~3 GB
innecesarios (torch + CUDA + nvidia-* vía openai-whisper y
faster-whisper), inflando imágenes Docker de 584 MB a 5.7 GB para
deploys que solo necesitaban la API de Whisper de OpenAI.

**Fix:** `[voice]` se redujo a `[]`. La funcionalidad de voz sigue
funcionando exactamente igual porque depende solo del cliente `openai`
que ya está en core.

### Reservas para integraciones futuras

Se agregaron dos extras stub para cuando se implementen backends
locales/alternativos de transcripción:

- `[voice-local-whisper]`: declara `openai-whisper` + `torch`. No tiene
  dispatch implementado todavía — instalar este extra hoy no cambia el
  comportamiento. Reservado para una futura entrada `VOICE_PROVIDER` en
  la config.
- `[voice-deepgram]`: declara `deepgram-sdk`. Mismo estado.

### Migración

| Tu caso | 0.5.1 | 0.5.2 |
|---------|-------|-------|
| Voz con API de OpenAI (90% de usuarios) | `[voice]` (5.7 GB) | `[voice]` (sin cambios, ~430 MB) |
| Voz con Whisper local | `[voice]` (incluía whisper) | `[voice,voice-local-whisper]` (no implementado) |

Si tu deploy bajó de 5.7 GB a ~500 MB sin que tu app de voz deje de
funcionar, es esperado: nunca necesitaste esas dependencias.

## [0.5.1] - 2026-05-18

### 🐛 Fix crítico: Redis inalcanzable colgaba el arranque

`behemot_framework/context.py` ejecutaba `redis_client.ping()` al
importarse el módulo, **sin timeout**. Si `REDIS_PUBLIC_URL` apuntaba a
un endpoint inalcanzable (firewall, TLS mal configurado, servicio
pausado), el proceso quedaba bloqueado indefinidamente antes de que
Uvicorn pudiera abrir el puerto, lo que se manifestaba en plataformas
como Railway como un *healthcheck failed* sin ningún log de aplicación.

**Fix:** se agregaron `socket_connect_timeout=5` y `socket_timeout=5` al
constructor de `redis.from_url(...)`. Ahora, si Redis no responde, el
ping falla en 5 s con un mensaje claro y la app **continúa sin
persistencia de contexto** en vez de colgarse.

### ✨ Aceptar `REDIS_URL` como fallback

Railway, Render y Heroku inyectan la URL de Redis bajo el nombre
`REDIS_URL` por convención. Behemot ahora la acepta como fallback de
`REDIS_PUBLIC_URL` (que sigue teniendo prioridad si ambas están
definidas). Esto elimina la fricción común de tener que crear una env
var con un nombre distinto al que la plataforma provee.

### 🧹 Saneamiento de la URL de Redis

La URL se pasa por `.strip()` y se quitan comillas envolventes (`"..."` o
`'...'`) si aparecen — protección contra el caso típico de pegar la URL
con comillas en el panel de configuración de la plataforma.

## [0.5.0] - 2026-05-18

### ⚠️ Breaking changes — empaquetado del extra `[rag]`

El extra `[rag]` deja de ser un bundle monolítico de ~3 GB y pasa a ser un
slim core que solo incluye lo necesario para indexar texto y consultar
ChromaDB con embeddings de OpenAI. Los loaders pesados y los backends de
embeddings de HuggingFace pasan a extras opcionales.

**Por qué:** la versión 0.4.x arrastraba `sentence-transformers` (→ torch,
CUDA, transformers) y `unstructured` (→ spacy, nltk) aunque el usuario solo
quisiera Markdown + OpenAI + ChromaDB. En despliegues como Railway/Render,
la imagen Docker pesaba ~3 GB y el `pip install` tardaba >3 minutos.

**Nuevo `[rag]` (slim, ~400-500 MB):**

- `langchain-core`, `langchain-text-splitters`, `langchain-openai`
- `langchain-chroma`, `chromadb`
- `tiktoken`, `markdown`

**Extras nuevos:**

| Extra | Para qué | Pesa |
|-------|----------|------|
| `rag-loaders-pdf` | Cargar PDFs (`pypdf`) | ~5 MB |
| `rag-loaders-office` | `.docx`, `.pptx`, `.eml` y mejor parseo de Markdown vía `unstructured` | ~500 MB (trae transformers) |
| `rag-loaders-web` | `WebBaseLoader`, `TextLoader`, `CSVLoader`, `DirectoryLoader` (langchain-community) | ~10 MB |
| `rag-embeddings-hf` | Embeddings locales con HuggingFace (`sentence-transformers`) | ~2.5 GB (trae torch + CUDA) |
| `rag-full` | Bundle con el comportamiento de 0.4.x | ~3 GB |

### Migración

Caso por caso, el comando equivalente:

| Tu caso | 0.4.x | 0.5.0 |
|---------|-------|-------|
| OpenAI + ChromaDB + Markdown local | `[rag]` | `[rag]` |
| OpenAI + ChromaDB + PDF local | `[rag]` | `[rag,rag-loaders-pdf]` |
| Google Gemini + GCS bucket | `[rag,gemini,cloud]` | `[rag,gemini,cloud,rag-loaders-pdf]` |
| HuggingFace embeddings locales | `[rag]` | `[rag,rag-embeddings-hf]` |
| Compatibilidad total con 0.4.x | `[rag]` | `[rag-full]` |

### Cambios internos

- `behemot_framework/rag/document_loader.py`: todos los loaders concretos
  (PDF, CSV, Web, S3, GCS, Google Drive, UnstructuredMarkdown) ahora se
  importan de forma perezosa. Si llamas un loader cuyo extra no instalaste,
  recibes un `ImportError` con el comando `pip install` exacto.
- `behemot_framework/rag/document_loader.py::load_markdown`: si
  `unstructured` no está instalado, hace fallback a un parser ligero que
  lee el `.md` como texto plano. Suficiente para el 95% de casos de RAG.
- `behemot_framework/rag/embeddings.py`: `HuggingFaceEmbeddings` y los
  embeddings de Google se importan de forma perezosa dentro de su método
  correspondiente.
- `behemot_framework/rag/rag_pipeline.py`: migrado de
  `langchain_community.vectorstores.Chroma` a `langchain_chroma.Chroma`.
- `behemot_framework/rag/retriever.py`: `ContextualCompressionRetriever` y
  `LLMChainExtractor` (`langchain-classic`) se importan de forma perezosa
  solo si llamas `get_compression_retriever`.
- Removidas dependencias no usadas del extra `[rag]`: `faiss-cpu`,
  `langchain-classic`, `langchain` (meta-paquete), `langchain-community`.

### Impacto esperado

- Tamaño de imagen Docker para caso OpenAI+ChromaDB+Markdown: **~3 GB → ~500 MB**.
- Tiempo de `pip install` en CI sin cache: **~3 min → ~30 s**.
- Errores `No module named 'googleapiclient' / 'boto3' / 'google.cloud'`
  durante el arranque cuando no se usan esos backends: eliminados.

## [0.1.2] - 2025-01-03

### ✨ Nuevas Características

#### Sistema de Permisos Granular
- **Sistema de permisos completo** con control granular de acceso a comandos administrativos
- **Modos de administración**: `dev` (todos son admin) y `production` (solo usuarios configurados)
- **Permisos disponibles**:
  - `user_info` - Ver información propia
  - `broadcast` - Envío masivo de mensajes
  - `user_management` - Gestión de usuarios y sesiones
  - `system` - Comandos de sistema y monitoreo
  - `super_admin` - Acceso total a todos los comandos

#### Nuevo Comando &whoami
- **Comando `&whoami`** para que usuarios vean su información y permisos
- **Información detallada** por plataforma (Telegram, WhatsApp, Google Chat, API)
- **Lista de comandos disponibles** basada en permisos reales
- **Metadata específica**: username, teléfono, email, IP según la plataforma

#### Sistema de Mensajería Masiva
- **Comando `&sendmsg`** para envío masivo a todos los usuarios activos
- **Envío por plataforma específica** con parámetro `platform`
- **Comando `&list_users`** para ver usuarios activos por plataforma
- **Tracking automático** de usuarios que interactúan con el bot
- **Metadata enriquecida** para marketing y análisis

#### Filtro de Seguridad Configurable
- **`SAFETY_LEVEL` configurable**: `off`, `low`, `medium`, `high`
- **Filtro mejorado** que permite conversaciones normales (nombres, edad, fechas)
- **Protección contra prompt injection** y contenido inapropiado
- **Fail-safe**: permite contenido en caso de errores del filtro

### 🔧 Mejoras

#### Configuración
- **Nuevas opciones de configuración** para permisos y seguridad
- **CLI actualizado** con configuración de permisos en proyectos nuevos
- **Archivo de ejemplo** `config_with_admin_users.yaml`
- **Documentación mejorada** en README con ejemplos de configuración

#### Sistema de Comandos
- **Verificación de permisos** integrada en comandos administrativos
- **Mensajes de error informativos** para acceso denegado
- **Logging mejorado** con emojis para mejor debugging

### 📚 Documentación
- **Sección de permisos** en README con ejemplos completos
- **Comandos útiles** documentados (`&whoami`, `&help`)
- **Configuración paso a paso** para diferentes modos de administración

### 🐛 Correcciones
- **Filtro de seguridad** ya no bloquea conversaciones normales
- **Contexto mantenido** correctamente en todas las plataformas
- **Mejor manejo de errores** en comandos administrativos

## [0.1.1] - 2025-01-02

### Mejoras anteriores
- Sistema RAG con múltiples proveedores de embeddings
- Soporte para modelos Gemini y OpenAI
- Conectores para múltiples plataformas
- Interfaz de prueba local con Gradio

## [0.1.0] - 2025-01-01

### Lanzamiento inicial
- Framework base para asistentes IA multimodales
- Soporte para herramientas extensibles
- Sistema de configuración YAML
- CLI para generación de proyectos