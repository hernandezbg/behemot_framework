#!/usr/bin/env python3
"""
CLI de administración para Behemot Framework
Permite crear la estructura inicial de un proyecto de asistente
"""

import os
import sys
import argparse
from pathlib import Path


def create_yaml_config(assistant_name: str) -> str:
    """Genera el contenido del archivo YAML de configuración"""
    return f"""# Configuración para {assistant_name}
# Generado por behemot-admin

# Configuración del modelo
MODEL_PROVIDER: "openai"  # openai, gemini, vertex
MODEL_NAME: "gpt-4o-mini"  # gpt-4o-mini, gpt-4o, gemini-1.5-pro, gemini-1.5-flash
MODEL_TEMPERATURE: 0.7     # Creatividad del modelo (0.0 - 2.0)
MODEL_MAX_TOKENS: 150      # Máximo tokens en respuestas

# Prompt del sistema
PROMPT_SISTEMA: |
  Eres un asistente inteligente llamado {assistant_name}.
  Tu objetivo es ayudar a los usuarios de manera amable, precisa y eficiente.
  
  Características principales:
  - Eres conversacional y amigable
  - Proporcionas respuestas claras y concisas
  - Si no sabes algo, lo admites honestamente
  
  Recuerda siempre ser respetuoso y profesional.

# Configuración de seguridad
SAFETY_LEVEL: "medium"  # off, low, medium, high

# Sistema de permisos
ADMIN_MODE: "dev"  # dev, production
# En modo "dev": todos los usuarios tienen permisos de admin
# En modo "production": solo usuarios configurados tienen permisos

# Usuarios administradores (para modo production)
ADMIN_USERS: []
# Ejemplo de configuración:
# ADMIN_USERS:
#   - user_id: "tu_id_de_usuario"
#     platform: "telegram"  # telegram, whatsapp, google_chat, api
#     permissions: ["super_admin"]  # super_admin, broadcast, user_management, system

# Configuración de Redis (opcional)
REDIS_PUBLIC_URL: ""  # Ejemplo: redis://localhost:6379

# RAG (Retrieval Augmented Generation) - Opcional
ENABLE_RAG: false
RAG_FOLDERS: []
RAG_EMBEDDING_PROVIDER: "openai"
RAG_EMBEDDING_MODEL: "text-embedding-3-small"

# Configuración de logs
LOG_LEVEL: "INFO"

# Versión del asistente
VERSION: "1.0.0"
"""


def create_main_py(assistant_name: str) -> str:
    """Genera el contenido del archivo main.py"""
    return f'''"""
Punto de entrada principal para {assistant_name}
Generado por behemot-admin
"""

from behemot_framework.factory import create_behemot_app
from dotenv import load_dotenv
import os
import logging

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Crear la aplicación
app = create_behemot_app(
    enable_api=True,  # Habilitar API REST
    enable_telegram=False,  # Habilitar bot de Telegram
    enable_whatsapp=False,  # Habilitar WhatsApp
    enable_google_chat=False,  # Habilitar Google Chat
    enable_voice=False,  # Habilitar procesamiento de voz
    use_tools=[],  # Lista de herramientas a cargar
    config_path="config/{assistant_name}.yaml",
)

if __name__ == "__main__":
    import uvicorn
    # Ejecutar con recarga automática en desarrollo
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )
'''


def create_env_example() -> str:
    """Genera el contenido del archivo .env.example"""
    return """# Variables de entorno para Behemot Framework
# Copia este archivo a .env y configura tus valores

# OpenAI
GPT_API_KEY=sk-...

# Google Gemini (opcional)
GEMINI_API_KEY=AI...

# Google Vertex AI (opcional)
VERTEX_PROJECT_ID=mi-proyecto-gcp
VERTEX_LOCATION=us-central1

# Redis (opcional)
REDIS_PUBLIC_URL=redis://localhost:6379

# Telegram (opcional)
TELEGRAM_TOKEN=
TELEGRAM_WEBHOOK_URL=https://tu-dominio.com/webhook

# WhatsApp (opcional)
WHATSAPP_TOKEN=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_WEBHOOK_URL=https://tu-dominio.com/whatsapp-webhook

# API REST - Para plataformas web personalizadas (opcional)
API_WEBHOOK_URL=https://tu-plataforma-web.com/api

# Google Chat (opcional)
GC_PROJECT_ID=
GC_PRIVATE_KEY_ID=
GC_PRIVATE_KEY=
GC_CLIENT_EMAIL=
GC_CLIENT_ID=
GC_AUTH_URI=
GC_TOKEN_URI=
GC_AUTH_PROVIDER_CERT_URL=
GC_CLIENT_CERT_URL=

# Puerto de la aplicación
PORT=8000
"""


def create_requirements_txt() -> str:
    """Genera el contenido del archivo requirements.txt"""
    return """behemot_framework
python-dotenv
uvicorn[standard]
"""


def create_readme(assistant_name: str) -> str:
    """Genera el contenido del archivo README.md"""
    return f"""# {assistant_name}

Asistente IA creado con Behemot Framework.

## 🚀 Inicio Rápido

### 1. Configurar entorno

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\\Scripts\\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env con tus API keys
```

### 3. Ejecutar el asistente

```bash
python main.py
```

El asistente estará disponible en http://localhost:8000

## 📁 Estructura del Proyecto

```
{assistant_name}/
├── config/
│   └── {assistant_name}.yaml    # Configuración del asistente
├── tools/
│   └── __init__.py              # Directorio para herramientas personalizadas
├── .env.example                 # Ejemplo de variables de entorno
├── main.py                      # Punto de entrada
├── requirements.txt             # Dependencias
└── README.md                    # Este archivo
```

## 🛠️ Personalización

### Modificar el prompt
Edita `config/{assistant_name}.yaml` y modifica `PROMPT_SISTEMA`.

### Agregar herramientas
1. Crea un archivo en `tools/mi_herramienta.py`
2. Define tu herramienta usando el decorador `@tool`
3. Agrégala a `use_tools` en `main.py`

### Habilitar canales
En `main.py`, cambia los parámetros:
- `enable_telegram=True` para Telegram
- `enable_whatsapp=True` para WhatsApp
- `enable_google_chat=True` para Google Chat

## 📚 Documentación

Para más información, visita la [documentación de Behemot Framework](https://github.com/hernandezbg/behemot_framework).
"""


def create_gitignore() -> str:
    """Genera el contenido del archivo .gitignore"""
    return """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
.venv

# Environment variables
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Logs
*.log
logs/

# RAG data
rag_data/
*.db
*.pkl

# Temp files
temp/
tmp/
*.tmp
"""


def create_agent(args):
    """Comando para crear un nuevo proyecto de asistente IA"""
    assistant_name = args.name
    current_dir = Path.cwd()
    
    print(f"🤖 Creando proyecto '{assistant_name}' en el directorio actual...")
    
    # Verificar que el directorio actual esté relativamente vacío
    existing_files = list(current_dir.iterdir())
    # Ignorar venv, .git, __pycache__
    important_files = [f for f in existing_files 
                      if f.name not in ['venv', '.venv', 'env', '.git', '__pycache__', '.gitignore']]
    
    if important_files:
        print(f"⚠️  Advertencia: El directorio actual contiene archivos:")
        for f in important_files[:5]:  # Mostrar máximo 5 archivos
            print(f"   - {f.name}")
        if len(important_files) > 5:
            print(f"   ... y {len(important_files) - 5} más")
        
        response = input("\n¿Continuar de todos modos? (s/N): ")
        if response.lower() != 's':
            print("❌ Operación cancelada.")
            sys.exit(0)
    
    try:
        # Crear estructura de directorios
        (current_dir / "config").mkdir(exist_ok=True)
        (current_dir / "tools").mkdir(exist_ok=True)
        
        # Crear archivos
        files_to_create = {
            f"config/{assistant_name}.yaml": create_yaml_config(assistant_name),
            "tools/__init__.py": "# Directorio para herramientas personalizadas\n",
            "main.py": create_main_py(assistant_name),
            ".env.example": create_env_example(),
            "requirements.txt": create_requirements_txt(),
            "README.md": create_readme(assistant_name),
            ".gitignore": create_gitignore(),
        }
        
        created_files = []
        for filename, content in files_to_create.items():
            filepath = current_dir / filename
            
            # Verificar si el archivo ya existe
            if filepath.exists():
                response = input(f"⚠️  El archivo '{filename}' ya existe. ¿Sobrescribir? (s/N): ")
                if response.lower() != 's':
                    print(f"  ⏭️  Saltando: {filename}")
                    continue
            
            filepath.write_text(content, encoding='utf-8')
            created_files.append(filename)
            print(f"  ✓ Creado: {filename}")
        
        if created_files:
            print(f"\n✅ Proyecto '{assistant_name}' creado exitosamente!")
            print(f"\n📝 Próximos pasos:")
            print(f"  1. cp .env.example .env")
            print(f"  2. # Editar .env con tus API keys")
            print(f"  3. python main.py")
            print(f"\n🚀 ¡Tu asistente estará corriendo en http://localhost:8000!")
        else:
            print("\n⚠️  No se creó ningún archivo.")
        
    except Exception as e:
        print(f"❌ Error creando el proyecto: {e}")
        sys.exit(1)


def main():
    """Punto de entrada principal del CLI"""
    parser = argparse.ArgumentParser(
        description="Behemot Framework - Herramienta de administración"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando create-agent
    create_agent_parser = subparsers.add_parser(
        'create-agent',
        help='Crear un nuevo proyecto de asistente IA'
    )
    create_agent_parser.add_argument(
        'name',
        help='Nombre del asistente a crear'
    )
    
    args = parser.parse_args()
    
    if args.command == 'create-agent':
        create_agent(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()