from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ci import write_annotation
from .datasets import coverage_report, init_dataset, list_dataset, promote_scenario, validate_dataset
from .eval_runner import load_latest_gate, run_eval
from .generator import generate_config, generate_starter_eval
from .harness import append_test_case, build_test_case, new_scenario, slugify, write_scenario
from .result_store import compare_latest_to_baseline, copy_report_artifacts, list_runs, save_baseline
from .scanner import scan_repo
from .scenario_generator import generate_scenario_files
from .server import serve
from .traces import import_trace, scenario_from_trace
from .universal import generate_policy_yaml
from .validator import validate_config


def cmd_scan(args: argparse.Namespace) -> int:
    result = scan_repo(args.path)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Root: {result['root']}")
        print(f"Python files: {result['python_files']}")
        print(f"Findings: {result['summary']['total_findings']}")
        print(f"Risky: {result['summary']['risky']}")
        print(f"Unknown: {result['summary']['unknown']}")
        for item in result["tools_or_risks"]:
            print(f"- {item['classification']}: {item['function']} ({item['file']})")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    errors = validate_config(args.config)
    if errors:
        print("Config validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Config validation: PASS")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    content = generate_starter_eval(args.path, args.agent)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"Wrote {out}")
    else:
        print(content)
    return 0


def cmd_generate_simulators(args: argparse.Namespace) -> int:
    content = generate_policy_yaml(args.manifest)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"Wrote {out}")
    else:
        print(content)
    return 0


def cmd_generate_scenarios(args: argparse.Namespace) -> int:
    paths = generate_scenario_files(
        args.config,
        agent_id=args.agent,
        provider=args.provider,
        model=args.model,
        output_dir=args.output_dir,
        force=args.force,
        print_prompt=args.print_prompt,
    )
    for path in paths:
        print(f"Wrote {path}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.path)
    config_path = root / "agentops.yml"
    eval_path = root / "tests" / f"{args.agent}.generated.yml"
    if config_path.exists() and not args.force:
        raise FileExistsError(f"{config_path} already exists; pass --force to overwrite")
    config_path.write_text(generate_config(root, args.agent, args.entrypoint), encoding="utf-8")
    eval_path.parent.mkdir(parents=True, exist_ok=True)
    eval_path.write_text(generate_starter_eval(root, args.agent), encoding="utf-8")
    print(f"Wrote {config_path}")
    print(f"Wrote {eval_path}")
    return 0


def cmd_scenario_create(args: argparse.Namespace) -> int:
    scenario_id = slugify(args.name)
    out = Path(args.output) if args.output else Path("tests") / f"{scenario_id}.yml"
    scenario = new_scenario(args.agent, scenario_id, description=args.description or "")
    path = write_scenario(out, scenario, force=args.force)
    print(f"Wrote {path}")
    return 0


def cmd_scenario_from_trace(args: argparse.Namespace) -> int:
    path = scenario_from_trace(
        args.trace,
        args.output,
        agent_id=args.agent,
        config_path=args.config,
        force=args.force,
    )
    print(f"Wrote {path}")
    return 0


def cmd_case_add(args: argparse.Namespace) -> int:
    case_id = args.id or slugify(args.user[:48])
    case = build_test_case(
        case_id=case_id,
        user=args.user,
        contains=args.contains or [],
        must_not_contain=args.must_not_contain or [],
        tool_called=args.tool_called or [],
        tool_not_called=args.tool_not_called or [],
        approval_required_for=args.approval_required_for or [],
    )
    path = append_test_case(args.suite, case)
    print(f"Added test case {case_id!r} to {path}")
    return 0


def cmd_eval_run(args: argparse.Namespace) -> int:
    result = run_eval(args.config, environment=args.environment)
    print(f"Run: {result['run_id']}")
    print(f"Score: {result['score']:.2f} / required {result['min_score']:.2f}")
    print(f"Gate: {'PASS' if result['passed'] else 'FAIL'}")
    print(f"Results: {result['results_dir']}")
    return 0 if result["passed"] else 1


def cmd_gate(args: argparse.Namespace) -> int:
    result = load_latest_gate(args.config)
    print(f"Gate: {'PASS' if result['passed'] else 'FAIL'}")
    print(f"Score: {result['score']:.2f} / required {result['min_score']:.2f}")
    if result.get("blocking_summary"):
        print("Blocking summary:")
        for category, count in sorted(result["blocking_summary"].items()):
            print(f"- {category}: {count}")
    if result.get("blocking"):
        print("Blocking:")
        max_items = int(getattr(args, "max_blocking", 50))
        for issue in result["blocking"][:max_items]:
            print(f"- {issue}")
        remaining = len(result["blocking"]) - max_items
        if remaining > 0:
            print(f"... {remaining} more blocking issues in run.json/report artifacts")
    if result.get("root_causes"):
        print("Root causes:")
        for item in result["root_causes"]:
            print(f"- {item.get('title')}: {item.get('recommendation')}")
    return 0 if result["passed"] else 1


def cmd_report(args: argparse.Namespace) -> int:
    result = load_latest_gate(args.config)
    report = Path(result["results_dir"]) / "report.md"
    print(report.read_text(encoding="utf-8"))
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    runs = list_runs(Path(args.config).resolve().parent)
    if args.json:
        print(json.dumps(runs, indent=2))
        return 0
    for run in runs[: args.limit]:
        status = "PASS" if run.get("passed") else "FAIL"
        print(f"{run.get('run_id')}  {status}  score={float(run.get('score', 0)):.2f}  env={run.get('environment')}")
    return 0


def cmd_baseline_save(args: argparse.Namespace) -> int:
    path = save_baseline(Path(args.config).resolve().parent, args.name)
    print(f"Saved baseline {args.name!r} to {path}")
    return 0


def cmd_baseline_compare(args: argparse.Namespace) -> int:
    result = compare_latest_to_baseline(Path(args.config).resolve().parent, args.name)
    print(json.dumps(result, indent=2))
    return 1 if result["regressed"] and args.fail_on_regression else 0


def cmd_export(args: argparse.Namespace) -> int:
    out = copy_report_artifacts(Path(args.config).resolve().parent, args.output)
    print(f"Exported latest artifacts to {out}")
    return 0


def cmd_traces_import(args: argparse.Namespace) -> int:
    path = import_trace(args.input, args.output, source_format=args.format)
    print(f"Wrote {path}")
    return 0


def cmd_dataset_init(args: argparse.Namespace) -> int:
    path = init_dataset(args.config, args.output, force=args.force)
    print(f"Wrote {path}")
    return 0


def cmd_dataset_list(args: argparse.Namespace) -> int:
    rows = list_dataset(args.dataset)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            print(f"{row.get('status', 'unknown'):10} {row.get('agent')} {row.get('path')}")
    return 0


def cmd_dataset_validate(args: argparse.Namespace) -> int:
    errors = validate_dataset(args.dataset)
    if errors:
        print("Dataset validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Dataset validation: PASS")
    return 0


def cmd_dataset_coverage(args: argparse.Namespace) -> int:
    report = coverage_report(args.dataset, config_path=args.config)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Scenarios: {report['scenarios_total']}")
        print(f"Generated: {report['generated']}")
        print(f"Review required: {report['review_required']}")
        print(f"Tools covered: {len(report['tools_covered'])} / {len(report['tools_expected'])}")
        print(f"Missing tools: {', '.join(report['tools_missing']) or 'none'}")
        print(
            "Destructive tools missing forbidden checks: "
            f"{', '.join(report['destructive_tools_missing_forbidden_checks']) or 'none'}"
        )
        print(f"Approval cases: {report['approval_cases']}")
        print(f"Privacy/secret cases: {report['privacy_or_secret_cases']}")
    return 0


def cmd_dataset_promote(args: argparse.Namespace) -> int:
    path = promote_scenario(
        args.dataset,
        args.scenario,
        status=args.status,
        owner=args.owner,
        tags=args.tag or [],
    )
    print(f"Updated {path}")
    return 0


def cmd_ci_annotate(args: argparse.Namespace) -> int:
    content = write_annotation(args.config, args.output, fmt=args.format, max_cases=args.max_cases)
    if not args.output:
        print(content)
    else:
        print(f"Wrote {args.output}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    serve(Path(args.config).resolve().parent, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="open-agentops")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="scan a repo for agents/tools/risks")
    scan.add_argument("path", nargs="?", default=".")
    scan.add_argument("--json", action="store_true")
    scan.set_defaults(func=cmd_scan)

    validate = sub.add_parser("validate", help="validate config and scenario test suites")
    validate.add_argument("--config", required=True)
    validate.set_defaults(func=cmd_validate)

    init = sub.add_parser("init", help="generate agentops.yml and starter scenario tests")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--agent", default="detected_agent")
    init.add_argument("--entrypoint", default="agent:agent")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    scenario = sub.add_parser("scenario", help="scenario harness commands")
    scenario_sub = scenario.add_subparsers(dest="scenario_command", required=True)
    scenario_create = scenario_sub.add_parser("create", help="create a scenario test file")
    scenario_create.add_argument("--agent", required=True)
    scenario_create.add_argument("--name", required=True)
    scenario_create.add_argument("--description", default="")
    scenario_create.add_argument("--output")
    scenario_create.add_argument("--force", action="store_true")
    scenario_create.set_defaults(func=cmd_scenario_create)
    scenario_trace = scenario_sub.add_parser("from-trace", help="generate a review-required scenario from a trace")
    scenario_trace.add_argument("--trace", required=True)
    scenario_trace.add_argument("--agent", required=True)
    scenario_trace.add_argument("--output", required=True)
    scenario_trace.add_argument("--config", help="optional agentops.yml for destructive tool policy lookup")
    scenario_trace.add_argument("--force", action="store_true")
    scenario_trace.set_defaults(func=cmd_scenario_from_trace)

    case = sub.add_parser("case", help="test case harness commands")
    case_sub = case.add_subparsers(dest="case_command", required=True)
    case_add = case_sub.add_parser("add", help="append a test case to a scenario")
    case_add.add_argument("--suite", required=True, help="scenario/test YAML file")
    case_add.add_argument("--id")
    case_add.add_argument("--user", required=True)
    case_add.add_argument("--contains", action="append")
    case_add.add_argument("--must-not-contain", dest="must_not_contain", action="append")
    case_add.add_argument("--tool-called", dest="tool_called", action="append")
    case_add.add_argument("--tool-not-called", dest="tool_not_called", action="append")
    case_add.add_argument("--approval-required-for", dest="approval_required_for", action="append")
    case_add.set_defaults(func=cmd_case_add)

    gen = sub.add_parser("generate", help="generate starter files")
    gen_sub = gen.add_subparsers(dest="generate_command", required=True)
    evals = gen_sub.add_parser("evals")
    evals.add_argument("path", nargs="?", default=".")
    evals.add_argument("--agent", default="detected_agent")
    evals.add_argument("--output")
    evals.set_defaults(func=cmd_generate)

    tests = gen_sub.add_parser("tests")
    tests.add_argument("path", nargs="?", default=".")
    tests.add_argument("--agent", default="detected_agent")
    tests.add_argument("--output")
    tests.set_defaults(func=cmd_generate)

    sims = gen_sub.add_parser("simulators")
    sims.add_argument("--from", dest="manifest", required=True, help="MCP/tool catalog/OpenAPI/custom tool manifest JSON")
    sims.add_argument("--output")
    sims.set_defaults(func=cmd_generate_simulators)

    scenarios = gen_sub.add_parser("scenarios", help="generate scenario YAML from config and optional model")
    scenarios.add_argument("--config", required=True)
    scenarios.add_argument("--agent", help="generate for one agent; defaults to all agents")
    scenarios.add_argument("--provider", choices=["local", "openai", "anthropic"], default="local")
    scenarios.add_argument("--model", help="model name for model-backed providers")
    scenarios.add_argument("--output-dir", help="directory for generated YAML; defaults to configured test suite path")
    scenarios.add_argument("--force", action="store_true", help="overwrite existing scenario files")
    scenarios.add_argument("--print-prompt", action="store_true", help="print the prompt that would be sent to the model")
    scenarios.set_defaults(func=cmd_generate_scenarios)

    eval_cmd = sub.add_parser("eval", help="eval commands")
    eval_sub = eval_cmd.add_subparsers(dest="eval_command", required=True)
    run = eval_sub.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument("--environment", default="ci")
    run.set_defaults(func=cmd_eval_run)

    test_cmd = sub.add_parser("test", help="test harness commands")
    test_sub = test_cmd.add_subparsers(dest="test_command", required=True)
    test_run = test_sub.add_parser("run", help="run scenario tests")
    test_run.add_argument("--config", required=True)
    test_run.add_argument("--environment", default="ci")
    test_run.set_defaults(func=cmd_eval_run)

    gate = sub.add_parser("gate", help="apply latest gate result")
    gate.add_argument("--config", required=True)
    gate.add_argument("--max-blocking", type=int, default=50, help="maximum raw blocking issues to print")
    gate.set_defaults(func=cmd_gate)

    report = sub.add_parser("report", help="print latest markdown report")
    report.add_argument("--config", required=True)
    report.set_defaults(func=cmd_report)

    history = sub.add_parser("history", help="list stored local runs")
    history.add_argument("--config", required=True)
    history.add_argument("--limit", type=int, default=20)
    history.add_argument("--json", action="store_true")
    history.set_defaults(func=cmd_history)

    baseline = sub.add_parser("baseline", help="save or compare baselines")
    baseline_sub = baseline.add_subparsers(dest="baseline_command", required=True)
    baseline_save = baseline_sub.add_parser("save")
    baseline_save.add_argument("--config", required=True)
    baseline_save.add_argument("--name", default="main")
    baseline_save.set_defaults(func=cmd_baseline_save)
    baseline_compare = baseline_sub.add_parser("compare")
    baseline_compare.add_argument("--config", required=True)
    baseline_compare.add_argument("--name", default="main")
    baseline_compare.add_argument("--fail-on-regression", action="store_true")
    baseline_compare.set_defaults(func=cmd_baseline_compare)

    export = sub.add_parser("export", help="copy latest report artifacts")
    export.add_argument("--config", required=True)
    export.add_argument("--output", required=True)
    export.set_defaults(func=cmd_export)

    traces = sub.add_parser("traces", help="trace import commands")
    traces_sub = traces.add_subparsers(dest="traces_command", required=True)
    traces_import = traces_sub.add_parser("import", help="normalize external traces into AgentOps trace JSONL")
    traces_import.add_argument("--input", required=True)
    traces_import.add_argument("--output", required=True)
    traces_import.add_argument("--format", default="auto", choices=["auto", "jsonl", "openai-agents", "openinference", "generic"])
    traces_import.set_defaults(func=cmd_traces_import)

    dataset = sub.add_parser("dataset", help="dataset lifecycle commands")
    dataset_sub = dataset.add_subparsers(dest="dataset_command", required=True)
    dataset_init = dataset_sub.add_parser("init", help="create dataset.yml from configured scenario suites")
    dataset_init.add_argument("--config", required=True)
    dataset_init.add_argument("--output", required=True)
    dataset_init.add_argument("--force", action="store_true")
    dataset_init.set_defaults(func=cmd_dataset_init)
    dataset_list = dataset_sub.add_parser("list", help="list dataset scenarios")
    dataset_list.add_argument("--dataset", required=True)
    dataset_list.add_argument("--json", action="store_true")
    dataset_list.set_defaults(func=cmd_dataset_list)
    dataset_validate = dataset_sub.add_parser("validate", help="validate dataset scenario files")
    dataset_validate.add_argument("--dataset", required=True)
    dataset_validate.set_defaults(func=cmd_dataset_validate)
    dataset_coverage = dataset_sub.add_parser("coverage", help="report tool/risk coverage for a dataset")
    dataset_coverage.add_argument("--dataset", required=True)
    dataset_coverage.add_argument("--config")
    dataset_coverage.add_argument("--json", action="store_true")
    dataset_coverage.set_defaults(func=cmd_dataset_coverage)
    dataset_promote = dataset_sub.add_parser("promote", help="add or update a scenario in a dataset")
    dataset_promote.add_argument("--dataset", required=True)
    dataset_promote.add_argument("--scenario", required=True)
    dataset_promote.add_argument("--status", default="approved", choices=["draft", "approved", "deprecated", "missing"])
    dataset_promote.add_argument("--owner")
    dataset_promote.add_argument("--tag", action="append")
    dataset_promote.set_defaults(func=cmd_dataset_promote)

    ci = sub.add_parser("ci", help="CI helper commands")
    ci_sub = ci.add_subparsers(dest="ci_command", required=True)
    ci_annotate = ci_sub.add_parser("annotate", help="write PR/CI annotation markdown from latest run")
    ci_annotate.add_argument("--config", required=True)
    ci_annotate.add_argument("--format", choices=["markdown", "ci", "json"], default="ci")
    ci_annotate.add_argument("--output")
    ci_annotate.add_argument("--max-cases", type=int, default=5)
    ci_annotate.set_defaults(func=cmd_ci_annotate)

    server = sub.add_parser("serve", help="serve local run history UI")
    server.add_argument("--config", required=True)
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8765)
    server.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"open-agentops: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
