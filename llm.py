import json
import os

import anthropic

MODELO = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
# Para pasos rápidos y repetitivos (planear consultas, re-ranking) alcanza un modelo más barato
MODELO_RAPIDO = os.environ.get("CLAUDE_MODEL_RAPIDO", "claude-haiku-5-5")

# Estos modelos aceptan `fallbacks="default"`: si el modelo rechaza la petición,
# la API la reintenta automáticamente en otro modelo adecuado.
_MODELOS_CON_FALLBACK = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

_client = None


def cliente() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class ErrorLLM(Exception):
    pass


def crear_mensaje(modelo: str = MODELO, **kwargs):
    extra = {}
    if modelo in _MODELOS_CON_FALLBACK:
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    resp = cliente().beta.messages.create(model=modelo, **extra, **kwargs)
    if resp.stop_reason == "refusal":
        raise ErrorLLM("El modelo rechazó la petición.")
    if resp.stop_reason == "max_tokens":
        raise ErrorLLM("La respuesta se cortó por max_tokens.")
    return resp


def texto(resp) -> str:
    return "".join(b.text for b in resp.content if b.type == "text")


def pedir_json(prompt: str, schema: dict, modelo: str = MODELO_RAPIDO, system: str = "", max_tokens: int = 4000) -> dict:
    """Pide una respuesta que cumple exactamente un JSON Schema (structured outputs)."""
    kwargs = {"system": system} if system else {}
    resp = crear_mensaje(
        modelo=modelo,
        max_tokens=max_tokens,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    return json.loads(texto(resp))
