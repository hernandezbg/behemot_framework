from setuptools import setup, find_packages

# Dependencias mínimas para arrancar un agente con el conector API REST y
# modelos OpenAI. Todo lo demás (RAG, voz, otros providers, Gradio, etc.) va a
# `extras_require` para no obligar al usuario a instalar ~3 GB de paquetes que
# quizá no necesita.
CORE_REQUIRES = [
    "fastapi",
    "uvicorn",
    "requests",
    "python-dotenv",
    "pydantic>=2",
    "openai",
    "redis",
    "PyYAML",             # config.py carga YAML
    "python-multipart",   # uploads en /api/chat
    "jsonschema",         # validación de argumentos de tools (seguridad)
    "beautifulsoup4",     # sanitización HTML en RAG (seguridad)
]

EXTRAS = {
    # RAG base slim: chunking + ChromaDB + tiktoken. Embeddings y loaders
    # opcionales se instalan vía extras adicionales (ver más abajo).
    # Breaking change vs 0.4.x: ya no incluye sentence-transformers,
    # unstructured, faiss-cpu ni langchain-classic. Para el comportamiento
    # anterior, instalar [rag-full].
    "rag": [
        "langchain-core>=0.1.0",
        "langchain-text-splitters>=0.0.1",
        "langchain-openai>=0.0.5",     # provider OpenAI por defecto
        "langchain-chroma>=0.1.0",
        "chromadb>=0.4.22",
        "tiktoken>=0.5.1",
        "markdown",                     # parseo .md sin unstructured
    ],

    # Loaders opcionales por formato/fuente.
    # Todos arrastran langchain-community porque los loaders concretos
    # (PyPDFLoader, CSVLoader, WebBaseLoader, UnstructuredMarkdownLoader,
    # etc.) viven en ese paquete. langchain-community pesa ~10 MB; lo
    # gordo (torch, transformers) viene solo si se pide [rag-loaders-office]
    # o [rag-embeddings-hf].
    "rag-loaders-pdf": [
        "langchain-community>=0.0.13",
        "pypdf>=3.17.1",
    ],
    "rag-loaders-office": [
        # unstructured arrastra transitivamente transformers, nltk, etc.
        # Solo instalar si se necesitan .docx/.pptx/.eml o el loader
        # UnstructuredMarkdownLoader (no requerido para .md básico).
        "langchain-community>=0.0.13",
        "unstructured>=0.4.16",
    ],
    "rag-loaders-web": [
        # WebBaseLoader, TextLoader, CSVLoader, DirectoryLoader.
        "langchain-community>=0.0.13",
    ],

    # Embeddings opcionales. OpenAI ya viene en [rag].
    "rag-embeddings-hf": [
        # sentence-transformers arrastra torch + nvidia-* (~2.5 GB).
        "sentence-transformers",
        "langchain-community>=0.0.13",  # HuggingFaceEmbeddings vive aquí
    ],

    # Bundle con el comportamiento previo a 0.5.0 — facilita migración.
    "rag-full": [
        "langchain>=0.1.0",
        "langchain-core>=0.1.0",
        "langchain-community>=0.0.13",
        "langchain-text-splitters>=0.0.1",
        "langchain-openai>=0.0.5",
        "langchain-chroma>=0.1.0",
        "chromadb>=0.4.22",
        "tiktoken>=0.5.1",
        "pypdf>=3.17.1",
        "unstructured>=0.4.16",
        "markdown",
        "sentence-transformers",
    ],
    # Voz: el TranscriptionService usa openai.audio.transcriptions, que
    # ya está cubierto por `openai` en CORE_REQUIRES. El extra existe
    # como marcador semántico (deja explícito en el requirements que se
    # quiere activar voice) sin instalar nada adicional.
    #
    # Breaking change vs 0.5.x: ya no instala openai-whisper,
    # faster-whisper, deepgram-sdk, SpeechRecognition, pydub,
    # ffmpeg-python, soundfile — ninguno se usa en el código actual y
    # arrastraban ~3 GB de torch + CUDA.
    #
    # Para Whisper local (no implementado todavía en el framework),
    # instalar [voice-local-whisper]. Para Deepgram, [voice-deepgram].
    "voice": [],
    "voice-local-whisper": [
        # Reservado: integración pendiente. Quien instale esto debe
        # implementar el dispatch en TranscriptionService.
        "openai-whisper",
        "torch",
    ],
    "voice-deepgram": [
        # Reservado: integración pendiente.
        "deepgram-sdk",
    ],
    "voice-elevenlabs": [
        "elevenlabs>=1.0.0",
    ],
    "gemini": [
        "google-generativeai>=0.3.0",
        "langchain-google-genai>=1.0.0",
    ],
    "cloud": [
        "google-cloud-storage>=2.9.0",
        "google-api-python-client",
        "google-auth==2.28.1",
        "boto3",
    ],
    "vertex": [
        # Vertex AI (Gemini en GCP, autenticación con ADC / cuenta de servicio).
        # google-genai es la librería oficial vigente; reemplaza al SDK
        # deprecado `vertexai` dentro de `google-cloud-aiplatform`.
        "google-genai>=0.3.0",
    ],
    "telegram": [
        "python-telegram-bot",
    ],
    "google_chat": [
        # Conector de Google Chat (autenticación con service account de GCP).
        "google-api-python-client>=2.0.0",
        "google-auth>=2.0.0",
    ],
    "whatsapp": [
        "twilio",
    ],
    "gradio": [
        "gradio>=4.0.0",
        "Pillow>=10.0.0",
    ],
    "observability": [
        # Tracing con Langfuse: cada turno del agente genera un trace con
        # input del usuario, output del asistente, tool calls y (para OpenAI)
        # conteo de tokens. Requiere LANGFUSE_SECRET_KEY y LANGFUSE_PUBLIC_KEY.
        "langfuse>=2.0.0",
    ],
    "dev": [
        "pytest",
        "pytest-asyncio",
        "respx",
        "httpx",
        "build",
        "twine",
    ],
}
# Meta-extra "all": instala todo excepto dev.
EXTRAS["all"] = sorted({pkg for name, lst in EXTRAS.items() if name != "dev" for pkg in lst})


with open("README.md", encoding="utf-8") as f:
    LONG_DESCRIPTION = f.read()


setup(
    name="behemot_framework",
    version="0.6.24",
    packages=find_packages(),
    install_requires=CORE_REQUIRES,
    extras_require=EXTRAS,
    author="Bruno Hernandez",
    author_email="hernandezbg@gmail.com",
    description="A modular framework for building multimodal AI assistants.",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url="https://github.com/hernandezbg/behemot_framework",
    project_urls={
        "Source": "https://github.com/hernandezbg/behemot_framework",
        "Issues": "https://github.com/hernandezbg/behemot_framework/issues",
    },
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Framework :: FastAPI",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "behemot-admin=behemot_framework.cli.admin:main",
        ],
    },
    include_package_data=True,
)
