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
    "rag": [
        "langchain>=0.1.0",
        "langchain-core>=0.1.0",
        "langchain-community>=0.0.13",
        "langchain-text-splitters>=0.0.1",
        "langchain-openai>=0.0.5",
        "langchain-classic>=1.0.0",
        "langchain-chroma>=0.1.0",
        "chromadb>=0.4.22",
        "tiktoken>=0.5.1",
        "pypdf>=3.17.1",
        "unstructured>=0.4.16",
        "markdown",
        "sentence-transformers",
        "faiss-cpu>=1.7.4",
    ],
    "voice": [
        "openai-whisper",
        "faster-whisper",
        "pydub",
        "ffmpeg-python",
        "SpeechRecognition",
        "soundfile",
        "deepgram-sdk",
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
        # Trae también `vertexai` y `google-cloud-aiplatform`.
        "google-cloud-aiplatform>=1.40.0",
        "Pillow",  # vertex_model.py importa PIL para imágenes
    ],
    "telegram": [
        "python-telegram-bot",
    ],
    "whatsapp": [
        "twilio",
    ],
    "gradio": [
        "gradio>=4.0.0",
        "Pillow>=10.0.0",
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
    version="0.3.6",
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
