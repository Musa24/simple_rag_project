"""
conftest.py – pytest session setup.

Adds the backend/ directory to sys.path and installs lightweight mocks for
heavy external packages (chromadb, sentence_transformers, anthropic, dotenv)
*before* any backend module is imported.  This lets the test suite run without
needing a GPU, a live Anthropic API key, or a running ChromaDB instance.
"""

import sys
import os
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Add backend/ to the import path
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ---------------------------------------------------------------------------
# 2. Stub out heavy / external packages before any backend imports
# ---------------------------------------------------------------------------
_MOCKED_PACKAGES = [
    "chromadb",
    "chromadb.config",
    "chromadb.utils",
    "chromadb.utils.embedding_functions",
    "sentence_transformers",
    "anthropic",
    "dotenv",
]

for _pkg in _MOCKED_PACKAGES:
    if _pkg not in sys.modules:
        sys.modules[_pkg] = MagicMock()
