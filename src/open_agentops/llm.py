from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def call_openai(messages: list[dict[str, str]], *, model: str | None = None) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    payload = {
        "model": model or os.environ.get("OPEN_AGENTOPS_LLM_MODEL", "gpt-4o-mini"),
        "messages": messages,
        "temperature": 0,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed: HTTP {exc.code}: {detail}") from exc
    return str(data["choices"][0]["message"]["content"])


def call_anthropic(messages: list[dict[str, str]], *, model: str | None = None) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    system_parts = [message["content"] for message in messages if message.get("role") == "system"]
    user_messages = [
        {"role": message.get("role", "user"), "content": message.get("content", "")}
        for message in messages
        if message.get("role") != "system"
    ]
    payload = {
        "model": model or os.environ.get("OPEN_AGENTOPS_LLM_MODEL", "claude-3-5-sonnet-latest"),
        "max_tokens": 4096,
        "temperature": 0,
        "system": "\n\n".join(system_parts),
        "messages": user_messages,
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Anthropic request failed: HTTP {exc.code}: {detail}") from exc
    return "\n".join(str(item.get("text", "")) for item in data.get("content", []) if item.get("type") == "text")


def call_model(provider: str, messages: list[dict[str, str]], *, model: str | None = None) -> str:
    if provider == "openai":
        return call_openai(messages, model=model)
    if provider == "anthropic":
        return call_anthropic(messages, model=model)
    raise ValueError(f"unsupported provider {provider!r}; expected openai or anthropic")


def llm_score(rubric: str, output: str, *, model: str | None = None) -> tuple[float, str]:
    prompt = (
        "You are grading an AI agent eval. Return strict JSON with keys score and reason. "
        "score must be a number from 0 to 1.\n\n"
        f"Rubric:\n{rubric}\n\nAgent output:\n{output}"
    )
    provider = os.environ.get("OPEN_AGENTOPS_JUDGE_PROVIDER", "openai")
    content = call_model(
        provider,
        [
            {"role": "system", "content": "You are a precise eval judge."},
            {"role": "user", "content": prompt},
        ],
        model=model,
    )
    try:
        data = json.loads(content)
        return float(data.get("score", 0)), str(data.get("reason", ""))
    except Exception:
        lowered = content.lower()
        if "pass" in lowered and "fail" not in lowered:
            return 1.0, content
        return 0.0, content
