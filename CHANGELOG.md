# Changelog

Todas las mejoras y cambios importantes de Behemot Framework se documentan en este archivo.

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