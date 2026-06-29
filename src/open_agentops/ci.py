from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .eval_runner import load_latest_gate


def _top_failed_cases(result: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    failed = [case for case in result.get("cases", []) if not case.get("passed")]
    return sorted(failed, key=lambda case: float(case.get("score", 0)))[:limit]


def render_markdown_annotation(result: dict[str, Any], *, max_cases: int = 5) -> str:
    status = "PASS" if result.get("passed") else "FAIL"
    lines = [
        f"## Open AgentOps Gate: {status}",
        "",
        f"- Run: `{result.get('run_id')}`",
        f"- Score: `{float(result.get('score', 0)):.2f}` / required `{float(result.get('min_score', 0)):.2f}`",
        f"- Results: `{result.get('results_dir')}`",
        "",
    ]
    metrics = result.get("metrics") or {}
    if metrics:
        lines.extend(
            [
                "### Metrics",
                "",
                f"- Cases: `{metrics.get('cases_passed')}` passed / `{metrics.get('cases_total')}` total",
                f"- Tool calls: `{metrics.get('tool_calls_total')}`",
                f"- Policy violations: `{metrics.get('policy_violations')}`",
                f"- Security findings: `{metrics.get('security_findings')}`",
                "",
            ]
        )
    if result.get("blocking_summary"):
        lines.extend(["### Blocking Summary", ""])
        for category, count in sorted(result["blocking_summary"].items()):
            lines.append(f"- `{category}`: `{count}`")
        lines.append("")
    failed_cases = _top_failed_cases(result, max_cases)
    if failed_cases:
        lines.extend([f"### Top {len(failed_cases)} Failed Cases", ""])
        for case in failed_cases:
            lines.append(f"- `{case.get('agent')}::{case.get('id')}` score `{float(case.get('score', 0)):.2f}`")
            for issue in (case.get("blocking") or [])[:3]:
                lines.append(f"  - {issue}")
        lines.append("")
    if result.get("root_causes"):
        lines.extend(["### Root Cause Suggestions", ""])
        for item in result["root_causes"]:
            lines.append(f"- **{item.get('title')}**: {item.get('recommendation')}")
        lines.append("")
    lines.extend(
        [
            "### Artifacts",
            "",
            "- `report.html`",
            "- `report.md`",
            "- `junit.xml`",
            "- `run.json`",
            "- `trace.jsonl`",
            "",
        ]
    )
    return "\n".join(lines)


def render_ci_step_summary(result: dict[str, Any], *, max_cases: int = 5) -> str:
    return render_markdown_annotation(result, max_cases=max_cases)


def write_annotation(
    config_path: str | Path,
    output_path: str | Path | None = None,
    *,
    fmt: str = "markdown",
    max_cases: int = 5,
) -> str:
    result = load_latest_gate(config_path)
    if fmt == "json":
        content = json.dumps(result, indent=2)
    elif fmt in {"markdown", "ci"}:
        content = render_markdown_annotation(result, max_cases=max_cases)
    else:
        raise ValueError(f"unsupported annotation format {fmt!r}")
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
    return content
