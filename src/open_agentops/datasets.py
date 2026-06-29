from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config import load_config, load_yaml
from .harness import normalize_suite
from .validator import validate_eval_suite


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _scenario_entry(path: Path, root: Path, *, status: str = "approved", owner: str | None = None, tags: list[str] | None = None) -> dict[str, Any]:
    suite = normalize_suite(load_yaml(path), source=path)
    entry = {
        "path": _rel(path, root),
        "agent": suite.get("agent"),
        "scenario": suite.get("scenario"),
        "status": status,
        "generated": bool(suite.get("generated")),
        "review_required": bool(suite.get("review_required")),
        "tags": tags or [],
    }
    if owner:
        entry["owner"] = owner
    return entry


def init_dataset(config_path: str | Path, output_path: str | Path, *, force: bool = False) -> Path:
    config_path = Path(config_path).resolve()
    root = config_path.parent
    config = load_config(config_path)
    scenarios: list[dict[str, Any]] = []
    for agent_id, agent in (config.get("agents") or {}).items():
        for suite in agent.get("test_suites") or agent.get("eval_suites") or []:
            suite_path = (root / suite).resolve()
            if suite_path.exists():
                scenarios.append(_scenario_entry(suite_path, root, status="approved"))
            else:
                scenarios.append(
                    {
                        "path": str(suite),
                        "agent": agent_id,
                        "scenario": Path(str(suite)).stem,
                        "status": "missing",
                        "generated": False,
                        "review_required": True,
                        "tags": [],
                    }
                )
    dataset = {
        "version": 1,
        "name": f"{root.name}-agentops-dataset",
        "root": str(root),
        "config": _rel(config_path, root),
        "scenarios": scenarios,
    }
    out = Path(output_path)
    if out.exists() and not force:
        raise FileExistsError(f"{out} already exists; pass --force to overwrite")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(dataset, sort_keys=False, width=120), encoding="utf-8")
    return out


def load_dataset(path: str | Path) -> dict[str, Any]:
    data = load_yaml(path)
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError(f"{path}: scenarios must be a list")
    return data


def list_dataset(path: str | Path) -> list[dict[str, Any]]:
    return list(load_dataset(path).get("scenarios") or [])


def validate_dataset(path: str | Path) -> list[str]:
    dataset_path = Path(path).resolve()
    dataset = load_dataset(dataset_path)
    root = Path(dataset.get("root") or dataset_path.parent).resolve()
    errors: list[str] = []
    for index, scenario in enumerate(dataset.get("scenarios") or []):
        scenario_path = root / str(scenario.get("path") or "")
        agent_id = str(scenario.get("agent") or "")
        if not scenario_path.exists():
            errors.append(f"scenario {index} missing file: {scenario_path}")
            continue
        errors.extend(validate_eval_suite(scenario_path, agent_id or None))
    return errors


def promote_scenario(
    dataset_path: str | Path,
    scenario_path: str | Path,
    *,
    status: str = "approved",
    owner: str | None = None,
    tags: list[str] | None = None,
) -> Path:
    dataset_file = Path(dataset_path).resolve()
    dataset = load_dataset(dataset_file)
    root = Path(dataset.get("root") or dataset_file.parent).resolve()
    entry = _scenario_entry(
        (root / scenario_path).resolve() if not Path(scenario_path).is_absolute() else Path(scenario_path),
        root,
        status=status,
        owner=owner,
        tags=tags,
    )
    scenarios = dataset.setdefault("scenarios", [])
    for index, existing in enumerate(scenarios):
        if existing.get("path") == entry["path"]:
            scenarios[index] = {**existing, **entry}
            break
    else:
        scenarios.append(entry)
    dataset_file.write_text(yaml.safe_dump(dataset, sort_keys=False, width=120), encoding="utf-8")
    return dataset_file


def coverage_report(dataset_path: str | Path, config_path: str | Path | None = None) -> dict[str, Any]:
    dataset_file = Path(dataset_path).resolve()
    dataset = load_dataset(dataset_file)
    root = Path(dataset.get("root") or dataset_file.parent).resolve()
    expected_tools: set[str] = set()
    destructive_tools: set[str] = set()
    if config_path:
        config = load_config(config_path)
        for name, policy in (config.get("tools") or {}).items():
            expected_tools.add(str(name))
            if (policy or {}).get("effect") == "destructive":
                destructive_tools.add(str(name))

    covered_tools: set[str] = set()
    forbidden_tools: set[str] = set()
    approval_cases = 0
    privacy_cases = 0
    generated = 0
    review_required = 0
    by_status: dict[str, int] = {}
    for scenario in dataset.get("scenarios") or []:
        by_status[str(scenario.get("status") or "unknown")] = by_status.get(str(scenario.get("status") or "unknown"), 0) + 1
        generated += int(bool(scenario.get("generated")))
        review_required += int(bool(scenario.get("review_required")))
        scenario_path = root / str(scenario.get("path") or "")
        if not scenario_path.exists():
            continue
        suite = normalize_suite(load_yaml(scenario_path), source=scenario_path)
        for case in suite.get("cases") or []:
            expect = case.get("expect") or {}
            covered_tools.update(str(item) for item in expect.get("tools_called") or [])
            forbidden_tools.update(str(item) for item in expect.get("tools_not_called") or [])
            if expect.get("approval_required_for"):
                approval_cases += 1
            if expect.get("privacy") or expect.get("secrets"):
                privacy_cases += 1
    return {
        "dataset": str(dataset_file),
        "scenarios_total": len(dataset.get("scenarios") or []),
        "by_status": by_status,
        "generated": generated,
        "review_required": review_required,
        "tools_expected": sorted(expected_tools),
        "tools_covered": sorted(covered_tools),
        "tools_missing": sorted(expected_tools - covered_tools),
        "destructive_tools": sorted(destructive_tools),
        "destructive_tools_forbidden": sorted(destructive_tools & forbidden_tools),
        "destructive_tools_missing_forbidden_checks": sorted(destructive_tools - forbidden_tools),
        "approval_cases": approval_cases,
        "privacy_or_secret_cases": privacy_cases,
    }
