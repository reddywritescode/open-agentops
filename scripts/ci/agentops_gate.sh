#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-examples/validation_suite/agentops.safe.yml}"
EXPORT_DIR="${2:-agentops-artifacts}"
PYTHON_BIN="${PYTHON:-python3}"

"$PYTHON_BIN" -m pip install -e .
"$PYTHON_BIN" -m open_agentops.cli validate --config "$CONFIG"

set +e
"$PYTHON_BIN" -m open_agentops.cli test run --config "$CONFIG"
TEST_STATUS=$?
"$PYTHON_BIN" -m open_agentops.cli gate --config "$CONFIG"
GATE_STATUS=$?
set -e

rm -rf "$EXPORT_DIR"
"$PYTHON_BIN" -m open_agentops.cli export --config "$CONFIG" --output "$EXPORT_DIR"
"$PYTHON_BIN" -m open_agentops.cli ci annotate --config "$CONFIG" --format ci --output "$EXPORT_DIR/ci-summary.md"

if [ "$TEST_STATUS" -ne 0 ]; then
  exit "$TEST_STATUS"
fi

exit "$GATE_STATUS"
