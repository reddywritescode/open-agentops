#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "== Scan validation suite =="
.venv/bin/open-agentops scan examples/validation_suite

echo "== Safe baseline run =="
.venv/bin/open-agentops test run --config examples/validation_suite/agentops.safe.yml
.venv/bin/open-agentops gate --config examples/validation_suite/agentops.safe.yml
.venv/bin/open-agentops baseline save --config examples/validation_suite/agentops.safe.yml --name release

echo "== Bad candidate run, expected to fail =="
set +e
.venv/bin/open-agentops test run --config examples/validation_suite/agentops.candidate-bad.yml
BAD_EVAL=$?
.venv/bin/open-agentops gate --config examples/validation_suite/agentops.candidate-bad.yml
BAD_GATE=$?
set -e
echo "bad_test_run_exit=$BAD_EVAL"
echo "bad_gate_exit=$BAD_GATE"

echo "== Rollback to safe baseline =="
.venv/bin/open-agentops test run --config examples/validation_suite/agentops.safe.yml
.venv/bin/open-agentops gate --config examples/validation_suite/agentops.safe.yml
.venv/bin/open-agentops baseline compare --config examples/validation_suite/agentops.safe.yml --name release --fail-on-regression
