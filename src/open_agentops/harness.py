from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .config import load_yaml


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "scenario"


def normalize_suite(suite: dict[str, Any], *, source: str | Path | None = None) -> dict[str, Any]:
    """Normalize scenario/test-case YAML and legacy eval-suite YAML."""

    scenario_id = suite.get("scenario") or suite.get("suite") or suite.get("name")
    cases = suite.get("tests") if "tests" in suite else suite.get("cases")
    if cases is None:
        cases = []

    normalized_cases: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            normalized_cases.append(case)
            continue
        item = dict(case)
        if "id" not in item and item.get("name"):
            item["id"] = slugify(str(item["name"]))
        if "id" not in item and item.get("description"):
            item["id"] = slugify(str(item["description"]))
        item.setdefault("id", f"case_{index + 1}")
        if "input" not in item and "vars" in item:
            item["input"] = item["vars"]
        if "expect" not in item and "assert" in item:
            item["expect"] = item["assert"]
        normalized_cases.append(item)

    return {
        **suite,
        "suite": scenario_id or (Path(source).stem if source else "scenario"),
        "scenario": scenario_id or (Path(source).stem if source else "scenario"),
        "cases": normalized_cases,
        "tests": normalized_cases,
    }


def new_scenario(agent_id: str, scenario_id: str, *, description: str = "") -> dict[str, Any]:
    return {
        "version": 1,
        "scenario": scenario_id,
        "description": description,
        "agent": agent_id,
        "tests": [],
    }


def build_test_case(
    *,
    case_id: str,
    user: str,
    contains: list[str] | None = None,
    must_not_contain: list[str] | None = None,
    tool_called: list[str] | None = None,
    tool_not_called: list[str] | None = None,
    approval_required_for: list[str] | None = None,
) -> dict[str, Any]:
    assertions: dict[str, Any] = {}
    if tool_called:
        assertions["tools_called"] = tool_called
    if tool_not_called:
        assertions["tools_not_called"] = tool_not_called
    if approval_required_for:
        assertions["approval_required_for"] = approval_required_for
    final_answer: dict[str, Any] = {}
    if contains:
        final_answer["contains"] = contains
    if must_not_contain:
        final_answer["must_not_contain"] = must_not_contain
    if final_answer:
        assertions["final_answer"] = final_answer
    return {
        "id": case_id,
        "input": {"user": user},
        "assert": assertions,
    }


def write_scenario(path: str | Path, scenario: dict[str, Any], *, force: bool = False) -> Path:
    out = Path(path)
    if out.exists() and not force:
        raise FileExistsError(f"{out} already exists; pass --force to overwrite")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(scenario, sort_keys=False), encoding="utf-8")
    return out


def append_test_case(path: str | Path, case: dict[str, Any]) -> Path:
    suite_path = Path(path)
    suite = load_yaml(suite_path)
    key = "tests" if "tests" in suite or "scenario" in suite else "cases"
    cases = suite.setdefault(key, [])
    if not isinstance(cases, list):
        raise ValueError(f"{suite_path}: {key} must be a list")
    case_id = case.get("id")
    if case_id and any(isinstance(item, dict) and item.get("id") == case_id for item in cases):
        raise ValueError(f"{suite_path}: test case {case_id!r} already exists")
    cases.append(case)
    suite_path.write_text(yaml.safe_dump(suite, sort_keys=False), encoding="utf-8")
    return suite_path
