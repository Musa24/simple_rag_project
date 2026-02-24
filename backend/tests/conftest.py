"""
conftest.py – pytest session setup.

Adds the backend/ directory to sys.path and installs lightweight mocks for
heavy external packages (chromadb, sentence_transformers, anthropic, dotenv)
*before* any backend module is imported.  This lets the test suite run without
needing a GPU, a live Anthropic API key, or a running ChromaDB instance.

Also patches fastapi.staticfiles.StaticFiles so that app.py can be imported
in tests without the ../frontend directory needing to exist on disk.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch

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

# ---------------------------------------------------------------------------
# 3. Patch fastapi.staticfiles.StaticFiles so app.py can be imported without
#    a real ../frontend directory.  DevStaticFiles inherits from StaticFiles,
#    so replacing StaticFiles with MagicMock (the class, not an instance) lets
#    DevStaticFiles(...) construct without any filesystem checks.
# ---------------------------------------------------------------------------
import fastapi.staticfiles  # noqa: E402 – must run after sys.path is set
fastapi.staticfiles.StaticFiles = MagicMock


# ---------------------------------------------------------------------------
# 4. Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_rag_system():
    """
    A pre-configured MagicMock that stands in for a real RAGSystem.

    Default return values cover the happy-path for every API endpoint:
      - query()               → ("Test answer", [])
      - get_course_analytics()→ {total_courses: 2, course_titles: [...]}
      - session_manager.*     → sensible stubs

    Individual tests may override any return value or side_effect before
    making their HTTP request.
    """
    mock = MagicMock()
    mock.query.return_value = ("Test answer", [])
    mock.session_manager.create_session.return_value = "test-session-id"
    mock.session_manager.clear_session.return_value = None
    mock.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
    # Prevent tuple-unpack errors if the startup event fires add_course_folder
    mock.add_course_folder.return_value = (0, 0)
    return mock


@pytest.fixture
def api_client(mock_rag_system):
    """
    A Starlette TestClient pointed at the real FastAPI app from app.py,
    with rag_system replaced by mock_rag_system.

    Using this fixture in a test also gives you access to mock_rag_system
    so you can inspect calls or override return values:

        def test_something(self, api_client, mock_rag_system):
            mock_rag_system.query.return_value = ("Custom", [])
            response = api_client.post("/api/query", json={"query": "q"})
    """
    from fastapi.testclient import TestClient
    import app as app_module

    with patch.object(app_module, "rag_system", mock_rag_system):
        with TestClient(app_module.app, raise_server_exceptions=False) as client:
            yield client
