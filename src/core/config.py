"""Typed configuration, loaded once from the environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The agent reasons by calling the gateway; it never talks to a model vendor.
    gateway_url: str = "http://localhost:8080"

    # Backs the knowledge-base search tool.
    rag_url: str = "http://localhost:8081"

    # Hard cap on reason->act->observe cycles. Without this a confused model can
    # loop until it burns the budget, so the loop is bounded by construction.
    max_iterations: int = 6

    gateway_timeout: float = 60.0
    tool_timeout: float = 20.0


@lru_cache
def get_settings() -> Settings:
    return Settings()