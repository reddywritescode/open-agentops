from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .result_store import list_runs


def _page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif; margin: 32px; color: #172033; }}
    a {{ color: #5146d8; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border-bottom: 1px solid #d9dee8; text-align: left; padding: 10px; }}
    .pass {{ color: #147d3f; font-weight: 700; }}
    .fail {{ color: #b42318; font-weight: 700; }}
    pre {{ background: #f6f8fb; padding: 12px; border-radius: 6px; white-space: pre-wrap; }}
  </style>
</head>
<body>
{body}
</body>
</html>""".encode("utf-8")


class AgentOpsHandler(BaseHTTPRequestHandler):
    root: Path

    def _send(self, body: bytes, content_type: str = "text/html", status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/runs":
            body = json.dumps(list_runs(self.root), indent=2).encode("utf-8")
            self._send(body, "application/json")
            return
        if parsed.path == "/run":
            run_id = parse_qs(parsed.query).get("id", [""])[0]
            self._send(self._render_run(run_id))
            return
        self._send(self._render_index())

    def _render_index(self) -> bytes:
        rows = []
        for run in list_runs(self.root):
            status = "PASS" if run.get("passed") else "FAIL"
            cls = "pass" if run.get("passed") else "fail"
            rows.append(
                "<tr>"
                f"<td><a href=\"/run?id={html.escape(str(run.get('run_id')))}\">{html.escape(str(run.get('run_id')))}</a></td>"
                f"<td class=\"{cls}\">{status}</td>"
                f"<td>{float(run.get('score', 0)):.2f}</td>"
                f"<td>{html.escape(str(run.get('environment')))}</td>"
                f"<td>{html.escape(', '.join(a.get('agent', '') for a in run.get('agents', [])))}</td>"
                "</tr>"
            )
        table_rows = "".join(rows) or '<tr><td colspan="5">No runs yet</td></tr>'
        body = (
            "<h1>Open AgentOps Runs</h1>"
            f"<p>Root: <code>{html.escape(str(self.root))}</code></p>"
            "<table><thead><tr><th>Run</th><th>Gate</th><th>Score</th><th>Env</th><th>Agents</th></tr></thead>"
            f"<tbody>{table_rows}</tbody></table>"
        )
        return _page("Open AgentOps", body)

    def _render_run(self, run_id: str) -> bytes:
        for run in list_runs(self.root):
            if run.get("run_id") == run_id:
                body = [
                    f"<p><a href=\"/\">Back</a></p><h1>Run {html.escape(run_id)}</h1>",
                    f"<p>Gate: <span class=\"{'pass' if run.get('passed') else 'fail'}\">{'PASS' if run.get('passed') else 'FAIL'}</span></p>",
                    f"<p>Score: {float(run.get('score', 0)):.2f} / {float(run.get('min_score', 0)):.2f}</p>",
                ]
                if run.get("blocking"):
                    body.append("<h2>Blocking</h2><ul>")
                    body.extend(f"<li>{html.escape(str(item))}</li>" for item in run["blocking"])
                    body.append("</ul>")
                body.append("<h2>Cases</h2>")
                for case in run.get("cases", []):
                    body.append(
                        f"<h3>{html.escape(str(case.get('id')))} - {'PASS' if case.get('passed') else 'FAIL'}</h3>"
                        f"<pre>{html.escape(json.dumps(case, indent=2))}</pre>"
                    )
                return _page("Open AgentOps Run", "".join(body))
        return _page("Not Found", "<h1>Run not found</h1>")


def serve(root: str | Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    handler = type("ConfiguredAgentOpsHandler", (AgentOpsHandler,), {"root": Path(root).resolve()})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Open AgentOps server: http://{host}:{port}")
    print(f"Serving results from: {Path(root).resolve()}")
    server.serve_forever()
