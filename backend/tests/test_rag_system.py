"""
Tests for RAGSystem.query() (rag_system.py).

Focus: how the RAG system handles content-query routing – does it pass the
right prompt to the AI, thread session history correctly, collect sources from
the tool, and reset them afterwards?

All heavy sub-components are replaced with MagicMocks so no ChromaDB, no
Anthropic API, and no file I/O is required.
"""

import pytest
from unittest.mock import MagicMock, patch

# conftest.py has already mocked chromadb / anthropic and added backend/ to path.
from rag_system import RAGSystem
from search_tools import CourseSearchTool


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def rag():
    """
    Return a RAGSystem whose internal components are replaced with mocks.

    We patch the constructor dependencies so RAGSystem.__init__ never touches
    real ChromaDB, real Anthropic, or the filesystem.
    """
    with patch("rag_system.DocumentProcessor"), \
         patch("rag_system.VectorStore"), \
         patch("rag_system.AIGenerator") as MockAI, \
         patch("rag_system.SessionManager") as MockSession, \
         patch("rag_system.ToolManager") as MockTM, \
         patch("rag_system.CourseSearchTool") as MockCST, \
         patch("rag_system.CourseOutlineTool"):

        from dataclasses import dataclass

        @dataclass
        class MockConfig:
            CHUNK_SIZE: int = 800
            CHUNK_OVERLAP: int = 100
            CHROMA_PATH: str = "/tmp/test_chroma"
            EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
            MAX_RESULTS: int = 5
            MAX_HISTORY: int = 2
            ANTHROPIC_API_KEY: str = "test-key"
            ANTHROPIC_MODEL: str = "test-model"

        system = RAGSystem(MockConfig())

        # Expose mock instances for convenient test-level control
        system._mock_ai = MockAI.return_value
        system._mock_session = MockSession.return_value
        system._mock_tm = MockTM.return_value

    # Default behaviours
    system.ai_generator = system._mock_ai
    system.session_manager = system._mock_session
    system.tool_manager = system._mock_tm

    system._mock_ai.generate_response.return_value = "AI answer"
    system._mock_session.get_conversation_history.return_value = None
    system._mock_tm.get_last_sources.return_value = []
    system._mock_tm.get_tool_definitions.return_value = [{"name": "search_course_content"}]

    return system


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

class TestRAGQueryPrompt:

    def test_query_is_wrapped_with_course_materials_prefix(self, rag):
        """
        RAGSystem wraps every user query with a 'course materials' prefix
        before handing it to the AI generator.  This means even general
        knowledge questions are framed as course queries – a design issue
        that may cause unnecessary tool calls.
        """
        rag.query("What is 2 + 2?")

        call_kwargs = rag._mock_ai.generate_response.call_args.kwargs
        prompt_sent = call_kwargs.get("query") or rag._mock_ai.generate_response.call_args.args[0]
        assert "What is 2 + 2?" in prompt_sent
        assert "course materials" in prompt_sent.lower()

    def test_original_user_query_is_present_in_prompt(self, rag):
        rag.query("Explain RAG in detail")

        call_kwargs = rag._mock_ai.generate_response.call_args.kwargs
        prompt = call_kwargs.get("query") or rag._mock_ai.generate_response.call_args.args[0]
        assert "Explain RAG in detail" in prompt

    def test_tool_definitions_passed_to_generator(self, rag):
        rag.query("Some question")

        call_kwargs = rag._mock_ai.generate_response.call_args.kwargs
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == [{"name": "search_course_content"}]

    def test_tool_manager_passed_to_generator(self, rag):
        rag.query("Some question")

        call_kwargs = rag._mock_ai.generate_response.call_args.kwargs
        assert call_kwargs.get("tool_manager") is rag.tool_manager


# ---------------------------------------------------------------------------
# Return values
# ---------------------------------------------------------------------------

class TestRAGQueryReturnValues:

    def test_returns_tuple_of_response_and_sources(self, rag):
        result = rag.query("What is MCP?")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_response_text_comes_from_ai_generator(self, rag):
        rag._mock_ai.generate_response.return_value = "Detailed MCP explanation"

        response, _ = rag.query("What is MCP?")

        assert response == "Detailed MCP explanation"

    def test_sources_come_from_tool_manager(self, rag):
        rag._mock_tm.get_last_sources.return_value = [
            {"label": "MCP Course - Lesson 1", "url": "https://example.com"}
        ]

        _, sources = rag.query("What is MCP?")

        assert len(sources) == 1
        assert sources[0]["label"] == "MCP Course - Lesson 1"

    def test_sources_empty_when_no_tool_called(self, rag):
        rag._mock_tm.get_last_sources.return_value = []

        _, sources = rag.query("What is 2 + 2?")

        assert sources == []


# ---------------------------------------------------------------------------
# Sources lifecycle
# ---------------------------------------------------------------------------

class TestRAGSourcesLifecycle:

    def test_tool_manager_get_last_sources_called_once(self, rag):
        rag.query("q")
        rag._mock_tm.get_last_sources.assert_called_once()

    def test_tool_manager_reset_sources_called_after_retrieval(self, rag):
        """Sources must be reset after being returned so they don't bleed into the next query."""
        rag.query("q")
        rag._mock_tm.reset_sources.assert_called_once()

    def test_reset_sources_called_after_get_last_sources(self, rag):
        """reset_sources must be called AFTER get_last_sources, not before."""
        call_order = []
        rag._mock_tm.get_last_sources.side_effect = lambda: call_order.append("get")
        rag._mock_tm.reset_sources.side_effect = lambda: call_order.append("reset")

        rag.query("q")

        assert call_order == ["get", "reset"], (
            f"Expected ['get', 'reset'] but got {call_order}"
        )


# ---------------------------------------------------------------------------
# Session / conversation history
# ---------------------------------------------------------------------------

class TestRAGSessionHistory:

    def test_no_history_fetched_when_session_id_is_none(self, rag):
        rag.query("q", session_id=None)
        rag._mock_session.get_conversation_history.assert_not_called()

    def test_history_fetched_for_given_session_id(self, rag):
        rag._mock_session.get_conversation_history.return_value = "User: hi\nAssistant: hello"

        rag.query("q", session_id="session_1")

        rag._mock_session.get_conversation_history.assert_called_once_with("session_1")

    def test_history_passed_to_ai_generator(self, rag):
        rag._mock_session.get_conversation_history.return_value = "User: hi\nAssistant: hello"

        rag.query("q", session_id="session_1")

        call_kwargs = rag._mock_ai.generate_response.call_args.kwargs
        assert call_kwargs.get("conversation_history") == "User: hi\nAssistant: hello"

    def test_no_history_in_generator_when_session_id_none(self, rag):
        rag.query("q", session_id=None)

        call_kwargs = rag._mock_ai.generate_response.call_args.kwargs
        assert call_kwargs.get("conversation_history") is None

    def test_exchange_added_to_session_after_response(self, rag):
        rag._mock_ai.generate_response.return_value = "Final answer"

        rag.query("User question", session_id="session_1")

        rag._mock_session.add_exchange.assert_called_once_with(
            "session_1", "User question", "Final answer"
        )

    def test_no_exchange_added_when_session_id_none(self, rag):
        rag.query("q", session_id=None)
        rag._mock_session.add_exchange.assert_not_called()


# ---------------------------------------------------------------------------
# General-knowledge vs content queries (prompt framing issue)
# ---------------------------------------------------------------------------

class TestRAGQueryFraming:

    def test_general_question_still_gets_course_materials_prefix(self, rag):
        """
        DESIGN ISSUE: the prompt prefix 'Answer this question about course
        materials:' is applied unconditionally, even for clearly general
        questions.  This can cause Claude to search for course content when
        no search is needed, wasting tokens and latency.

        The test documents the current (potentially undesired) behaviour.
        """
        rag.query("What is the capital of France?")

        kwargs = rag._mock_ai.generate_response.call_args.kwargs
        prompt = kwargs.get("query") or rag._mock_ai.generate_response.call_args.args[0]
        # Currently the prefix IS added – this may not be the desired behaviour
        assert "Answer this question about course materials" in prompt
