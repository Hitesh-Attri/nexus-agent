"""Client for the resilient-llm-gateway. All reasoning goes through it, so the
agent inherits the gateway's retries and provider fallback for free."""

from __future__ import annotations

import json
from typing import Any

import httpx

from core.config import get_settings
from core.decision import DECISION_SCHEMA


class GatewayError(RuntimeError):
    """The gateway was unreachable, timed out, or returned an unusable body."""


def decide(system: str, user: str) -> dict[str, Any]:
    """Ask the model for one decision. Returns the validated JSON object."""
    settings = get_settings()
    payload = {
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "response_schema": DECISION_SCHEMA,
    }
    try:
        resp = httpx.post(
            f"{settings.gateway_url}/v1/chat",
            json=payload,
            timeout=settings.gateway_timeout,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise GatewayError(str(e)) from e

    data = resp.json()
    parsed = data.get("parsed")
    if parsed is None:
        # The gateway populates `parsed` when a response_schema validates; fall
        # back to decoding `content` so a provider that skips it still works.
        try:
            parsed = json.loads(data.get("content", ""))
        except json.JSONDecodeError as e:
            raise GatewayError(f"response was not valid JSON: {e}") from e
    return parsed