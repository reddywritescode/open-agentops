from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def load_config(path: str | Path) -> dict[str, Any]:
    config = load_yaml(path)
    if "agents" not in config:
        raise ValueError("agentops config must define agents")
    return config


def tool_policies(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tools = config.get("tools") or {}
    if not isinstance(tools, dict):
        raise ValueError("tools must be a mapping")
    return {str(name): dict(policy or {}) for name, policy in tools.items()}

