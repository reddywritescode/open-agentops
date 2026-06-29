from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


RISK_KEYWORDS = {
    "destructive": ["delete", "remove", "drop", "destroy", "refund", "cancel_subscription", "cancel_plan", "page"],
    "write": ["update", "create", "insert", "send", "post", "publish", "assign", "label", "approval", "request"],
    "read": ["get", "list", "search", "lookup", "read", "find", "fetch"],
}


def classify_name(name: str) -> str:
    lower = name.lower()
    normalized = lower.lstrip("_")
    for keyword in RISK_KEYWORDS["read"]:
        if normalized.startswith(keyword):
            return "read"
    for risk, keywords in RISK_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            return risk
    return "unknown"


def scan_python_file(path: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    findings: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            decorators = []
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name):
                    decorators.append(dec.id)
                elif isinstance(dec, ast.Attribute):
                    decorators.append(dec.attr)
                elif isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Name):
                        decorators.append(dec.func.id)
                    elif isinstance(dec.func, ast.Attribute):
                        decorators.append(dec.func.attr)
            risk = classify_name(name)
            if name.startswith("_") and "tool" not in decorators:
                continue
            if name.endswith(("_safe", "_unsafe")) and "tool" not in decorators:
                continue
            if "tool" in decorators or risk != "unknown":
                findings.append(
                    {
                        "file": str(path),
                        "function": name,
                        "decorators": decorators,
                        "classification": risk,
                    }
                )
    return findings


def scan_repo(root: str | Path) -> dict[str, Any]:
    base = Path(root)
    python_files = [p for p in base.rglob("*.py") if ".venv" not in p.parts and "__pycache__" not in p.parts]
    findings: list[dict[str, Any]] = []
    for path in python_files:
        findings.extend(scan_python_file(path))
    return {
        "root": str(base),
        "python_files": len(python_files),
        "tools_or_risks": findings,
        "summary": {
            "total_findings": len(findings),
            "risky": sum(1 for item in findings if item["classification"] in {"write", "destructive"}),
            "unknown": sum(1 for item in findings if item["classification"] == "unknown"),
        },
    }
