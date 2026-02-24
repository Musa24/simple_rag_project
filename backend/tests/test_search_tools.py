"""
Tests for CourseSearchTool.execute() and ToolManager (search_tools.py).

All tests use a mock VectorStore; no ChromaDB or network access required.
"""

import pytest
from unittest.mock import MagicMock, call

# conftest.py has already added backend/ to sys.path and mocked chromadb /
# sentence_transformers, so these imports work in isolation.
from vector_store import SearchResults
from search_tools import CourseSearchTool, ToolManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_results(docs, metas, distances=None):
    """Build a non-empty SearchResults with sensible defaults."""
    return SearchResults(
        documents=docs,
        metadata=metas,
        distances=distances or [0.5] * len(docs),
    )


def empty_results():
    return SearchResults(documents=[], metadata=[], distances=[])


def error_results(msg):
    return SearchResults(documents=[], metadata=[], distances=[], error=msg)


# ---------------------------------------------------------------------------
# CourseSearchTool.execute() – success paths
# ---------------------------------------------------------------------------

class TestCourseSearchToolExecuteSuccess:

    def setup_method(self):
        self.store = MagicMock()
        self.tool = CourseSearchTool(self.store)

    def test_returns_non_empty_string_when_results_found(self):
        self.store.search.return_value = make_results(
            docs=["MCP is a protocol for tool communication."],
            metas=[{"course_title": "MCP Course", "lesson_number": 1}],
        )
        self.store.get_lesson_link.return_value = "https://example.com/lesson1"

        result = self.tool.execute(query="What is MCP?")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_result_contains_course_title(self):
        self.store.search.return_value = make_results(
            docs=["Tool communication details."],
            metas=[{"course_title": "MCP Course", "lesson_number": 2}],
        )
        self.store.get_lesson_link.return_value = None

        result = self.tool.execute(query="tool communication")

        assert "MCP Course" in result

    def test_result_contains_document_text(self):
        self.store.search.return_value = make_results(
            docs=["The answer is 42."],
            metas=[{"course_title": "Course A", "lesson_number": 1}],
        )
        self.store.get_lesson_link.return_value = None

        result = self.tool.execute(query="answer")

        assert "The answer is 42." in result

    def test_header_includes_lesson_number_when_present(self):
        self.store.search.return_value = make_results(
            docs=["Content"],
            metas=[{"course_title": "Course A", "lesson_number": 5}],
        )
        self.store.get_lesson_link.return_value = None

        result = self.tool.execute(query="q")

        assert "Lesson 5" in result

    def test_header_omits_lesson_when_absent_from_metadata(self):
        """When metadata has no 'lesson_number', header must not include 'Lesson'."""
        self.store.search.return_value = make_results(
            docs=["Content"],
            metas=[{"course_title": "Course A"}],   # no lesson_number key
        )
        self.store.get_lesson_link.return_value = None

        result = self.tool.execute(query="q")

        assert "Lesson" not in result

    def test_multiple_results_joined_by_double_newline(self):
        self.store.search.return_value = make_results(
            docs=["Doc 1", "Doc 2"],
            metas=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 3},
            ],
        )
        self.store.get_lesson_link.return_value = None

        result = self.tool.execute(query="q")

        assert "\n\n" in result
        assert "Course A" in result
        assert "Course B" in result

    def test_get_lesson_link_called_for_every_result(self):
        self.store.search.return_value = make_results(
            docs=["d1", "d2", "d3"],
            metas=[
                {"course_title": "C", "lesson_number": 1},
                {"course_title": "C", "lesson_number": 2},
                {"course_title": "C", "lesson_number": 3},
            ],
        )
        self.store.get_lesson_link.return_value = None

        self.tool.execute(query="q")

        assert self.store.get_lesson_link.call_count == 3


# ---------------------------------------------------------------------------
# CourseSearchTool.execute() – store call arguments
# ---------------------------------------------------------------------------

class TestCourseSearchToolStoreArgs:

    def setup_method(self):
        self.store = MagicMock()
        self.store.search.return_value = empty_results()
        self.tool = CourseSearchTool(self.store)

    def _search_kwargs(self):
        return self.store.search.call_args.kwargs

    def test_passes_query_to_store(self):
        self.tool.execute(query="specific search query")
        assert self._search_kwargs()["query"] == "specific search query"

    def test_passes_course_name_to_store(self):
        self.tool.execute(query="q", course_name="MCP Course")
        assert self._search_kwargs()["course_name"] == "MCP Course"

    def test_passes_lesson_number_to_store(self):
        self.tool.execute(query="q", lesson_number=7)
        assert self._search_kwargs()["lesson_number"] == 7

    def test_course_name_defaults_to_none(self):
        self.tool.execute(query="q")
        assert self._search_kwargs().get("course_name") is None

    def test_lesson_number_defaults_to_none(self):
        self.tool.execute(query="q")
        assert self._search_kwargs().get("lesson_number") is None


# ---------------------------------------------------------------------------
# CourseSearchTool.execute() – empty / error results
# ---------------------------------------------------------------------------

class TestCourseSearchToolEmptyAndError:

    def setup_method(self):
        self.store = MagicMock()
        self.tool = CourseSearchTool(self.store)

    def test_empty_results_no_filter(self):
        self.store.search.return_value = empty_results()
        result = self.tool.execute(query="unknown topic")
        assert "No relevant content found" in result

    def test_empty_results_includes_course_name_when_filtered(self):
        self.store.search.return_value = empty_results()
        result = self.tool.execute(query="q", course_name="RAG Course")
        assert "No relevant content found" in result
        assert "RAG Course" in result

    def test_empty_results_includes_lesson_number_when_filtered(self):
        self.store.search.return_value = empty_results()
        result = self.tool.execute(query="q", lesson_number=4)
        assert "No relevant content found" in result
        assert "4" in result

    def test_empty_results_includes_both_filters(self):
        self.store.search.return_value = empty_results()
        result = self.tool.execute(query="q", course_name="MCP", lesson_number=2)
        assert "MCP" in result
        assert "2" in result

    def test_error_from_store_is_returned_directly(self):
        self.store.search.return_value = error_results("Search error: DB unavailable")
        result = self.tool.execute(query="anything")
        assert "Search error" in result

    def test_error_message_is_not_no_relevant_content(self):
        """An error is distinct from 'no results'."""
        self.store.search.return_value = error_results("Some error")
        result = self.tool.execute(query="q")
        assert "No relevant content found" not in result


# ---------------------------------------------------------------------------
# CourseSearchTool – last_sources tracking
# ---------------------------------------------------------------------------

class TestCourseSearchToolSources:

    def setup_method(self):
        self.store = MagicMock()
        self.tool = CourseSearchTool(self.store)

    def test_last_sources_populated_after_successful_search(self):
        self.store.search.return_value = make_results(
            docs=["d1", "d2"],
            metas=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course A", "lesson_number": 2},
            ],
        )
        self.store.get_lesson_link.return_value = "https://example.com"

        self.tool.execute(query="q")

        assert len(self.tool.last_sources) == 2

    def test_last_sources_label_includes_lesson_number(self):
        self.store.search.return_value = make_results(
            docs=["d"],
            metas=[{"course_title": "Course A", "lesson_number": 3}],
        )
        self.store.get_lesson_link.return_value = None

        self.tool.execute(query="q")

        assert self.tool.last_sources[0]["label"] == "Course A - Lesson 3"

    def test_last_sources_label_without_lesson_is_just_course_title(self):
        self.store.search.return_value = make_results(
            docs=["d"],
            metas=[{"course_title": "My Course"}],  # no lesson_number
        )
        self.store.get_lesson_link.return_value = None

        self.tool.execute(query="q")

        assert self.tool.last_sources[0]["label"] == "My Course"

    def test_last_sources_url_comes_from_get_lesson_link(self):
        self.store.search.return_value = make_results(
            docs=["d"],
            metas=[{"course_title": "Course A", "lesson_number": 1}],
        )
        self.store.get_lesson_link.return_value = "https://course-a.com/lesson1"

        self.tool.execute(query="q")

        assert self.tool.last_sources[0]["url"] == "https://course-a.com/lesson1"

    def test_last_sources_cleared_on_empty_results(self):
        """
        After a search that returns no results, last_sources must be reset to
        [] so stale sources from a previous query cannot bleed through to the
        next response.
        """
        self.store.search.return_value = make_results(
            docs=["d"],
            metas=[{"course_title": "Old Course", "lesson_number": 1}],
        )
        self.store.get_lesson_link.return_value = None
        self.tool.execute(query="first query")          # populates last_sources

        self.store.search.return_value = empty_results()
        self.tool.execute(query="second query - no results")

        # last_sources must be empty – no stale entries from the first search
        assert self.tool.last_sources == []


# ---------------------------------------------------------------------------
# ToolManager
# ---------------------------------------------------------------------------

class TestToolManager:

    def setup_method(self):
        self.manager = ToolManager()

    def _make_tool(self, name, execute_return="result"):
        tool = MagicMock()
        tool.get_tool_definition.return_value = {"name": name}
        tool.execute.return_value = execute_return
        return tool

    def test_register_tool_makes_it_available(self):
        tool = self._make_tool("my_tool")
        self.manager.register_tool(tool)
        assert "my_tool" in self.manager.tools

    def test_get_tool_definitions_returns_all_defs(self):
        self.manager.register_tool(self._make_tool("tool_a"))
        self.manager.register_tool(self._make_tool("tool_b"))

        defs = self.manager.get_tool_definitions()

        names = [d["name"] for d in defs]
        assert "tool_a" in names
        assert "tool_b" in names

    def test_execute_tool_dispatches_by_name(self):
        tool = self._make_tool("search_course_content", execute_return="search output")
        self.manager.register_tool(tool)

        result = self.manager.execute_tool("search_course_content", query="test")

        tool.execute.assert_called_once_with(query="test")
        assert result == "search output"

    def test_execute_unknown_tool_returns_error_string(self):
        result = self.manager.execute_tool("nonexistent_tool")
        assert "nonexistent_tool" in result or "not found" in result.lower()

    def test_get_last_sources_returns_sources_from_course_search_tool(self):
        mock_store = MagicMock()
        search_tool = CourseSearchTool(mock_store)
        search_tool.last_sources = [{"label": "Course A - Lesson 1", "url": "http://x.com"}]
        self.manager.register_tool(search_tool)

        sources = self.manager.get_last_sources()

        assert len(sources) == 1
        assert sources[0]["label"] == "Course A - Lesson 1"

    def test_get_last_sources_returns_empty_when_no_sources(self):
        mock_store = MagicMock()
        search_tool = CourseSearchTool(mock_store)
        search_tool.last_sources = []
        self.manager.register_tool(search_tool)

        assert self.manager.get_last_sources() == []

    def test_reset_sources_empties_last_sources(self):
        mock_store = MagicMock()
        search_tool = CourseSearchTool(mock_store)
        search_tool.last_sources = [{"label": "Stale", "url": None}]
        self.manager.register_tool(search_tool)

        self.manager.reset_sources()

        assert search_tool.last_sources == []
