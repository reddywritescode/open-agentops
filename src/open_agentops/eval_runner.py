from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import yaml

from .config import load_config, load_yaml, tool_policies
from .harness import normalize_suite
from .llm import llm_score
from .reports import render_html_report, render_junit_report, render_markdown_report
from .security import PII_KINDS, SECRET_KINDS, detect_sensitive_data
from .sdk import RunContext, reset_current_run, set_current_run
from .simulators import default_simulators


def import_entrypoint(entrypoint: str, cwd: Path) -> Callable[..., Any]:
    module_name, _, attr = entrypoint.partition(":")
    if not module_name or not attr:
        raise ValueError(f"Invalid entrypoint {entrypoint!r}; expected module:function")
    sys.path.insert(0, str(cwd))
    try:
        module = importlib.import_module(module_name)
        obj = module
        for part in attr.split("."):
            obj = getattr(obj, part)
        if not callable(obj):
            raise TypeError(f"{entrypoint} is not callable")
        return obj
    finally:
        try:
            sys.path.remove(str(cwd))
        except ValueError:
            pass


def run_command_agent(command: str, payload: dict[str, Any], cwd: Path) -> Any:
    proc = subprocess.run(
        command,
        input=json.dumps(payload),
        text=True,
        shell=True,
        cwd=str(cwd),
        capture_output=True,
        check=False,
    )
    output = proc.stdout.strip()
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"command failed with exit code {proc.returncode}")
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {"output": output}


def run_http_agent(url: str, payload: dict[str, Any]) -> Any:
    import urllib.request

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"output": body}


def resolve_agent_runner(agent: dict[str, Any], project_root: Path) -> Callable[[dict[str, Any]], Any]:
    runner = str(agent.get("runner") or "entrypoint")
    if runner == "command":
        command = str(agent.get("command") or "")
        if not command:
            raise ValueError("command runner requires command")
        return lambda payload: run_command_agent(command, payload, project_root)
    if runner == "http":
        url = str(agent.get("url") or "")
        if not url:
            raise ValueError("http runner requires url")
        return lambda payload: run_http_agent(url, payload)
    entrypoint = agent.get("entrypoint")
    if not entrypoint:
        raise ValueError("entrypoint runner requires entrypoint")
    return import_entrypoint(str(entrypoint), project_root)


def _events_by_type(events: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [event for event in events if event.get("type") == event_type]


def _tool_names(events: list[dict[str, Any]]) -> list[str]:
    return [str(event.get("tool")) for event in _events_by_type(events, "tool_call")]


def _tool_events(events: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [event for event in _events_by_type(events, "tool_call") if event.get("tool") == name]


def _contains_in_json(value: Any, needle: str) -> bool:
    return needle.lower() in json.dumps(value, sort_keys=True).lower()


def _final_output(result: Any) -> str:
    if isinstance(result, dict):
        return str(result.get("output") or result.get("final") or result)
    return str(result)


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def _scope_payloads(output: str, events: list[dict[str, Any]], scopes: list[str]) -> list[tuple[str, str]]:
    payloads: list[tuple[str, str]] = []
    if "final_answer" in scopes:
        payloads.append(("final_answer", output))
    if "tool_args" in scopes:
        payloads.extend((f"tool_args:{event.get('tool')}", _safe_json(event.get("args"))) for event in _events_by_type(events, "tool_call"))
    if "tool_results" in scopes:
        payloads.extend(
            (f"tool_result:{event.get('tool')}", _safe_json(event.get("result")))
            for event in _events_by_type(events, "tool_result")
        )
    if "simulator_state" in scopes:
        payloads.extend(("simulator_state", _safe_json(event.get("state"))) for event in _events_by_type(events, "simulator_state"))
    if "all_events" in scopes:
        payloads.append(("all_events", _safe_json(events)))
    return payloads


def _expand_kinds(value: Any, universe: set[str]) -> set[str]:
    if value is True:
        return set(universe)
    if value in (False, None):
        return set()
    requested = {str(item) for item in (value if isinstance(value, list) else [value])}
    if "all" in requested:
        return set(universe)
    return requested


def _case_metrics(events: list[dict[str, Any]], duration_ms: float, result: Any) -> dict[str, Any]:
    tool_calls = _events_by_type(events, "tool_call")
    policy_violations = _events_by_type(events, "policy_violation")
    approvals = _events_by_type(events, "approval_request")
    metrics: dict[str, Any] = {
        "duration_ms": round(duration_ms, 3),
        "tool_calls": len(tool_calls),
        "live_tool_calls": sum(1 for event in tool_calls if event.get("mode") == "live"),
        "simulated_tool_calls": sum(1 for event in tool_calls if event.get("mode") in {"simulate", "sandbox"}),
        "blocked_tool_calls": sum(1 for event in tool_calls if event.get("mode") == "block"),
        "approval_requests": len(approvals),
        "policy_violations": len(policy_violations),
        "agent_errors": len(_events_by_type(events, "agent_error")),
    }
    for event in _events_by_type(events, "metric"):
        name = str(event.get("name") or event.get("metric") or "")
        value = event.get("value")
        if name and isinstance(value, (int, float)):
            metrics[name] = value
    if isinstance(result, dict) and isinstance(result.get("metrics"), dict):
        for name, value in result["metrics"].items():
            if isinstance(value, (int, float, str, bool)):
                metrics[str(name)] = value
    return metrics


def _nested_get(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _apply_metric_limits(
    expect: dict[str, Any],
    metrics: dict[str, Any],
    checks: list[dict[str, Any]],
    blocking: list[str],
) -> None:
    limits = expect.get("limits") or {}
    builtin_max = {
        "max_tool_calls": "tool_calls",
        "max_live_tool_calls": "live_tool_calls",
        "max_simulated_tool_calls": "simulated_tool_calls",
        "max_blocked_tool_calls": "blocked_tool_calls",
        "max_approval_requests": "approval_requests",
        "max_policy_violations": "policy_violations",
        "max_agent_errors": "agent_errors",
        "max_duration_ms": "duration_ms",
    }
    builtin_min = {
        "min_tool_calls": "tool_calls",
        "min_approval_requests": "approval_requests",
    }
    for limit_name, metric_name in builtin_max.items():
        if limit_name not in limits:
            continue
        threshold = float(limits[limit_name])
        actual = float(metrics.get(metric_name, 0))
        passed = actual <= threshold
        checks.append({"name": f"limit:{limit_name}", "passed": passed, "actual": actual, "expected_max": threshold})
        if not passed:
            blocking.append(f"limit exceeded: {metric_name}={actual:g} > {threshold:g}")
    for limit_name, metric_name in builtin_min.items():
        if limit_name not in limits:
            continue
        threshold = float(limits[limit_name])
        actual = float(metrics.get(metric_name, 0))
        passed = actual >= threshold
        checks.append({"name": f"limit:{limit_name}", "passed": passed, "actual": actual, "expected_min": threshold})
        if not passed:
            blocking.append(f"limit missed: {metric_name}={actual:g} < {threshold:g}")

    metric_expectations = expect.get("metrics") or {}
    for metric_name, threshold in (metric_expectations.get("max") or {}).items():
        actual = metrics.get(metric_name)
        passed = isinstance(actual, (int, float)) and float(actual) <= float(threshold)
        checks.append({"name": f"metric_max:{metric_name}", "passed": passed, "actual": actual, "expected_max": threshold})
        if not passed:
            blocking.append(f"metric max failed: {metric_name}={actual} > {threshold}")
    for metric_name, threshold in (metric_expectations.get("min") or {}).items():
        actual = metrics.get(metric_name)
        passed = isinstance(actual, (int, float)) and float(actual) >= float(threshold)
        checks.append({"name": f"metric_min:{metric_name}", "passed": passed, "actual": actual, "expected_min": threshold})
        if not passed:
            blocking.append(f"metric min failed: {metric_name}={actual} < {threshold}")


def _apply_business_metrics(
    expect: dict[str, Any],
    result: Any,
    checks: list[dict[str, Any]],
    blocking: list[str],
) -> None:
    expected = expect.get("business_metrics") or {}
    if not expected:
        return
    actual_metrics = result.get("business_metrics") if isinstance(result, dict) else None
    if not isinstance(actual_metrics, dict):
        actual_metrics = result.get("metrics") if isinstance(result, dict) and isinstance(result.get("metrics"), dict) else {}
    for path, expected_value in expected.items():
        actual_value = _nested_get(actual_metrics, str(path))
        passed = actual_value == expected_value
        checks.append(
            {
                "name": f"business_metric:{path}",
                "passed": passed,
                "actual": actual_value,
                "expected": expected_value,
            }
        )
        if not passed:
            blocking.append(f"business metric failed: {path} expected {expected_value!r}, got {actual_value!r}")


def _apply_sensitive_data_checks(
    expect: dict[str, Any],
    output: str,
    events: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    blocking: list[str],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    privacy = expect.get("privacy") or {}
    secrets = expect.get("secrets") or {}

    forbidden_pii = _expand_kinds(privacy.get("forbidden_pii") or privacy.get("forbidden"), PII_KINDS)
    allowed_pii = _expand_kinds(privacy.get("allowed_pii"), PII_KINDS)
    if forbidden_pii:
        scopes = [str(item) for item in (privacy.get("inspect") or ["final_answer", "tool_args"])]
        scoped_findings = [
            finding
            for source, text in _scope_payloads(output, events, scopes)
            for finding in detect_sensitive_data(text, source=source)
            if finding["category"] == "pii" and finding["kind"] in forbidden_pii and finding["kind"] not in allowed_pii
        ]
        findings.extend(scoped_findings)
        passed = not scoped_findings
        checks.append({"name": "privacy:no_forbidden_pii", "passed": passed, "findings": scoped_findings})
        if not passed:
            for finding in scoped_findings:
                blocking.append(f"privacy leak: {finding['kind']} in {finding['source']}")

    forbidden_secret_kinds = _expand_kinds(secrets.get("forbidden_types") or secrets.get("forbidden"), SECRET_KINDS)
    if forbidden_secret_kinds:
        scopes = [str(item) for item in (secrets.get("inspect") or ["final_answer", "tool_args", "tool_results"])]
        scoped_findings = [
            finding
            for source, text in _scope_payloads(output, events, scopes)
            for finding in detect_sensitive_data(text, source=source)
            if finding["category"] == "secret" and finding["kind"] in forbidden_secret_kinds
        ]
        findings.extend(scoped_findings)
        passed = not scoped_findings
        checks.append({"name": "secrets:no_secret_leak", "passed": passed, "findings": scoped_findings})
        if not passed:
            for finding in scoped_findings:
                blocking.append(f"secret leak: {finding['kind']} in {finding['source']}")
    return findings


def _root_cause_suggestions(blocking: list[str], checks: list[dict[str, Any]]) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []

    def add(title: str, recommendation: str) -> None:
        if any(item["title"] == title for item in suggestions):
            return
        suggestions.append({"title": title, "recommendation": recommendation})

    for issue in blocking:
        if "forbidden tool called" in issue or "blocked_tool_called" in issue:
            add("Mutation policy violation", "Route mutating tools through simulate, sandbox, approval_required, or block in CI.")
        elif "approval not requested" in issue:
            add("Missing human approval", "Add an approval tool call before destructive or externally visible actions.")
        elif "privacy leak" in issue:
            add("Sensitive data leak", "Redact PII before final answers and before sending text to external tools.")
        elif "secret leak" in issue:
            add("Secret exposure", "Do not echo credentials or pass them to tools; replace them with redacted placeholders.")
        elif "limit exceeded" in issue or "metric max failed" in issue:
            add("Budget or latency regression", "Reduce tool loops, add early exits, or raise the budget only after review.")
        elif "business metric failed" in issue:
            add("Business outcome mismatch", "Return and validate explicit business_metrics for the domain outcome.")
        elif "forbidden output text" in issue:
            add("Unsafe final answer", "Make final answers reflect what the tool trace actually did, especially blocked or approval-only actions.")
        elif "tool " in issue and "expected mode" in issue:
            add("Tool policy mismatch", "Fix agentops.yml so the tool runs in the expected mode for this environment.")
        elif "policy violation" in issue:
            add("Policy violation", "Review the trace and tighten the tool policy or agent decision logic.")

    for check in checks:
        if check.get("passed"):
            continue
        name = str(check.get("name") or "")
        if name.startswith("output_contains"):
            add("Missing required answer evidence", "Update the agent response to include the expected business outcome.")
        elif name.startswith("simulator_contains"):
            add("Simulator state mismatch", "Verify the simulator adapter captured the expected resource mutation.")
        elif name.startswith("metric_"):
            add("Metric threshold mismatch", "Emit the expected metric and keep it inside the configured threshold.")
    return suggestions


def summarize_blocking(blocking: list[str]) -> dict[str, int]:
    summary = {
        "forbidden_tool": 0,
        "missing_approval": 0,
        "tool_mode": 0,
        "forbidden_output": 0,
        "limit": 0,
        "metric": 0,
        "business_metric": 0,
        "privacy_leak": 0,
        "secret_leak": 0,
        "policy_violation": 0,
        "other": 0,
    }
    for issue in blocking:
        if "forbidden tool called" in issue:
            summary["forbidden_tool"] += 1
        elif "approval not requested" in issue:
            summary["missing_approval"] += 1
        elif "expected mode" in issue:
            summary["tool_mode"] += 1
        elif "forbidden output text" in issue:
            summary["forbidden_output"] += 1
        elif issue.startswith("limit "):
            summary["limit"] += 1
        elif issue.startswith("metric "):
            summary["metric"] += 1
        elif issue.startswith("business metric failed"):
            summary["business_metric"] += 1
        elif issue.startswith("privacy leak"):
            summary["privacy_leak"] += 1
        elif issue.startswith("secret leak"):
            summary["secret_leak"] += 1
        elif "policy violation" in issue or issue == "blocked_tool_called":
            summary["policy_violation"] += 1
        else:
            summary["other"] += 1
    return {key: value for key, value in summary.items() if value}


def grade_case(case: dict[str, Any], result: Any, events: list[dict[str, Any]], *, duration_ms: float = 0.0) -> dict[str, Any]:
    expect = case.get("expect") or {}
    checks: list[dict[str, Any]] = []
    blocking: list[str] = []
    tools = _tool_names(events)
    output = _final_output(result)
    metrics = _case_metrics(events, duration_ms, result)

    for name in expect.get("tools_called") or []:
        passed = name in tools
        checks.append({"name": f"tool_called:{name}", "passed": passed})

    for name in expect.get("tools_not_called") or []:
        passed = name not in tools
        checks.append({"name": f"tool_not_called:{name}", "passed": passed})
        if not passed:
            blocking.append(f"forbidden tool called: {name}")

    approvals = {event.get("tool") for event in _events_by_type(events, "approval_request")}
    for name in expect.get("approval_required_for") or []:
        passed = name in approvals
        checks.append({"name": f"approval_requested:{name}", "passed": passed})
        if not passed:
            blocking.append(f"approval not requested: {name}")

    for name, expected_mode in (expect.get("tool_modes") or {}).items():
        matching = _tool_events(events, name)
        passed = any(event.get("mode") == expected_mode for event in matching)
        checks.append({"name": f"tool_mode:{name}:{expected_mode}", "passed": passed})
        if not passed:
            blocking.append(f"tool {name} did not run in expected mode {expected_mode}")

    simulator_states = [event.get("state") for event in _events_by_type(events, "simulator_state")]
    for requirement in expect.get("simulator_contains") or []:
        simulator = requirement.get("simulator")
        text = str(requirement.get("text") or "")
        passed = any(
            simulator in state and _contains_in_json(state.get(simulator), text)
            for state in simulator_states
            if isinstance(state, dict)
        )
        checks.append({"name": f"simulator_contains:{simulator}:{text}", "passed": passed})

    final = expect.get("final_answer") or {}
    for text in final.get("contains") or []:
        passed = str(text).lower() in output.lower()
        checks.append({"name": f"output_contains:{text}", "passed": passed})
    for text in final.get("must_not_contain") or []:
        passed = str(text).lower() not in output.lower()
        checks.append({"name": f"output_not_contains:{text}", "passed": passed})
        if not passed:
            blocking.append(f"forbidden output text: {text}")

    _apply_metric_limits(expect, metrics, checks, blocking)
    _apply_business_metrics(expect, result, checks, blocking)
    security_findings = _apply_sensitive_data_checks(expect, output, events, checks, blocking)

    for event in _events_by_type(events, "policy_violation"):
        blocking.append(str(event.get("reason") or "policy violation"))

    llm_results = []
    for judge in case.get("judges") or []:
        if judge.get("type") == "llm":
            min_score = float(judge.get("min_score", 0.8))
            try:
                score, reason = llm_score(str(judge.get("rubric") or ""), output, model=judge.get("model"))
                passed = score >= min_score
                llm_results.append({"score": score, "reason": reason, "passed": passed, "model": judge.get("model")})
                checks.append(
                    {
                        "name": "llm_judge",
                        "check_type": "judge_based",
                        "passed": passed,
                        "score": score,
                        "reason": reason,
                        "model": judge.get("model"),
                    }
                )
            except Exception as exc:
                checks.append({"name": "llm_judge", "check_type": "judge_based", "passed": False, "error": str(exc)})

    for check in checks:
        check.setdefault("check_type", "deterministic")
    passed_count = sum(1 for check in checks if check.get("passed"))
    score = passed_count / len(checks) if checks else 1.0
    passed = score >= 1.0 and not blocking
    root_causes = _root_cause_suggestions(blocking, checks)
    return {
        "id": case.get("id"),
        "passed": passed,
        "score": score,
        "checks": checks,
        "blocking": blocking,
        "output": output,
        "llm_results": llm_results,
        "metrics": metrics,
        "security_findings": security_findings,
        "root_causes": root_causes,
    }


def collect_metrics(events: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    tool_calls = _events_by_type(events, "tool_call")
    tool_results = _events_by_type(events, "tool_result")
    durations = [float(case.get("metrics", {}).get("duration_ms", 0)) for case in cases]
    return {
        "cases_total": len(cases),
        "cases_passed": sum(1 for case in cases if case.get("passed")),
        "cases_failed": sum(1 for case in cases if not case.get("passed")),
        "tool_calls_total": len(tool_calls),
        "tool_calls_by_mode": {
            mode: sum(1 for event in tool_calls if event.get("mode") == mode)
            for mode in ["live", "simulate", "sandbox", "approval_required", "block"]
        },
        "tool_results_by_status": {
            status: sum(1 for event in tool_results if event.get("status") == status)
            for status in ["live", "simulated", "blocked", "approval_required"]
        },
        "approval_requests": len(_events_by_type(events, "approval_request")),
        "policy_violations": len(_events_by_type(events, "policy_violation")),
        "agent_errors": len(_events_by_type(events, "agent_error")),
        "duration_ms_total": round(sum(durations), 3),
        "duration_ms_max": round(max(durations), 3) if durations else 0,
        "security_findings": sum(len(case.get("security_findings", [])) for case in cases),
        "blocking_total": sum(len(case.get("blocking", [])) for case in cases),
        "root_cause_total": sum(len(case.get("root_causes", [])) for case in cases),
    }


def _dedupe_root_causes(cases: list[dict[str, Any]]) -> list[dict[str, str]]:
    root_causes: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for case in cases:
        for item in case.get("root_causes", []):
            key = (str(item.get("title") or ""), str(item.get("recommendation") or ""))
            if key in seen:
                continue
            seen.add(key)
            root_causes.append({"title": key[0], "recommendation": key[1]})
    return root_causes


def run_eval(config_path: str | Path, *, environment: str = "ci") -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    project_root = config_path.parent
    config = load_config(config_path)
    policies = tool_policies(config)
    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    results_dir = project_root / ".agentops" / "results" / run_id
    results_dir.mkdir(parents=True, exist_ok=True)

    all_case_results: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []
    agent_summaries: list[dict[str, Any]] = []

    for agent_id, agent in (config.get("agents") or {}).items():
        agent_fn = resolve_agent_runner(agent, project_root)
        suites = agent.get("test_suites") or agent.get("eval_suites") or []
        for suite_path in suites:
            suite_file = (project_root / suite_path).resolve()
            suite = normalize_suite(load_yaml(suite_file), source=suite_file)
            for case in suite.get("cases") or []:
                simulators = default_simulators(config)
                ctx = RunContext(environment=environment, tool_policies=policies, simulators=simulators)
                token = set_current_run(ctx)
                result: Any = None
                error: str | None = None
                started = time.perf_counter()
                try:
                    result = agent_fn(case.get("input") or {})
                except Exception as exc:
                    error = str(exc)
                    ctx.event("agent_error", error=error)
                finally:
                    duration_ms = (time.perf_counter() - started) * 1000
                    reset_current_run(token)

                simulator_state = {
                    name: sim.state() for name, sim in simulators.items() if hasattr(sim, "state")
                }
                ctx.event("simulator_state", state=simulator_state)
                case_result = grade_case(
                    case,
                    result if error is None else {"output": error},
                    ctx.events,
                    duration_ms=duration_ms,
                )
                case_result["agent"] = agent_id
                case_result["suite"] = suite.get("suite") or str(suite_file)
                case_result["error"] = error
                all_case_results.append(case_result)
                all_events.extend(ctx.events)

        agent_summaries.append(
            {
                "agent": agent_id,
                "entrypoint": agent.get("entrypoint"),
                "runner": agent.get("runner") or "entrypoint",
            }
        )

    suite_score = (
        sum(float(item["score"]) for item in all_case_results) / len(all_case_results)
        if all_case_results
        else 0.0
    )
    gate = config.get("gate") or {}
    agent_gates = [agent.get("gate") or {} for agent in (config.get("agents") or {}).values()]
    min_score = float(gate.get("min_score") or (agent_gates[0].get("min_score") if agent_gates else 1.0) or 1.0)
    blocking = [issue for item in all_case_results for issue in item.get("blocking", [])]
    blocking_summary = summarize_blocking(blocking)
    root_causes = _dedupe_root_causes(all_case_results)
    passed = suite_score >= min_score and not blocking and all(item["passed"] for item in all_case_results)
    metrics = collect_metrics(all_events, all_case_results)
    output = {
        "run_id": run_id,
        "config": str(config_path),
        "environment": environment,
        "agents": agent_summaries,
        "score": suite_score,
        "min_score": min_score,
        "passed": passed,
        "blocking": blocking,
        "blocking_summary": blocking_summary,
        "root_causes": root_causes,
        "cases": all_case_results,
        "metrics": metrics,
        "results_dir": str(results_dir),
    }

    (results_dir / "run.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    with (results_dir / "trace.jsonl").open("w", encoding="utf-8") as fh:
        for event in all_events:
            fh.write(json.dumps(event) + "\n")
    (results_dir / "gate.json").write_text(
        json.dumps(
            {
                "passed": passed,
                "score": suite_score,
                "blocking": blocking,
                "blocking_summary": blocking_summary,
                "root_causes": root_causes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (results_dir / "report.md").write_text(render_markdown_report(output), encoding="utf-8")
    (results_dir / "report.html").write_text(render_html_report(output), encoding="utf-8")
    (results_dir / "junit.xml").write_text(render_junit_report(output), encoding="utf-8")
    latest = project_root / ".agentops" / "latest-run.json"
    latest.parent.mkdir(exist_ok=True)
    latest.write_text(json.dumps(output, indent=2), encoding="utf-8")
    latest_by_config = project_root / ".agentops" / "latest" / f"{config_path.stem}.json"
    latest_by_config.parent.mkdir(parents=True, exist_ok=True)
    latest_by_config.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output

def load_latest_gate(config_path: str | Path) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    latest = config_path.parent / ".agentops" / "latest" / f"{config_path.stem}.json"
    if not latest.exists():
        latest = config_path.parent / ".agentops" / "latest-run.json"
    if not latest.exists():
        raise FileNotFoundError(f"No latest run found at {latest}; run test run first")
    return json.loads(latest.read_text(encoding="utf-8"))
