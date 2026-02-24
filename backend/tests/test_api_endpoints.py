"""
Tests for the FastAPI endpoints defined in backend/app.py.

Covers:
  POST   /api/query               – query processing
  GET    /api/courses              – course statistics
  DELETE /api/session/{session_id} – session cleanup

All tests rely on the ``api_client`` and ``mock_rag_system`` fixtures from
conftest.py.  No ChromaDB, Anthropic API, or filesystem access is required.

Design notes
------------
* ``api_client`` is a Starlette TestClient pointed at the real FastAPI app,
  with the module-level ``rag_system`` object replaced by ``mock_rag_system``.
* ``mock_rag_system`` is a pre-configured MagicMock; individual tests override
  return values / side_effects for the specific behaviour they need to verify.
* ``raise_server_exceptions=False`` on the TestClient means route-level
  HTTPException(500) is returned as a 500 response rather than being re-raised,
  so we can assert on the status code directly.
"""

import pytest


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:

    def test_returns_200_for_valid_query(self, api_client, mock_rag_system):
        response = api_client.post("/api/query", json={"query": "What is MCP?"})
        assert response.status_code == 200

    def test_response_body_has_required_fields(self, api_client, mock_rag_system):
        response = api_client.post("/api/query", json={"query": "What is RAG?"})
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data

    def test_answer_text_comes_from_rag_system(self, api_client, mock_rag_system):
        mock_rag_system.query.return_value = ("Deep learning answer", [])

        response = api_client.post(
            "/api/query", json={"query": "What is deep learning?"}
        )

        assert response.json()["answer"] == "Deep learning answer"

    def test_sources_propagated_from_rag_system(self, api_client, mock_rag_system):
        sources = [{"label": "Course A - Lesson 1", "url": "https://example.com"}]
        mock_rag_system.query.return_value = ("Answer with sources", sources)

        response = api_client.post("/api/query", json={"query": "q"})

        assert response.json()["sources"] == sources

    def test_provided_session_id_is_forwarded_to_rag(self, api_client, mock_rag_system):
        """session_id from the request body must be passed straight to RAGSystem.query."""
        response = api_client.post(
            "/api/query", json={"query": "follow-up", "session_id": "existing-session"}
        )

        mock_rag_system.query.assert_called_once_with("follow-up", "existing-session")
        assert response.json()["session_id"] == "existing-session"

    def test_new_session_created_when_none_provided(self, api_client, mock_rag_system):
        """When session_id is absent, a new session is created and returned."""
        mock_rag_system.session_manager.create_session.return_value = "new-sess-123"

        response = api_client.post("/api/query", json={"query": "q"})

        mock_rag_system.session_manager.create_session.assert_called_once()
        assert response.json()["session_id"] == "new-sess-123"

    def test_rag_called_with_generated_session_id(self, api_client, mock_rag_system):
        """When no session_id is supplied, RAGSystem.query receives the newly created one."""
        mock_rag_system.session_manager.create_session.return_value = "generated-id"

        api_client.post("/api/query", json={"query": "q"})

        mock_rag_system.query.assert_called_once_with("q", "generated-id")

    def test_returns_500_when_rag_system_raises(self, api_client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("DB unavailable")

        response = api_client.post("/api/query", json={"query": "q"})

        assert response.status_code == 500

    def test_error_detail_included_in_500_response(self, api_client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("DB unavailable")

        response = api_client.post("/api/query", json={"query": "q"})

        assert "DB unavailable" in response.json()["detail"]

    def test_missing_query_field_returns_422(self, api_client, mock_rag_system):
        """FastAPI should reject requests that omit the required 'query' field."""
        response = api_client.post("/api/query", json={})
        assert response.status_code == 422

    def test_empty_sources_list_returned_when_no_tool_called(
        self, api_client, mock_rag_system
    ):
        mock_rag_system.query.return_value = ("General knowledge answer", [])

        response = api_client.post("/api/query", json={"query": "What is 2 + 2?"})

        assert response.json()["sources"] == []


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:

    def test_returns_200(self, api_client, mock_rag_system):
        response = api_client.get("/api/courses")
        assert response.status_code == 200

    def test_response_has_total_courses_and_titles(self, api_client, mock_rag_system):
        response = api_client.get("/api/courses")
        data = response.json()
        assert "total_courses" in data
        assert "course_titles" in data

    def test_total_courses_reflects_analytics(self, api_client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": ["A", "B", "C"],
        }

        response = api_client.get("/api/courses")

        assert response.json()["total_courses"] == 3

    def test_course_titles_list_reflects_analytics(self, api_client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": ["RAG Basics", "MCP Fundamentals"],
        }

        response = api_client.get("/api/courses")

        assert response.json()["course_titles"] == ["RAG Basics", "MCP Fundamentals"]

    def test_empty_catalog_returns_zero_and_empty_list(
        self, api_client, mock_rag_system
    ):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }

        response = api_client.get("/api/courses")
        data = response.json()

        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_get_course_analytics_called_once(self, api_client, mock_rag_system):
        api_client.get("/api/courses")
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_returns_500_when_analytics_raises(self, api_client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = Exception("Analytics error")

        response = api_client.get("/api/courses")

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /api/session/{session_id}
# ---------------------------------------------------------------------------

class TestDeleteSessionEndpoint:

    def test_returns_200_on_successful_delete(self, api_client, mock_rag_system):
        response = api_client.delete("/api/session/session-abc")
        assert response.status_code == 200

    def test_response_body_is_cleared_status(self, api_client, mock_rag_system):
        response = api_client.delete("/api/session/session-abc")
        assert response.json() == {"status": "cleared"}

    def test_clear_session_called_with_correct_id(self, api_client, mock_rag_system):
        api_client.delete("/api/session/my-session-id")
        mock_rag_system.session_manager.clear_session.assert_called_once_with(
            "my-session-id"
        )

    def test_different_session_ids_are_each_forwarded(
        self, api_client, mock_rag_system
    ):
        """Each DELETE uses the exact session_id from the URL path."""
        api_client.delete("/api/session/alpha")
        api_client.delete("/api/session/beta")

        calls = [
            c.args[0]
            for c in mock_rag_system.session_manager.clear_session.call_args_list
        ]
        assert calls == ["alpha", "beta"]
