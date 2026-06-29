from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


READ_VERBS = ("get", "list", "search", "lookup", "read", "find", "fetch", "retrieve", "query")
WRITE_VERBS = ("create", "update", "send", "post", "publish", "insert", "upsert", "assign", "label", "comment", "reply")
DESTRUCTIVE_VERBS = ("delete", "remove", "drop", "destroy", "refund", "cancel", "revoke", "disable", "charge", "transfer")


def load_tool_manifest(path: str | Path) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, list):
        tools = raw
    elif isinstance(raw, dict) and isinstance(raw.get("tools"), list):
        tools = raw["tools"]
    elif isinstance(raw, dict) and isinstance(raw.get("actions"), list):
        tools = raw["actions"]
    elif isinstance(raw, dict) and "paths" in raw:
        tools = _tools_from_openapi(raw)
    else:
        raise ValueError("Unsupported manifest: expected tools/actions list or OpenAPI paths")
    return [_normalize_tool(tool) for tool in tools]


def _tools_from_openapi(raw: dict[str, Any]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for path, path_item in (raw.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            name = op.get("operationId") or f"{method}_{path.strip('/').replace('/', '_').replace('{', '').replace('}', '')}"
            tools.append(
                {
                    "name": name,
                    "description": op.get("description") or op.get("summary") or "",
                    "method": method.upper(),
                    "path": path,
                    "inputSchema": op.get("requestBody") or op.get("parameters") or {},
                }
            )
    return tools


def _normalize_tool(tool: dict[str, Any]) -> dict[str, Any]:
    name = str(tool.get("name") or tool.get("slug") or tool.get("operationId") or tool.get("id") or "unknown_tool")
    return {
        "name": name,
        "description": str(tool.get("description") or tool.get("summary") or ""),
        "input_schema": tool.get("inputSchema") or tool.get("input_schema") or tool.get("schema") or {},
        "raw": tool,
    }


def classify_effect(tool: dict[str, Any]) -> str:
    text = f"{tool.get('name', '')} {tool.get('description', '')}".lower()
    tokens = tuple(filter(None, re.split(r"[^a-z0-9]+", text)))
    if any(verb in tokens or text.startswith(f"{verb}_") for verb in DESTRUCTIVE_VERBS):
        return "destructive"
    if any(verb in tokens or text.startswith(f"{verb}_") for verb in WRITE_VERBS):
        return "write"
    if any(verb in tokens or text.startswith(f"{verb}_") for verb in READ_VERBS):
        return "read"
    method = str((tool.get("raw") or {}).get("method") or "").upper()
    if method == "GET":
        return "read"
    if method == "DELETE":
        return "destructive"
    if method in {"POST", "PUT", "PATCH"}:
        return "write"
    return "unknown"


def simulator_name(tool_name: str) -> str:
    if "." in tool_name:
        return tool_name.split(".", 1)[0].lower()
    if "_" in tool_name:
        return tool_name.split("_", 1)[0].lower()
    return re.sub(r"[^a-z0-9]+", "-", tool_name.lower()).strip("-") or "generic"


def generate_policy_from_tools(tools: list[dict[str, Any]]) -> dict[str, Any]:
    policies: dict[str, Any] = {}
    simulator_specs: dict[str, Any] = {}
    for tool in tools:
        name = tool["name"]
        effect = classify_effect(tool)
        sim = simulator_name(name)
        if effect == "read":
            ci_mode = "live"
        elif effect == "write":
            ci_mode = "simulate"
        elif effect == "destructive":
            ci_mode = "block"
        else:
            ci_mode = "block"
        policies[name] = {
            "effect": effect,
            "ci_mode": ci_mode,
            "staging_mode": "sandbox" if effect in {"write", "destructive"} else "live",
            "production_mode": "approval_required" if effect in {"write", "destructive", "unknown"} else "live",
            "simulator": sim,
            "review_required": effect == "unknown",
        }
        simulator_specs.setdefault(
            sim,
            {
                "type": "generic",
                "resources": {},
                "tools": [],
            },
        )
        simulator_specs[sim]["tools"].append(
            {
                "name": name,
                "effect": effect,
                "input_schema": tool.get("input_schema") or {},
                "description": tool.get("description") or "",
            }
        )
    return {"tools": policies, "simulators": simulator_specs}


def generate_policy_yaml(manifest_path: str | Path) -> str:
    tools = load_tool_manifest(manifest_path)
    generated = generate_policy_from_tools(tools)
    generated["generated"] = True
    generated["review_required"] = any(policy.get("review_required") for policy in generated["tools"].values())
    return yaml.safe_dump(generated, sort_keys=False)


class GenericStatefulSimulator:
    """Fallback simulator for generated MCP/OpenAPI/custom tool manifests."""

    def __init__(self, name: str, spec: dict[str, Any] | None = None):
        self.name = name
        self.spec = spec or {}
        self.records: dict[str, list[dict[str, Any]]] = {}
        self.next_id = 1

    def call(self, tool_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        effect = self._effect_for(tool_name)
        resource = self._resource_for(tool_name)
        if effect == "read":
            return {"ok": True, "simulated": True, "tool": tool_name, "records": self.records.get(resource, [])}
        record_id = f"sim_{resource}_{self.next_id:03d}"
        self.next_id += 1
        record = {
            "id": record_id,
            "tool": tool_name,
            "effect": effect,
            "args": {"args": list(args), "kwargs": kwargs},
        }
        self.records.setdefault(resource, []).append(record)
        return {"ok": True, "simulated": True, "tool": tool_name, "id": record_id, "resource": resource}

    def _effect_for(self, tool_name: str) -> str:
        for tool in self.spec.get("tools", []):
            if tool.get("name") == tool_name:
                return str(tool.get("effect") or "write")
        return "write"

    def _resource_for(self, tool_name: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", tool_name.lower()).strip("_")
        parts = normalized.split("_")
        if parts and parts[0] in READ_VERBS + WRITE_VERBS + DESTRUCTIVE_VERBS:
            parts = parts[1:]
        return "_".join(parts[:2]) or normalized or "resource"

    def state(self) -> dict[str, Any]:
        return {"name": self.name, "records": self.records}

