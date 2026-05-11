# models/vertex_model.py
"""
Conector Vertex AI implementado con la librería oficial `google-genai`.

El SDK antiguo (`vertexai` dentro de `google-cloud-aiplatform`) fue
deprecado por Google el 24-jun-2025 y se retira el 24-jun-2026. Esta
implementación usa la librería actual unificada, que soporta tanto la
API pública de Gemini como Vertex AI con sólo cambiar variables de entorno.

Autenticación: Application Default Credentials (cuenta de servicio en
Cloud Run, `gcloud auth application-default login` en local, etc.).
No requiere API key.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .base_model import BaseModel
from behemot_framework.config import Config

logger = logging.getLogger(__name__)


# ---------- Mocks compatibles con el formato OpenAI legacy ----------
# El resto del framework (assistant.py) espera el shape de OpenAI con
# `choices[0].message.content` y `choices[0].message.function_call`.
# Mantenemos esos mocks aquí para no romper el contrato.


class _MockMessage:
    def __init__(self, content: Optional[str] = None, function_call: Any = None):
        self.content = content
        self.function_call = function_call


class _MockChoice:
    def __init__(self, message: _MockMessage):
        self.message = message


class _MockResponse:
    def __init__(self, choice: _MockChoice):
        self.choices = [choice]


class _MockFunctionCall:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


def _text_response(text: str) -> _MockResponse:
    return _MockResponse(_MockChoice(_MockMessage(content=text)))


def _function_call_response(name: str, arguments: str) -> _MockResponse:
    fc = _MockFunctionCall(name=name, arguments=arguments)
    return _MockResponse(_MockChoice(_MockMessage(content=None, function_call=fc)))


# -------------------- Modelo Vertex (google-genai) ------------------


class VertexModel(BaseModel):
    """
    Modelo Vertex AI usando `google-genai`.

    Configuración esperada en el YAML / env:
      - VERTEX_PROJECT_ID  (obligatorio)
      - VERTEX_LOCATION    (default: us-central1)
      - MODEL_NAME         (ej: gemini-2.5-flash-lite)
      - MODEL_TEMPERATURE  (default: 0.7)
      - MODEL_MAX_TOKENS   (default: 2048)
    """

    def __init__(self, api_key: Optional[str] = None):
        # `api_key` se ignora: Vertex usa ADC. El parámetro queda por
        # compatibilidad con la firma de BaseModel.
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as e:
            logger.error(f"google-genai no instalado: {e}")
            raise ImportError(
                "Para usar Vertex AI instala la extra correspondiente:\n"
                "    pip install 'behemot-framework[vertex]'\n"
                "o directamente:  pip install google-genai"
            )

        self._genai = genai
        self._genai_types = genai_types

        self.config = Config.get_config()
        self.project_id = self.config.get("VERTEX_PROJECT_ID")
        self.location = self.config.get("VERTEX_LOCATION", "us-central1")
        self.model_name = self.config.get("MODEL_NAME", "gemini-2.5-flash")
        self.temperature = float(self.config.get("MODEL_TEMPERATURE", 0.7))
        self.max_tokens = int(self.config.get("MODEL_MAX_TOKENS", 2048))

        if not self.project_id:
            raise ValueError("VERTEX_PROJECT_ID es obligatorio para usar Vertex AI")

        # El cliente de google-genai en modo Vertex acepta project/location
        # directamente; no hay que tocar variables de entorno globales.
        self.client = genai.Client(
            vertexai=True,
            project=self.project_id,
            location=self.location,
        )

        logger.info(
            f"Modelo Vertex AI inicializado (google-genai): "
            f"{self.model_name} en {self.project_id}/{self.location}"
        )

    # ---- Capacidades ----

    def soporta_vision(self) -> bool:
        """Todos los modelos Gemini 1.5+ soportan imágenes nativamente."""
        return "gemini" in self.model_name.lower()

    # ---- Helpers ----

    def _build_generation_config(self):
        return self._genai_types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )

    def _flatten_conversation(self, conversation: List[Dict[str, str]]) -> str:
        """
        Aplana la conversación OpenAI-style a un único prompt textual.
        google-genai admite también listas de Content tipadas, pero esta
        forma textual es la que el resto del framework asume hoy.
        """
        parts: List[str] = []
        for msg in conversation:
            role = msg.get("role", "user")
            content = msg.get("content", "") or ""
            if role == "system":
                parts.append(f"Sistema: {content}")
            elif role == "user":
                parts.append(f"Usuario: {content}")
            elif role == "assistant":
                parts.append(f"Asistente: {content}")
            elif role == "function":
                fname = msg.get("name", "función")
                parts.append(f"Resultado de {fname}: {content}")
        parts.append("Asistente:")
        return "\n\n".join(parts)

    def _load_image_part(self, imagen_path: str):
        """Construye un Part de imagen a partir de una ruta local."""
        with open(imagen_path, "rb") as fh:
            data = fh.read()
        # google-genai infiere el mime; lo dejamos en image/jpeg como default.
        return self._genai_types.Part.from_bytes(data=data, mime_type="image/jpeg")

    # ---- Métodos del contrato BaseModel ----

    def generar_respuesta(
        self,
        mensaje_usuario: str,
        prompt_sistema: str,
        imagen_path: Optional[str] = None,
    ) -> str:
        try:
            prompt = f"{prompt_sistema}\n\nUsuario: {mensaje_usuario}\nAsistente:"

            if imagen_path and self.soporta_vision():
                try:
                    image_part = self._load_image_part(imagen_path)
                    contents = [prompt, image_part]
                except Exception as e:
                    logger.error(f"Error cargando imagen {imagen_path}: {e}")
                    contents = prompt
            else:
                contents = prompt

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=self._build_generation_config(),
            )
            return (response.text or "").strip()
        except Exception as e:
            logger.error(f"Error en Vertex AI: {e}")
            return f"Error en la API de Vertex AI: {e}"

    def generar_respuesta_desde_contexto(self, conversation: List[Dict[str, str]]) -> str:
        try:
            prompt = self._flatten_conversation(conversation)
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=self._build_generation_config(),
            )
            return (response.text or "").strip()
        except Exception as e:
            logger.error(f"Error generando respuesta desde contexto (Vertex): {e}")
            return f"Error en la API de Vertex AI: {e}"

    def generar_respuesta_con_functions(
        self,
        conversation: List[Dict[str, str]],
        functions: List[Dict[str, Any]],
    ) -> Any:
        """
        Function calling vía prompt engineering.

        Gemini soporta function calling nativo en google-genai, pero el
        resto del framework (assistant.py) hoy espera el shape antiguo
        de OpenAI con `function_call.name` y `function_call.arguments`.
        Mantenemos el approach de prompt engineering para no romper ese
        contrato; la migración a tool calls nativos está en el plan de
        mejoras del framework.
        """
        try:
            logger.info("🔧 Vertex AI: function calling vía prompt engineering")

            prompt_parts: List[str] = []
            for msg in conversation:
                role = msg.get("role", "user")
                content = msg.get("content", "") or ""
                if role == "system":
                    prompt_parts.append(f"Sistema: {content}")
                elif role == "user":
                    prompt_parts.append(f"Usuario: {content}")
                elif role == "assistant":
                    prompt_parts.append(f"Asistente: {content}")
                elif role == "function":
                    fname = msg.get("name", "función")
                    prompt_parts.append(f"Resultado de {fname}: {content}")

            if functions:
                tools_text = "\n".join(
                    f"- {f['name']}: {f.get('description', '')}"
                    for f in functions
                )
                prompt_parts.append(f"\nHerramientas disponibles:\n{tools_text}")
                prompt_parts.append(
                    "\nSi necesitas información que no tienes, responde EXACTAMENTE en este formato:"
                )
                prompt_parts.append("USAR_HERRAMIENTA: nombre_herramienta")
                prompt_parts.append('ARGUMENTOS: {"parametro": "valor"}')

            prompt_parts.append("\nAsistente:")
            full_prompt = "\n".join(prompt_parts)

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=self._build_generation_config(),
            )
            text = (response.text or "").strip()

            return self._parse_tool_decision(text)
        except Exception as e:
            logger.error(f"Error en function calling con Vertex AI: {e}")
            # Fallback: respuesta sin herramientas
            try:
                fallback_text = self.generar_respuesta_desde_contexto(conversation)
                return _text_response(fallback_text)
            except Exception:
                return _text_response("Error al generar respuesta.")

    # ---- Parser de la salida de prompt engineering ----

    def _parse_tool_decision(self, response_text: str) -> _MockResponse:
        """
        Detecta si la respuesta indica una invocación de herramienta y
        construye el mock correspondiente al formato OpenAI legacy.
        """
        if "USAR_HERRAMIENTA:" not in response_text:
            return _text_response(response_text)

        tool_name: Optional[str] = None
        arguments: str = "{}"
        for line in response_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("USAR_HERRAMIENTA:"):
                tool_name = stripped.replace("USAR_HERRAMIENTA:", "", 1).strip()
            elif stripped.startswith("ARGUMENTOS:"):
                arguments = stripped.replace("ARGUMENTOS:", "", 1).strip() or "{}"

        if not tool_name:
            return _text_response(response_text)

        # Sanity-check que `arguments` sea JSON parseable; si no, lo dejamos
        # como objeto vacío para que tooling.call_tool no haga estallar nada.
        try:
            json.loads(arguments)
        except Exception:
            arguments = "{}"

        logger.info(f"🔧 Vertex AI invoca herramienta: {tool_name}")
        return _function_call_response(tool_name, arguments)
