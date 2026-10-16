"""Gemini clients (Vertex AI / Gemini Enterprise Agent Platform).

On Cloud Run the client authenticates as the service's own service account via
Application Default Credentials - there is no API key anywhere in the system.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .config import get_settings

log = logging.getLogger(__name__)


# Shared-capacity models can briefly return 429/503 under load; back off and retry.
RETRY = types.HttpOptions(retry_options=types.HttpRetryOptions(
    attempts=3, initial_delay=0.8, max_delay=4.0, exp_base=2.0, jitter=0.5,
    http_status_codes=[429, 500, 503, 504]))


@lru_cache
def client() -> genai.Client:
    s = get_settings()
    return genai.Client(vertexai=True, project=s.project_id or None, location=s.gemini_location,
                        http_options=RETRY)


@lru_cache
def live_client() -> genai.Client:
    s = get_settings()
    return genai.Client(vertexai=True, project=s.project_id or None, location=s.live_location)


async def generate(model: str, contents, config: types.GenerateContentConfig) -> types.GenerateContentResponse:
    """generate_content with a fallback model when the primary is out of capacity."""
    s = get_settings()
    try:
        return await client().aio.models.generate_content(model=model, contents=contents, config=config)
    except genai_errors.APIError as exc:
        if exc.code not in (429, 503) or not s.model_fallback or model == s.model_fallback:
            raise
        log.warning("%s unavailable (%s); falling back to %s", model, exc.code, s.model_fallback)
        return await client().aio.models.generate_content(model=s.model_fallback, contents=contents, config=config)


def json_config(schema: dict, *, system: str | None = None, thinking: str = "LOW",
                temperature: float = 0.2, tools: list | None = None) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json",
        response_json_schema=schema,
        thinking_config=types.ThinkingConfig(thinking_level=thinking),
        tools=tools,
    )


def parse_json(resp: types.GenerateContentResponse) -> dict[str, Any]:
    text = (resp.text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning("model returned non-JSON output: %.200s", text)
        raise


async def embed(texts: list[str], task_type: str = "SEMANTIC_SIMILARITY") -> list[list[float]]:
    s = get_settings()
    resp = await client().aio.models.embed_content(
        model=s.model_embed,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=s.embed_dim, task_type=task_type),
    )
    return [e.values for e in resp.embeddings]
