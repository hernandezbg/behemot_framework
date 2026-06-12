# Changelog

Todas las mejoras y cambios importantes de Behemot Framework se documentan en este archivo.

## [0.6.12] - 2026-06-12

### Bug fix

**Handoff: trigger funciona con mensajes de voz**

El trigger de handoff solo evaluaba mensajes de texto. Si el usuario enviaba
un audio diciendo "quiero hablar con un asesor", la derivación no se
disparaba.

Fix: en el trigger check, si el mensaje es de voz y hay transcriptor
disponible, se transcribe el audio primero y se evalúa el texto resultante
contra los triggers. La transcripción se reutiliza en el flujo normal del bot
(variable `_pre_transcribed`) para evitar doble transcripción si el audio
no era un trigger.

## [0.6.11] - 2026-06-12

### Feature

**Handoff: campo `user_avatar` en payload de start_handoff**

`start_handoff()` acepta nuevo parámetro opcional `user_avatar: str = None`.
Se incluye siempre en el payload enviado a behemot.net (null si no se provee).
Retrocompatible: los calls existentes no necesitan cambios. Si behemot.net
recibe null, muestra iniciales como fallback.

Obtener la foto de perfil real de WhatsApp requiere una llamada adicional a
la Cloud API que es poco confiable — se deja como extensión futura por canal.

## [0.6.10] - 2026-06-10

### Fix

**Handoff: user_name incluye nombre del perfil WhatsApp**

`start_handoff` recibía `_uid` (solo el número) como `user_name`.
Ahora extrae `contacts[0].profile.name` del payload de WhatsApp y
construye `"Juan Pérez (5491134567890)"`. Si el perfil no tiene nombre,
mantiene el número como fallback. `user_id` interno no cambia.

## [0.6.9] - 2026-06-09

### Features

**Handoff: soporte imagen bidireccional**

Mismo patrón que audio (v0.6.8), extendido a imágenes:

- **Entrante** (usuario → asesor): imagen durante handoff obtiene la URL
  autenticada vía `obtener_url_media()` y reenvía con `type="image"` y
  el caption como `content`. Limpia el archivo local ya descargado.
- **Saliente** (asesor → usuario): evento `agent.message` con `type="image"`
  usa `enviar_imagen_por_url(to, url, caption)` para entregar la imagen
  con su caption vía Cloud API.
- Nuevo método `enviar_imagen_por_url()` en `WhatsAppConnector`.

## [0.6.8] - 2026-06-09

### Features

**Handoff: soporte de audio bidireccional**

**Dirección 1 — WhatsApp → asesor (audio entrante):**

Cuando un usuario en handoff envía un mensaje de voz, el framework ya no
transcribe ni procesa el audio con el bot. En cambio:
- Obtiene la URL autenticada del audio desde la API de WhatsApp
  (`obtener_url_media(media_id)`) sin descargar el archivo.
- Llama a `forward_message` con `type="audio"` y `media_url`.
- Reenvía al endpoint `{session_id}/message/` de behemot.net:
  `{"content": "[mensaje de voz]", "type": "audio", "media_url": "https://..."}`

**Dirección 2 — asesor → WhatsApp (audio saliente):**

Cuando behemot.net envía `{"event": "agent.message", "type": "audio", "media_url": "https://storage.googleapis.com/..."}`,
el framework llama a `enviar_audio_por_url(to, media_url)` que usa el campo
`"audio": {"link": url}` de la Cloud API para entregar el audio directamente
al usuario de WhatsApp sin subida previa.

**Retrocompatibilidad:** `forward_message` sin `msg_type` sigue enviando texto
plano. Eventos `agent.message` sin campo `type` se tratan como texto.

## [0.6.7] - 2026-06-09

### Bug fix

**Handoff webhook: NameError `json` no definido**

`factory.py` no tenía `import json` a nivel de módulo. El handler
`setup_handoff_webhook` llamaba `json.loads(body)` pero `json` solo estaba
importado localmente como `_json` dentro del handler de WhatsApp (línea 604).
Fix: se agrega `import json` a los imports globales del módulo.

## [0.6.6] - 2026-06-09

### Debug

**Handoff webhook: error 400 incluye len(body) y excepción exacta**

El mensaje de error 400 ahora es:
`"Body no es JSON válido (len=0, err=JSONDecodeError(...))"`.
Esto aparece directamente en el log del Celery task de behemot.net sin
necesitar acceso a los logs del servidor. Si `len=0`, el body llega vacío
(problema de proxy/transporte); si `len>0`, el error de parseo es visible.

## [0.6.5] - 2026-06-09

### Debug / diagnóstico

**Handoff webhook: log del body entrante para diagnóstico**

Agrega `logger.info` antes de `json.loads` en `/handoff/webhook` que registra
`len`, `Content-Type` y los primeros 300 bytes del body. Si el Celery worker de
behemot.net envía el payload con `data=dict` (form-encoded) en lugar de
`json=dict`, el log lo evidencia y el `logger.error` en el except muestra el
error exacto de parseo.

El bug esperado: behemot.net usa `requests.post(url, data=payload)` → body
llega como `event=agent.message&session_id=...` (form-encoded, no JSON) → 400.
Fix en behemot.net: cambiar `data=` por `json=`.

## [0.6.4] - 2026-06-09

### Bug fixes

**Handoff: user_name vacío y framework_webhook_url inválida**

Dos errores en el mismo call a `start_handoff` en factory.py:

- `user_name=""` causaba validación 400 en behemot.net. Fix: se usa `_uid`
  (número de teléfono / chat_id) como fallback cuando no hay nombre disponible.
- `HANDOFF_CALLBACK_URL` vacío generaba `framework_webhook_url="/handoff/webhook"`
  (URL relativa inválida). Fix: si `HANDOFF_CALLBACK_URL` no está configurado se
  loguea un error claro y se omite el call a behemot.net; el mensaje de handoff
  se envía igual al usuario para no dejarlo sin respuesta.

Ambos fixes aplicados en los handlers de WhatsApp y Telegram.

## [0.6.3] - 2026-06-09

### Bug fix

**Handoff: 405 Method Not Allowed al llamar a behemot.net**

- Django tiene `APPEND_SLASH = True` por defecto: redirige `/start` → `/start/`
  con un 301. `requests` sigue el redirect convirtiendo el POST en GET, lo que
  resulta en `405 Método GET no permitido`.
- Fix: trailing slash agregado a los tres endpoints del cliente:
  `start/`, `{id}/message/`, `{id}/end/`.

## [0.6.2] - 2026-06-09

### Bug fix

**NameError: asyncio no importado en factory.py (handoff WhatsApp)**

- El bloque de handoff en el handler de WhatsApp usaba `asyncio.to_thread()`
  pero `asyncio` no estaba en los imports del módulo `factory.py`.
- Fix: `import asyncio` agregado al inicio de `factory.py`.

## [0.6.1] - 2026-06-09

### Nuevas funcionalidades

**Human Handoff — integración con behemot.net**

Cuando un usuario solicita hablar con un asesor humano, el framework pausa el
bot para ese usuario y deriva la conversación a la bandeja de behemot.net.

**Activación mínima:**
```yaml
HANDOFF_API_KEY:      "bh-live-xxxx"
HANDOFF_WEBHOOK_URL:  "https://behemot.net/api/v1/handoff/"
HANDOFF_CALLBACK_URL: "https://mi-agente.railway.app"
HANDOFF_TRIGGERS:
  - "quiero hablar con una persona"
  - "asesor"
  - "hablar con humano"
```

**Flujo:**
1. Usuario escribe una frase del listado `HANDOFF_TRIGGERS`
2. Framework llama `POST /handoff/start` en behemot.net con el historial
3. Bot se pausa para ese usuario (flag en Redis con TTL de 24h)
4. Mensajes nuevos del usuario se reenvían al asesor vía `POST /handoff/{id}/message`
5. Asesor responde desde la bandeja → behemot.net llama `POST /handoff/webhook` del framework
6. Framework reenvía la respuesta al usuario por WhatsApp/Telegram
7. Cuando el asesor cierra, bot se retoma automáticamente

**Mensajes configurables:**
- `HANDOFF_START_MESSAGE`: al iniciar el handoff
- `HANDOFF_ASSIGNED_MESSAGE`: cuando el asesor toma la conversación
- `HANDOFF_CLOSED_MESSAGE`: cuando el asesor cierra

**Archivos nuevos/modificados:**
- `services/handoff_service.py` — cliente HTTP a behemot.net + estado en Redis
- `factory.py` — handoff check en handlers de WhatsApp y Telegram +
  endpoint `POST /handoff/webhook` para recibir eventos de behemot.net
- `config.py` — nuevas claves `HANDOFF_*`

Sin las claves configuradas el comportamiento es idéntico al anterior.

## [0.6.0] - 2026-06-08

### Nuevas funcionalidades

**Observabilidad con Langfuse (opcional)**

Cada turno del agente ahora puede generar un trace en Langfuse con:
- Input del usuario y output final del asistente
- Span por cada tool call (nombre, argumentos, resultado)
- Generation LLM con conteo de tokens de prompt y completion (providers OpenAI)
- Latencia total y por paso

**Activación:**

```yaml
# config.yaml
LANGFUSE_SECRET_KEY: "sk-lf-..."
LANGFUSE_PUBLIC_KEY:  "pk-lf-..."
LANGFUSE_HOST: "https://cloud.langfuse.com"   # opcional, es el default
```

```bash
pip install behemot-framework[observability]
```

Si las claves no están configuradas, el framework funciona exactamente igual que antes — toda la lógica de observabilidad es un no-op.

**Archivos nuevos/modificados:**
- `services/observability.py` — singleton Langfuse con API `start_trace`, `end_trace`,
  `record_generation`, `record_tool_span`. Usa `contextvars` para propagar el trace
  activo entre `generar_respuesta` → `call_tool` de forma async-safe.
- `assistants/assistant.py` — `generar_respuesta` ahora es un thin wrapper que
  inicia/cierra el trace; la lógica existente se movió a `_run_turn`.
- `tooling.py` — `call_tool` llama `record_tool_span` tras ejecutar el handler.
- `factory.py` — llama `init_observability` al arrancar si las claves están presentes.
- `config.py` — nuevas claves `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST`.

## [0.5.9] - 2026-06-07

### Bug fixes

**&sendmsg: await sobre función síncrona en WhatsApp**

- `_send_to_platform` en `admin_commands.py` hacía `await enviar_mensaje(...)` pero
  `WhatsAppConnector.enviar_mensaje` es síncrona y devuelve `bool`. El await lanzaba
  `object bool can't be used in 'await' expression`, haciendo que todos los envíos se
  contaran como fallidos aunque WhatsApp devolviera HTTP 200.
- Fix: se elimina el `await` y se retorna directamente el `bool` del conector.

**&sendmsg: prefijo hardcodeado ahora es configurable**

- El texto `"📢 **Mensaje del administrador:**"` estaba hardcodeado en `execute_sendmsg`.
- Nuevo parámetro `prefix: str = ""` en `execute_sendmsg`. Si está vacío el mensaje
  se envía sin prefijo; si tiene valor se antepone con dos saltos de línea.
- Nueva clave de configuración `SENDMSG_PREFIX` (env var o YAML). Default: vacío.
  Ejemplo: `SENDMSG_PREFIX: "📢 Aviso de Ricci Propiedades:"`.

## [0.5.8] - 2026-06-06

### Documentación

**Corrección: firma correcta del handler en el decorador `@tool`**

- El README mostraba `async def mi_herramienta(parametro: str)` con parámetros
  individuales, pero `call_tool` siempre llama `handler(args)` pasando el dict
  completo como único argumento posicional.
- El ejemplo en README.md ahora usa `async def mi_herramienta(args: dict)` con
  acceso explícito `args["parametro"]`, consistente con cómo lo implementan las
  tools internas del framework (ej: `date_tools.py`).
- El docstring del decorador `@tool` en `tooling.py` documenta explícitamente
  la convención y muestra un ejemplo correcto.

## [0.5.7] - 2026-06-06

### Bug fix

**factory.py: mensajes de ubicación de WhatsApp no generaban respuesta**

- El conector `whatsapp_connector.py` (v0.5.6) ya extraía correctamente `type=location`,
  pero `factory.py` no tenía el caso `location` en su bloque de dispatch de tipos.
  El mensaje caía en el `else` de la línea 657 y retornaba `{"status": "ok"}` sin
  generar respuesta al usuario.
- Fix: se agrega `elif mensaje["type"] == "location"` que usa `mensaje["content"]`
  (ya construido por el conector) como texto para el asistente, manteniendo acceso
  a `latitude`, `longitude`, `name` y `address` en el contexto del log.

**Documentación: `use_tools` acepta nombres de módulos, no de funciones**

- El parámetro `use_tools` de `create_behemot_app()` espera el nombre del archivo
  `.py` dentro de `tools/` (ej: `"propiedades_cercanas"`), no el nombre de la
  función decorada con `@tool`. Clarificado en el docstring.

## [0.5.6] - 2026-06-06

### Nuevas funcionalidades

**Soporte de mensajes de ubicación en WhatsApp**

- `extraer_mensaje()` ahora maneja `"type": "location"`.
- El agente recibe las coordenadas en `content` como texto natural
  ("El usuario compartió su ubicación: latitud X, longitud Y") compatible
  con el flujo existente, más los campos estructurados `latitude`, `longitude`,
  `name` y `address` para tools que los necesiten directamente.

## [0.5.5] - 2026-06-05

### Nuevas funcionalidades

**ElevenLabs como provider TTS alternativo**

- `TTSService` ahora soporta `TTS_PROVIDER: "openai"` (default) o `"elevenlabs"`.
- Nuevas variables de config: `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` (default `Rachel`),
  `ELEVENLABS_MODEL` (default `eleven_multilingual_v2`).
- Nuevo extra de instalación: `pip install behemot-framework[voice-elevenlabs]`.
- Si `elevenlabs` no está instalado y se configura ese provider, el error es claro en logs.

## [0.5.4] - 2026-06-05

### Bug fix crítico: TTS bloqueaba el event loop en modo adaptive/audio

Las llamadas síncronas a la API de OpenAI TTS (`synthesize`) y a la API de
WhatsApp/Telegram se ejecutaban directamente dentro de handlers `async` de
FastAPI, congelando el event loop sin lanzar excepción. El agente recibía
el mensaje, generaba la respuesta pero nunca la enviaba.

Fix: `_enviar_respuesta_audio` en ambos conectores ahora ejecuta todas las
llamadas bloqueantes con `asyncio.to_thread()`.

## [0.5.3] - 2026-06-05

### Nuevas funcionalidades

**TTS (Text-to-Speech) en WhatsApp y Telegram**

- Nuevo `TTSService` (`services/tts_service.py`) usando `openai.audio.speech.create`.
  Se instancia automáticamente junto con el `TranscriptionService` cuando `ENABLE_VOICE=True`.
- `procesar_respuesta()` en ambos conectores acepta cuatro modos de respuesta
  configurables vía YAML:
  - `text` — solo texto (comportamiento anterior, default)
  - `audio` — solo audio TTS
  - `both` — texto + audio en el mismo turno
  - `adaptive` — audio si el usuario envió audio, texto si escribió
- WhatsApp: sube el MP3 generado a la Media API de Meta y lo envía como `audio`.
- Telegram: usa `sendVoice` directamente (sin upload previo).
- Variables de config nuevas: `WHATSAPP_RESPONSE_MODE`, `TELEGRAM_RESPONSE_MODE`,
  `TTS_MODEL` (default `tts-1`), `TTS_VOICE` (default `alloy`).

**Bug fix: nombres de colección ChromaDB con paths relativos**

- `./docs` en `RAG_FOLDERS` generaba `._docs`, rechazado por ChromaDB.
- Nueva función `_sanitize_collection_name()` en `startup.py` que normaliza
  cualquier path (`./`, `../`, separadores, caracteres inválidos, longitud mínima).

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