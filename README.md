# Guía Rápida para Crear un Nuevo Asistente con Behemot Framework

La filosofía es simple: **el framework proporciona el motor; tú proporcionas la personalidad (configuración) y las habilidades (herramientas).**

---

### Paso 1: Crear el Directorio del Proyecto y el Entorno Virtual

Primero, crea una nueva carpeta para tu asistente al mismo nivel que `my_assistant_project` y `behemot_framework_package`.

```bash
mkdir mi_nuevo_asistente
cd mi_nuevo_asistente
```

Es **muy recomendable** crear un entorno virtual para aislar las dependencias:

```bash
# En Windows
python -m venv .venv
.\.venv\Scripts\activate

# En macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### Paso 2: Instalar el Framework Behemot

Desde el directorio de tu nuevo asistente (`mi_nuevo_asistente`), instala el framework en modo "editable". Esto significa que cualquier cambio que hagas en el código del framework se reflejará inmediatamente en tu nuevo proyecto.

```bash
# Asegúrate de estar en la carpeta mi_nuevo_asistente
pip install -e ../behemot_framework_package
```

### Paso 3: Crear el Archivo de Configuración (`.yaml`)

Aquí es donde le das a tu asistente su "personalidad" y defines qué modelo y herramientas usará.

1.  Crea una carpeta `config`.
2.  Dentro de `config`, crea un archivo YAML, por ejemplo, `mi_asistente.yaml`.

**`config/mi_asistente.yaml` (Ejemplo con GPT):**
```yaml
VERSION: "1.0.0"
ASSISTANT_NAME: "AsistenteDelClima"
ASSISTANT_DESCRIPTION: "Un asistente experto en dar el pronóstico del tiempo."

# Configuración del modelo
MODEL_PROVIDER: "openai"  # Opciones: openai, gemini
MODEL_NAME: "gpt-4o-mini"
MODEL_TEMPERATURE: 0.5
MODEL_MAX_TOKENS: 150

# Prompt del sistema: ¡La parte más importante!
PROMPT_SISTEMA: |
  Eres un meteorólogo experto y amigable.
  Tu única función es dar el pronóstico del tiempo usando la herramienta 'consultar_clima'.
  Nunca respondas preguntas que no estén relacionadas con el clima.
  Sé siempre conciso y ve al grano.

# Habilitar RAG (si lo necesitas)
ENABLE_RAG: false

# Habilitar voz
ENABLE_VOICE: true
```

**`config/mi_asistente_gemini.yaml` (Ejemplo con Gemini):**
```yaml
VERSION: "1.0.0"
ASSISTANT_NAME: "AsistenteGemini"
ASSISTANT_DESCRIPTION: "Un asistente potenciado por Gemini AI."

# Configuración del modelo
MODEL_PROVIDER: "gemini"  # Usar Gemini en lugar de OpenAI
MODEL_NAME: "gemini-1.5-pro"  # o gemini-1.5-flash para respuestas más rápidas
MODEL_TEMPERATURE: 0.7
MODEL_MAX_TOKENS: 2048

# Prompt del sistema
PROMPT_SISTEMA: |
  Eres un asistente AI útil y amigable potenciado por Gemini.
  Puedes ayudar con diversas tareas y usar herramientas cuando sea necesario.

# Habilitar características
ENABLE_RAG: true
ENABLE_VOICE: true

# Configuración RAG con Gemini Embeddings
RAG_EMBEDDING_PROVIDER: "google"  # openai, google, huggingface
RAG_EMBEDDING_MODEL: "models/embedding-001"
```

### Paso 4: Desarrollar las Herramientas Personalizadas

Estas son las "habilidades" de tu asistente.

1.  Crea una carpeta `tools`.
2.  Dentro de `tools`, crea un archivo Python para cada herramienta. No olvides el archivo `__init__.py` en la carpeta `tools`.

**`tools/consultar_clima.py` (Ejemplo):**
```python
from behemot_framework.tooling import tool, Param

@tool(
    name="consultar_clima",
    description="Consulta el clima actual para una ciudad específica.",
    params=[
        Param(name="ciudad", type_="string", description="El nombre de la ciudad.", required=True)
    ]
)
def consultar_clima(args):
    ciudad = args.get("ciudad")
    if not ciudad:
        return "Por favor, especifica una ciudad."
    
    # Aquí iría la lógica real para consultar una API del clima
    # Por ahora, devolvemos un resultado simulado.
    return f"El clima en {ciudad} es soleado con 25°C."

```

### Paso 5: Crear el Punto de Entrada (`main.py`)

Este archivo une todo: carga la configuración, activa los canales y le dice al framework qué herramientas usar.

Crea un archivo `main.py` en la raíz de `mi_nuevo_asistente`.

**`main.py`:**
```python
import logging
import uvicorn
from behemot_framework.factory import create_behemot_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear la aplicación Behemot para el nuevo asistente
app = create_behemot_app(
    # Activa los canales que necesites
    enable_api=True,
    enable_telegram=True,
    
    # Especifica la ruta a TU archivo de configuración
    config_path="config/mi_asistente.yaml",
    
    # Especifica la lista de herramientas que quieres cargar
    use_tools=["consultar_clima"]
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
```

### Paso 6: Gestionar Dependencias y Variables de Entorno

1.  **`requirements.txt`**: Crea este archivo para que otros puedan instalar las dependencias de tu proyecto fácilmente.

    ```
    # requirements.txt
    -e ../behemot_framework_package
    # Aquí puedes añadir otras dependencias que tus herramientas necesiten, ej: requests
    ```

2.  **`.env`**: Crea este archivo en la raíz de `mi_nuevo_asistente` para guardar tus secretos.

    ```
    # .env
    # API Keys según el proveedor que uses
    GPT_API_KEY="tu_api_key_de_openai"      # Para OpenAI
    GEMINI_API_KEY="tu_api_key_de_google"   # Para Gemini
    
    # Tokens de plataformas
    TELEGRAM_TOKEN="tu_token_de_telegram"
    WEBHOOK_URL="tu_url_de_ngrok_o_servidor"
    REDIS_PUBLIC_URL="tu_url_de_conexion_a_redis"
    # ...y cualquier otra clave que necesites
    ```

### Paso 7: ¡Ejecutar tu Nuevo Asistente!

Con todos los archivos en su lugar y el entorno virtual activado, simplemente ejecuta Uvicorn:

```bash
uvicorn main:app --reload
```

¡Y eso es todo! Ahora tendrás un nuevo asistente funcionando, completamente separado del proyecto `CursoriaAI`, pero utilizando el mismo motor del framework Behemot.