#!/bin/bash
# Run all code quality checks (non-destructive, exit 1 on failure).
# Suitable for CI or pre-commit verification.
# Run from the repo root: ./scripts/check_quality.sh

set -e

cd "$(dirname "$0")/.." 

echo "==> black (format check)"
uv run black backend/ --check

echo ""
echo "All quality checks passed."
