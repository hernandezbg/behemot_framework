# Publicar Behemot Framework en PyPI

Guía paso a paso para publicar (y mantener) el paquete en https://pypi.org/.

---

## Una sola vez — preparación de cuentas

### 1. Crear cuenta en PyPI

1. Registrarse en https://pypi.org/account/register/ con `hernandezbg@gmail.com`.
2. Activar 2FA (obligatorio): https://pypi.org/manage/account/ → "Two factor authentication" → app autenticadora (Authy, Google Authenticator).
3. (Opcional pero útil) Hacer lo mismo en TestPyPI: https://test.pypi.org/account/register/. Es independiente de PyPI; sirve para ensayar releases sin "quemar" el nombre.

### 2. Generar API tokens

PyPI ya no permite usuario/password para `twine upload`. Necesitas un token.

- https://pypi.org/manage/account/token/ → "Add API token".
- Nombre: `behemot-framework-release`.
- Scope: la primera vez tiene que ser **"Entire account"** porque el proyecto aún no existe en PyPI. Tras el primer release, **revoca ese token y crea uno nuevo con scope limitado al proyecto** `behemot_framework`.
- Copia el token (`pypi-AgEI...`). Solo se muestra una vez.

Repite lo mismo en TestPyPI: https://test.pypi.org/manage/account/token/.

### 3. Guardar los tokens en `~/.pypirc`

`twine` lee credenciales de ese archivo. Crea `~/.pypirc` con permisos `600`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-AgEI...   ← token de PyPI

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgEI...   ← token de TestPyPI
```

```bash
chmod 600 ~/.pypirc
```

> Alternativa: definir `TWINE_USERNAME=__token__` y `TWINE_PASSWORD=pypi-...` como variables de entorno (mejor si automatizas con GitHub Actions).

---

## Primer release — `0.3.0`

### 1. Limpiar y construir

```bash
cd /home/hernandezbg/proyectos/behemot_framework

# Instalar herramientas de build (una sola vez)
pip install --upgrade build twine

# Limpiar restos de builds anteriores
rm -rf dist/ build/ *.egg-info behemot_framework.egg-info

# Construir sdist + wheel
python -m build
```

Resultado en `dist/`:
- `behemot_framework-0.3.0.tar.gz`  (source distribution)
- `behemot_framework-0.3.0-py3-none-any.whl`  (wheel)

### 2. Verificar el contenido (recomendado)

```bash
# Que no se haya colado nada raro
tar -tzf dist/behemot_framework-0.3.0.tar.gz | head -40

# Validar metadata
twine check dist/*
```

Espera "PASSED" en todo. Si hay errores, suelen ser del long_description (README mal formado).

### 3. Subir a TestPyPI (ensayo)

```bash
twine upload --repository testpypi dist/*
```

Revisa https://test.pypi.org/project/behemot-framework/. Comprueba que se vea bien el README, los classifiers, los extras.

Prueba la instalación desde TestPyPI en otro entorno virtual:

```bash
python -m venv /tmp/test-behemot && source /tmp/test-behemot/bin/activate
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            behemot-framework
```

(El `--extra-index-url` es necesario porque las dependencias de tu paquete viven en PyPI real, no en TestPyPI.)

### 4. Subir a PyPI real

```bash
twine upload dist/*
```

Disponible en ~30 segundos en:
- https://pypi.org/project/behemot-framework/
- `pip install behemot-framework`
- `pip install behemot-framework[rag,voice]`
- `pip install behemot-framework[all]`

---

## Cada release siguiente (0.3.1, 0.4.0, etc.)

```bash
# 1. Bump de versión
#    Editar setup.py → version="0.3.1"
#    (Opcional) actualizar CHANGELOG.md

# 2. Commit + tag
git add setup.py CHANGELOG.md
git commit -m "release: 0.3.1"
git tag v0.3.1
git push && git push --tags

# 3. Build + upload
rm -rf dist/ build/ *.egg-info
python -m build
twine upload dist/*
```

> ⚠️ **PyPI no permite re-subir una versión existente**, ni borrándola. Cada release necesita un número nuevo. Si te equivocas, sube `0.3.1.post1` o `0.3.2`.

---

## Versionado recomendado (SemVer)

- `0.3.0 → 0.3.1` — bug fix, sin cambios de API.
- `0.3.0 → 0.4.0` — features nuevas compatibles.
- `0.3.0 → 1.0.0` — primer release estable o cambios breaking.

Mientras estés en `0.x.x` se asume API inestable, lo cual es razonable para el estado actual del framework.

---

## Automatización (opcional, recomendado más adelante)

Cuando el flujo manual te canse, hay dos mejoras estándar:

1. **Trusted Publishers (PyPI)**: en https://pypi.org/manage/project/behemot-framework/settings/publishing/, autoriza GitHub Actions a publicar sin tokens. Se firma con OIDC.
2. **GitHub Action de release**: workflow que en cada tag `v*` ejecuta `python -m build` + upload. Plantilla oficial: https://docs.pypi.org/trusted-publishers/using-a-publisher/

Hasta entonces, el flujo manual de arriba es perfectamente válido.

---

## Errores comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `400 Bad Request: File already exists` | Intento de re-subir una versión existente | Cambia el número de versión |
| `403 Invalid or non-existent authentication` | Token mal pegado o sin scope | Re-genera token, verifica `~/.pypirc` |
| `long_description` no se renderiza | Markdown inválido | `twine check dist/*` lo detecta antes de subir |
| `pip install` instala 3 GB | `extras_require` no se respeta | Verifica que el usuario use `behemot-framework[rag]` no `[rag]` por sí solo |
| `ModuleNotFoundError: No module named 'tools'` | El usuario olvidó crear su carpeta `tools/` | Es comportamiento esperado del framework; documentado en el README |
