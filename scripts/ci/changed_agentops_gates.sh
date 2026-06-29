#!/usr/bin/env bash
set -euo pipefail

BASE_REF="${1:-}"
PYTHON_BIN="${PYTHON:-python3}"
ARTIFACT_ROOT="${ARTIFACT_ROOT:-agentops-artifacts/changed-agent-gates}"

if [ -z "$BASE_REF" ] || ! git rev-parse --verify "$BASE_REF^{commit}" >/dev/null 2>&1; then
  if git rev-parse --verify HEAD^ >/dev/null 2>&1; then
    BASE_REF="HEAD^"
  else
    echo "No base commit available; skipping changed agent gates."
    exit 0
  fi
fi

CHANGED_FILES="$(mktemp)"
CONFIGS_FILE="$(mktemp)"

cleanup() {
  rm -f "$CHANGED_FILES" "$CONFIGS_FILE"
}
trap cleanup EXIT

git diff --name-only --diff-filter=ACMRT "$BASE_REF"...HEAD | sort > "$CHANGED_FILES"
if [ ! -s "$CHANGED_FILES" ]; then
  echo "No changed files; skipping changed agent gates."
  exit 0
fi

find_config() {
  local path="$1"
  local dir
  if [ -d "$path" ]; then
    dir="$path"
  else
    dir="$(dirname "$path")"
  fi

  while [ "$dir" != "." ] && [ "$dir" != "/" ]; do
    if [ -f "$dir/agentops.yml" ]; then
      printf '%s\n' "$dir/agentops.yml"
      return 0
    fi
    if [ -f "$dir/agentops.safe.yml" ]; then
      printf '%s\n' "$dir/agentops.safe.yml"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

while IFS= read -r file; do
  if config="$(find_config "$file")"; then
    printf '%s\n' "$config" >> "$CONFIGS_FILE"
  fi
done < "$CHANGED_FILES"

if [ ! -s "$CONFIGS_FILE" ]; then
  echo "No changed agent configs found; skipping changed agent gates."
  exit 0
fi

mkdir -p "$ARTIFACT_ROOT"
status=0
sort -u "$CONFIGS_FILE" | while IFS= read -r config; do
  safe_name="$(printf '%s' "$config" | tr '/.' '__')"
  output_dir="$ARTIFACT_ROOT/$safe_name"
  echo "== Changed agent gate: $config =="
  if ! PYTHON="$PYTHON_BIN" bash scripts/ci/agentops_gate.sh "$config" "$output_dir"; then
    touch "$ARTIFACT_ROOT/.failed"
  fi
done

if [ -f "$ARTIFACT_ROOT/.failed" ]; then
  status=1
fi

exit "$status"
