from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def agentops_dir(root: str | Path) -> Path:
    return Path(root).resolve() / ".agentops"


def results_dir(root: str | Path) -> Path:
    return agentops_dir(root) / "results"


def baselines_dir(root: str | Path) -> Path:
    return agentops_dir(root) / "baselines"


def load_latest(root: str | Path) -> dict[str, Any]:
    latest = agentops_dir(root) / "latest-run.json"
    if not latest.exists():
        raise FileNotFoundError(f"No latest run found at {latest}")
    return json.loads(latest.read_text(encoding="utf-8"))


def list_runs(root: str | Path) -> list[dict[str, Any]]:
    runs = []
    base = results_dir(root)
    if not base.exists():
        return runs
    for run_file in sorted(base.glob("*/run.json"), reverse=True):
        try:
            runs.append(json.loads(run_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return runs


def save_baseline(root: str | Path, name: str = "main") -> Path:
    latest = load_latest(root)
    out_dir = baselines_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name}.json"
    out.write_text(json.dumps(latest, indent=2), encoding="utf-8")
    return out


def load_baseline(root: str | Path, name: str = "main") -> dict[str, Any]:
    path = baselines_dir(root) / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"No baseline named {name!r} at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def compare_latest_to_baseline(root: str | Path, name: str = "main") -> dict[str, Any]:
    latest = load_latest(root)
    baseline = load_baseline(root, name)
    delta = float(latest.get("score", 0)) - float(baseline.get("score", 0))
    latest_cases = {
        f"{case.get('agent')}::{case.get('suite')}::{case.get('id')}": case
        for case in latest.get("cases", [])
    }
    baseline_cases = {
        f"{case.get('agent')}::{case.get('suite')}::{case.get('id')}": case
        for case in baseline.get("cases", [])
    }
    new_failures = [
        case_id
        for case_id, case in latest_cases.items()
        if not case.get("passed") and baseline_cases.get(case_id, {}).get("passed", True)
    ]
    resolved_failures = [
        case_id
        for case_id, case in latest_cases.items()
        if case.get("passed") and not baseline_cases.get(case_id, {}).get("passed", True)
    ]
    latest_metrics = latest.get("metrics") or {}
    baseline_metrics = baseline.get("metrics") or {}
    metric_delta = {}
    for key in sorted(set(latest_metrics) | set(baseline_metrics)):
        latest_value = latest_metrics.get(key)
        baseline_value = baseline_metrics.get(key)
        if isinstance(latest_value, (int, float)) and isinstance(baseline_value, (int, float)):
            metric_delta[key] = latest_value - baseline_value
    return {
        "baseline": name,
        "latest_run": latest.get("run_id"),
        "baseline_run": baseline.get("run_id"),
        "latest_score": latest.get("score"),
        "baseline_score": baseline.get("score"),
        "delta": delta,
        "new_failures": new_failures,
        "resolved_failures": resolved_failures,
        "metric_delta": metric_delta,
        "regressed": delta < 0 or bool(new_failures),
    }


def copy_report_artifacts(root: str | Path, destination: str | Path) -> Path:
    latest = load_latest(root)
    src = Path(latest["results_dir"])
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    for name in ["run.json", "gate.json", "metrics.json", "trace.jsonl", "report.md", "report.html", "junit.xml"]:
        path = src / name
        if path.exists():
            shutil.copy2(path, dest / name)
    return dest
