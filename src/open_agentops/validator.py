from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_config, load_yaml
from .harness import normalize_suite


VALID_EFFECTS = {"read", "write", "destructive", "unknown"}
VALID_MODES = {"live", "simulate", "sandbox", "approval_required", "block"}
VALID_PII_KINDS = {"all", "email", "phone", "ssn", "credit_card"}
VALID_SECRET_KINDS = {"all", "api_key", "secret_assignment"}


def validate_config(path: str | Path) -> list[str]:
    errors: list[str] = []
    path = Path(path)
    try:
        config = load_config(path)
    except Exception as exc:
        return [str(exc)]

    agents = config.get("agents")
    if not isinstance(agents, dict) or not agents:
        errors.append("agents must be a non-empty mapping")
    else:
        for agent_id, agent in agents.items():
            if not isinstance(agent, dict):
                errors.append(f"agent {agent_id} must be an object")
                continue
            runner = agent.get("runner", "entrypoint")
            if runner == "entrypoint" and not agent.get("entrypoint"):
                errors.append(f"agent {agent_id} is missing entrypoint")
            if runner == "command" and not agent.get("command"):
                errors.append(f"agent {agent_id} command runner is missing command")
            if runner == "http" and not agent.get("url"):
                errors.append(f"agent {agent_id} http runner is missing url")
            suites = agent.get("test_suites") or agent.get("eval_suites") or []
            if not suites:
                errors.append(f"agent {agent_id} has no test_suites/eval_suites")
            for suite in suites:
                suite_path = (path.parent / suite).resolve()
                if not suite_path.exists():
                    errors.append(f"agent {agent_id} test suite not found: {suite}")
                else:
                    errors.extend(validate_eval_suite(suite_path, agent_id))

    tools = config.get("tools") or {}
    if not isinstance(tools, dict):
        errors.append("tools must be a mapping")
    else:
        for tool_name, policy in tools.items():
            if not isinstance(policy, dict):
                errors.append(f"tool {tool_name} policy must be an object")
                continue
            effect = policy.get("effect", "unknown")
            if effect not in VALID_EFFECTS:
                errors.append(f"tool {tool_name} has invalid effect {effect!r}")
            for key in ("ci_mode", "staging_mode", "production_mode", "mode"):
                if key in policy and policy[key] not in VALID_MODES:
                    errors.append(f"tool {tool_name} has invalid {key} {policy[key]!r}")

    gate = config.get("gate") or {}
    if "min_score" in gate:
        try:
            score = float(gate["min_score"])
            if score < 0 or score > 1:
                errors.append("gate.min_score must be between 0 and 1")
        except (TypeError, ValueError):
            errors.append("gate.min_score must be numeric")
    return errors


def validate_eval_suite(path: str | Path, agent_id: str | None = None) -> list[str]:
    errors: list[str] = []
    try:
        suite = normalize_suite(load_yaml(path), source=path)
    except Exception as exc:
        return [str(exc)]
    if agent_id and suite.get("agent") != agent_id:
        errors.append(f"{path}: suite agent {suite.get('agent')!r} does not match config agent {agent_id!r}")
    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append(f"{path}: tests/cases must be a non-empty list")
        return errors
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"{path}: case {index} must be an object")
            continue
        if not case.get("id"):
            errors.append(f"{path}: case {index} is missing id")
        if "input" not in case:
            errors.append(f"{path}: case {case.get('id', index)} is missing input")
        if "expect" not in case:
            errors.append(f"{path}: case {case.get('id', index)} is missing assert/expect")
            continue
        expect = case.get("expect") or {}
        if not isinstance(expect, dict):
            errors.append(f"{path}: case {case.get('id', index)} expect must be an object")
            continue
        errors.extend(_validate_expect(path, case.get("id", index), expect))
    return errors


def _as_list(value: Any) -> list[Any]:
    if value is True or value is False or value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _validate_expect(path: str | Path, case_id: str | int, expect: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    privacy = expect.get("privacy") or {}
    if privacy and not isinstance(privacy, dict):
        errors.append(f"{path}: case {case_id} privacy must be an object")
    elif privacy:
        for key in ("forbidden_pii", "allowed_pii"):
            invalid = {str(item) for item in _as_list(privacy.get(key))} - VALID_PII_KINDS
            if invalid:
                errors.append(f"{path}: case {case_id} privacy.{key} has invalid values {sorted(invalid)}")

    secrets = expect.get("secrets") or {}
    if secrets and not isinstance(secrets, dict):
        errors.append(f"{path}: case {case_id} secrets must be an object")
    elif secrets:
        invalid = {str(item) for item in _as_list(secrets.get("forbidden_types"))} - VALID_SECRET_KINDS
        if invalid:
            errors.append(f"{path}: case {case_id} secrets.forbidden_types has invalid values {sorted(invalid)}")

    limits = expect.get("limits") or {}
    if limits and not isinstance(limits, dict):
        errors.append(f"{path}: case {case_id} limits must be an object")
    elif limits:
        for key, value in limits.items():
            try:
                float(value)
            except (TypeError, ValueError):
                errors.append(f"{path}: case {case_id} limits.{key} must be numeric")

    metrics = expect.get("metrics") or {}
    if metrics and not isinstance(metrics, dict):
        errors.append(f"{path}: case {case_id} metrics must be an object")
    elif metrics:
        for bound in ("min", "max"):
            values = metrics.get(bound) or {}
            if not isinstance(values, dict):
                errors.append(f"{path}: case {case_id} metrics.{bound} must be an object")
                continue
            for key, value in values.items():
                try:
                    float(value)
                except (TypeError, ValueError):
                    errors.append(f"{path}: case {case_id} metrics.{bound}.{key} must be numeric")

    business = expect.get("business_metrics") or {}
    if business and not isinstance(business, dict):
        errors.append(f"{path}: case {case_id} business_metrics must be an object")
    return errors
