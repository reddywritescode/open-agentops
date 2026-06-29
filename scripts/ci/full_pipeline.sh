#!/usr/bin/env bash
set -euo pipefail

ARTIFACT_DIR="${1:-agentops-artifacts}"
PYTHON_BIN="${PYTHON:-python3}"
SAFE_CONFIG="examples/validation_suite/agentops.safe.yml"
BAD_CONFIG="examples/validation_suite/agentops.candidate-bad.yml"
GENERATED_EXPECTED="examples/refund_agent/agentops.generated-tools.yml"
GENERATED_ACTUAL="$(mktemp)"

cleanup() {
  rm -f "$GENERATED_ACTUAL"
}
trap cleanup EXIT

echo "== Install package =="
"$PYTHON_BIN" -m pip install -e .

echo "== Compile =="
"$PYTHON_BIN" -m compileall -q src tests examples/validation_suite examples/refund_agent examples/litmus_100

echo "== Unit and contract tests =="
"$PYTHON_BIN" -m unittest discover -s tests -v

echo "== Validate configs =="
"$PYTHON_BIN" -m open_agentops.cli validate --config "$SAFE_CONFIG"
"$PYTHON_BIN" -m open_agentops.cli validate --config "$BAD_CONFIG"

echo "== Verify generated simulator policy is up to date =="
"$PYTHON_BIN" -m open_agentops.cli generate simulators \
  --from examples/refund_agent/tool_manifest.json \
  --output "$GENERATED_ACTUAL"
if ! cmp -s "$GENERATED_EXPECTED" "$GENERATED_ACTUAL"; then
  echo "Generated simulator policy is stale: $GENERATED_EXPECTED" >&2
  echo "Regenerate with:" >&2
  echo "  open-agentops generate simulators --from examples/refund_agent/tool_manifest.json --output $GENERATED_EXPECTED" >&2
  diff -u "$GENERATED_EXPECTED" "$GENERATED_ACTUAL" || true
  exit 1
fi

echo "== Scan validation suite =="
"$PYTHON_BIN" -m open_agentops.cli scan examples/validation_suite

echo "== Safe baseline must pass =="
"$PYTHON_BIN" -m open_agentops.cli test run --config "$SAFE_CONFIG"
"$PYTHON_BIN" -m open_agentops.cli gate --config "$SAFE_CONFIG"
"$PYTHON_BIN" -m open_agentops.cli baseline save --config "$SAFE_CONFIG" --name release

echo "== Bad candidate must fail =="
set +e
"$PYTHON_BIN" -m open_agentops.cli test run --config "$BAD_CONFIG"
BAD_EVAL_STATUS=$?
"$PYTHON_BIN" -m open_agentops.cli gate --config "$BAD_CONFIG"
BAD_GATE_STATUS=$?
set -e

if [ "$BAD_EVAL_STATUS" -eq 0 ]; then
  echo "Expected bad candidate test run to fail, but it passed" >&2
  exit 1
fi

if [ "$BAD_GATE_STATUS" -eq 0 ]; then
  echo "Expected bad candidate gate to fail, but it passed" >&2
  exit 1
fi

echo "Bad candidate correctly failed: test_run=$BAD_EVAL_STATUS gate=$BAD_GATE_STATUS"

echo "== Roll back to safe baseline and prove no regression =="
"$PYTHON_BIN" -m open_agentops.cli test run --config "$SAFE_CONFIG"
"$PYTHON_BIN" -m open_agentops.cli gate --config "$SAFE_CONFIG"
"$PYTHON_BIN" -m open_agentops.cli baseline compare --config "$SAFE_CONFIG" --name release --fail-on-regression

echo "== Export CI artifacts =="
rm -rf "$ARTIFACT_DIR"
"$PYTHON_BIN" -m open_agentops.cli export --config "$SAFE_CONFIG" --output "$ARTIFACT_DIR"
"$PYTHON_BIN" -m open_agentops.cli ci annotate --config "$SAFE_CONFIG" --format ci --output "$ARTIFACT_DIR/ci-summary.md"
find "$ARTIFACT_DIR" -maxdepth 1 -type f -print | sort
