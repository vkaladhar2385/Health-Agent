"""Model adapter: swap Anthropic Claude and OpenAI behind one interface."""

from __future__ import annotations

import os
from typing import Any, Protocol

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class ChatModelFactory(Protocol):
    def __call__(self) -> BaseChatModel: ...


def load_project_env() -> None:
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def provider_name() -> str:
    return (os.environ.get("PHA_PROVIDER") or "anthropic").strip().lower()


def model_name() -> str:
    provider = provider_name()
    if provider == "openai":
        return (os.environ.get("PHA_MODEL") or DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL
    return (os.environ.get("PHA_MODEL") or DEFAULT_ANTHROPIC_MODEL).strip() or DEFAULT_ANTHROPIC_MODEL


def get_chat_model(**overrides: Any) -> BaseChatModel:
    """Return the configured chat model. PHA_PROVIDER=anthropic|openai."""
    load_project_env()
    provider = provider_name()
    if provider == "openai":
        return _openai_model(**overrides)
    if provider == "anthropic":
        return _anthropic_model(**overrides)
    raise RuntimeError(f"Unknown PHA_PROVIDER {provider!r}. Use anthropic or openai.")


def _anthropic_model(**overrides: Any) -> BaseChatModel:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is missing. Set it in .env.")
    params = {
        "model": model_name(),
        "api_key": key,
        "max_tokens": 1024,
    }
    params.update(overrides)
    return ChatAnthropic(**params)


def _openai_model(**overrides: Any) -> BaseChatModel:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "langchain-openai is not installed. Run: uv add langchain-openai"
        ) from exc
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing. Set it in .env for PHA_PROVIDER=openai.")
    params = {
        "model": model_name(),
        "api_key": key,
        "max_tokens": 1024,
    }
    params.update(overrides)
    return ChatOpenAI(**params)


def extract_usage(message: Any) -> tuple[int, int]:
    """Best-effort token usage from a LangChain message."""
    meta = getattr(message, "usage_metadata", None) or {}
    if isinstance(meta, dict) and meta:
        return int(meta.get("input_tokens") or 0), int(meta.get("output_tokens") or 0)
    resp = getattr(message, "response_metadata", None) or {}
    usage = resp.get("usage") or resp.get("token_usage") or {}
    if isinstance(usage, dict):
        inp = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        out = usage.get("output_tokens") or usage.get("completion_tokens") or 0
        return int(inp), int(out)
    return 0, 0


def message_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
    return "\n".join(part.strip() for part in parts if part.strip())
