from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from typing import Any


def render_markdown_report(run: dict[str, Any]) -> str:
    status = "PASS" if run["passed"] else "FAIL"
    lines = [
        f"# AgentOps Gate: {status}",
        "",
        f"- Run: `{run['run_id']}`",
        f"- Environment: `{run['environment']}`",
        f"- Score: `{run['score']:.2f}` / required `{run['min_score']:.2f}`",
        "",
    ]
    if run.get("blocking"):
        lines.extend(["## Blocking Issues", ""])
        if run.get("blocking_summary"):
            lines.append("Summary:")
            for category, count in sorted(run["blocking_summary"].items()):
                lines.append(f"- `{category}`: `{count}`")
            lines.append("")
        for issue in run["blocking"]:
            lines.append(f"- {issue}")
        lines.append("")
    lines.extend(["## Root Cause Suggestions", ""])
    if run.get("root_causes"):
        for item in run["root_causes"]:
            lines.append(f"- **{item.get('title')}**: {item.get('recommendation')}")
    else:
        lines.append("- None")
    lines.append("")
    if run.get("metrics"):
        metrics = run["metrics"]
        lines.extend(
            [
                "## Metrics",
                "",
                f"- Cases: `{metrics.get('cases_passed')}` passed / `{metrics.get('cases_total')}` total",
                f"- Tool calls: `{metrics.get('tool_calls_total')}`",
                f"- Approval requests: `{metrics.get('approval_requests')}`",
                f"- Policy violations: `{metrics.get('policy_violations')}`",
                f"- Security findings: `{metrics.get('security_findings')}`",
                f"- Max case duration: `{metrics.get('duration_ms_max')}` ms",
                "",
            ]
        )
    lines.extend(["## Cases", ""])
    for case in run.get("cases", []):
        lines.append(f"### {case.get('id')} - {'PASS' if case.get('passed') else 'FAIL'}")
        lines.append("")
        lines.append(f"Score: `{float(case.get('score', 0)):.2f}`")
        lines.append("")
        if case.get("metrics"):
            metrics = case["metrics"]
            lines.append(
                f"Case metrics: `{metrics.get('tool_calls')}` tool calls, "
                f"`{metrics.get('approval_requests')}` approvals, "
                f"`{metrics.get('duration_ms')}` ms"
            )
            lines.append("")
        if case.get("security_findings"):
            lines.append("Security findings:")
            for finding in case["security_findings"]:
                lines.append(f"- {finding.get('kind')} in {finding.get('source')}: `{finding.get('redacted')}`")
            lines.append("")
        if case.get("root_causes"):
            lines.append("Root cause suggestions:")
            for item in case["root_causes"]:
                lines.append(f"- {item.get('title')}: {item.get('recommendation')}")
            lines.append("")
        for check in case.get("checks", []):
            marker = "PASS" if check.get("passed") else "FAIL"
            lines.append(f"- {marker}: {check.get('name')}")
        lines.append("")
        lines.append("Output:")
        lines.append("")
        lines.append("```")
        lines.append(str(case.get("output") or ""))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def render_html_report(run: dict[str, Any]) -> str:
    status = "PASS" if run["passed"] else "FAIL"
    color = "#147d3f" if run["passed"] else "#b42318"
    case_blocks = []
    for case in run.get("cases", []):
        checks = "".join(
            f"<li class=\"{'pass' if check.get('passed') else 'fail'}\">"
            f"{html.escape('PASS' if check.get('passed') else 'FAIL')}: {html.escape(str(check.get('name')))}</li>"
            for check in case.get("checks", [])
        )
        root_causes = "".join(
            f"<li><strong>{html.escape(str(item.get('title')))}</strong>: "
            f"{html.escape(str(item.get('recommendation')))}</li>"
            for item in case.get("root_causes", [])
        )
        security_findings = "".join(
            f"<li>{html.escape(str(item.get('kind')))} in {html.escape(str(item.get('source')))}: "
            f"<code>{html.escape(str(item.get('redacted')))}</code></li>"
            for item in case.get("security_findings", [])
        )
        metrics = case.get("metrics") or {}
        case_blocks.append(
            "<section class=\"case\">"
            f"<h2>{html.escape(str(case.get('id')))} - {'PASS' if case.get('passed') else 'FAIL'}</h2>"
            f"<p>Score: {float(case.get('score', 0)):.2f}</p>"
            f"<p>Metrics: {html.escape(str(metrics.get('tool_calls', 0)))} tool calls, "
            f"{html.escape(str(metrics.get('approval_requests', 0)))} approvals, "
            f"{html.escape(str(metrics.get('duration_ms', 0)))} ms</p>"
            f"<h3>Security Findings</h3><ul>{security_findings or '<li>None</li>'}</ul>"
            f"<h3>Root Cause Suggestions</h3><ul>{root_causes or '<li>None</li>'}</ul>"
            f"<ul>{checks}</ul>"
            f"<pre>{html.escape(str(case.get('output') or ''))}</pre>"
            "</section>"
        )
    blocking_summary = "".join(
        f"<li><code>{html.escape(str(category))}</code>: {html.escape(str(count))}</li>"
        for category, count in sorted((run.get("blocking_summary") or {}).items())
    )
    blocking = "".join(f"<li>{html.escape(str(item))}</li>" for item in run.get("blocking", []))
    root_causes = "".join(
        f"<li><strong>{html.escape(str(item.get('title')))}</strong>: {html.escape(str(item.get('recommendation')))}</li>"
        for item in run.get("root_causes", [])
    )
    metrics = run.get("metrics") or {}
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>AgentOps Gate {status}</title>
  <style>
    body {{ font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif; margin: 32px; color: #172033; }}
    .status {{ color: {color}; }}
    .summary, .case {{ border: 1px solid #d9dee8; border-radius: 8px; padding: 16px; margin: 16px 0; }}
    .pass {{ color: #147d3f; }}
    .fail {{ color: #b42318; }}
    pre {{ background: #f6f8fb; padding: 12px; border-radius: 6px; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1 class="status">AgentOps Gate: {status}</h1>
  <section class="summary">
    <p><strong>Run:</strong> {html.escape(str(run['run_id']))}</p>
    <p><strong>Environment:</strong> {html.escape(str(run['environment']))}</p>
    <p><strong>Score:</strong> {float(run['score']):.2f} / required {float(run['min_score']):.2f}</p>
    <p><strong>Cases:</strong> {html.escape(str(metrics.get('cases_passed', 0)))} / {html.escape(str(metrics.get('cases_total', 0)))} passed</p>
    <p><strong>Tool calls:</strong> {html.escape(str(metrics.get('tool_calls_total', 0)))}, <strong>Security findings:</strong> {html.escape(str(metrics.get('security_findings', 0)))}</p>
  </section>
  <h2>Blocking Issues</h2>
  <h3>Summary</h3>
  <ul>{blocking_summary or '<li>None</li>'}</ul>
  <ul>{blocking or '<li>None</li>'}</ul>
  <h2>Root Cause Suggestions</h2>
  <ul>{root_causes or '<li>None</li>'}</ul>
  {''.join(case_blocks)}
</body>
</html>
"""


def render_junit_report(run: dict[str, Any]) -> str:
    suite = ET.Element(
        "testsuite",
        {
            "name": "open-agentops",
            "tests": str(len(run.get("cases", []))),
            "failures": str(sum(1 for case in run.get("cases", []) if not case.get("passed"))),
        },
    )
    for case in run.get("cases", []):
        test = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": str(case.get("agent") or "agent"),
                "name": str(case.get("id") or "case"),
            },
        )
        if not case.get("passed"):
            failure = ET.SubElement(test, "failure", {"message": "Agent scenario test failed"})
            root_causes = [
                f"{item.get('title')}: {item.get('recommendation')}"
                for item in case.get("root_causes", [])
            ]
            failure.text = (
                "\n".join(str(item) for item in case.get("blocking", []))
                + ("\n\nRoot causes:\n" + "\n".join(root_causes) if root_causes else "")
            ) or str(case.get("checks", []))
    return ET.tostring(suite, encoding="unicode")
