#!/bin/bash
# Format all Python source files with black.
# Run from the repo root: ./scripts/format.sh

set -e

cd "$(dirname "$0")/.." 

echo "Running black formatter..."
uv run black backend/
echo "Done."
