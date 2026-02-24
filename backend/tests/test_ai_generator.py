"""
Tests for AIGenerator (ai_generator.py).

Verifies:
  1. Direct (non-tool) response path
  2. Tool-use two-pass flow – tool call dispatched, result sent back
  3. API parameter construction (tools, tool_choice, system prompt, messages)
  4. Latent bug: tool_use response with no tool_manager hits AttributeError
"""

import pytest
from unittest.mock import MagicMock, patch, call

# conftest.py has already mocked 'anthropic' and added backend/ to sys.path.
from ai_generator import AIGenerator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_text_block(text="Answer text"):
    """Simulate a real Anthropic TextBlock (has .type and .text)."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def make_tool_use_block(
    tool_name="search_course_content", inputs=None, tool_id="toolu_01"
):
    """Simulate a real Anthropic ToolUseBlock (has .type, .name, .id, .input)."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.id = tool_id
    block.input = inputs or {"query": "test query"}
    return block


class RealToolUseBlock:
    """
    A real Python object – NOT a MagicMock – that mimics an Anthropic tool_use
    content block.  It deliberately has NO '.text' attribute so that accessing
    .text raises AttributeError (just like the real Anthropic SDK object).
    """

    type = "tool_use"
    id = "toolu_real"
    name = "search_course_content"
    input = {"query": "test"}


def api_response(stop_reason="end_turn", content_blocks=None):
    """Build a mock Anthropic Messages response."""
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = content_blocks or [make_text_block()]
    return resp


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def gen():
    """Return an AIGenerator whose Anthropic client is fully mocked."""
    generator = AIGenerator(api_key="test-key", model="test-model")
    generator.client = MagicMock()
    return generator


# ---------------------------------------------------------------------------
# Direct response (no tool use)
# ---------------------------------------------------------------------------


class TestDirectResponse:

    def test_returns_text_from_first_response(self, gen):
        gen.client.messages.create.return_value = api_response(
            stop_reason="end_turn",
            content_blocks=[make_text_block("Paris is the capital of France.")],
        )

        result = gen.generate_response(query="What is the capital of France?")

        assert result == "Paris is the capital of France."

    def test_only_one_api_call_when_no_tool_use(self, gen):
        gen.client.messages.create.return_value = api_response(stop_reason="end_turn")

        gen.generate_response(query="test")

        assert gen.client.messages.create.call_count == 1

    def test_query_sent_as_user_message(self, gen):
        gen.client.messages.create.return_value = api_response(stop_reason="end_turn")

        gen.generate_response(query="My specific question")

        kwargs = gen.client.messages.create.call_args.kwargs
        messages = kwargs["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "My specific question"

    def test_system_prompt_present_in_api_call(self, gen):
        gen.client.messages.create.return_value = api_response(stop_reason="end_turn")

        gen.generate_response(query="test")

        kwargs = gen.client.messages.create.call_args.kwargs
        assert "system" in kwargs
        assert len(kwargs["system"]) > 0

    def test_conversation_history_appended_to_system_prompt(self, gen):
        gen.client.messages.create.return_value = api_response(stop_reason="end_turn")
        history = "User: previous question\nAssistant: previous answer"

        gen.generate_response(query="follow-up", conversation_history=history)

        kwargs = gen.client.messages.create.call_args.kwargs
        assert history in kwargs["system"]

    def test_no_history_system_prompt_is_base_only(self, gen):
        gen.client.messages.create.return_value = api_response(stop_reason="end_turn")

        gen.generate_response(query="test")

        kwargs = gen.client.messages.create.call_args.kwargs
        # System prompt should equal the static SYSTEM_PROMPT with no history appended
        assert kwargs["system"] == gen.SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# API parameter construction for tools
# ---------------------------------------------------------------------------


class TestToolParameters:

    def test_tools_added_when_provided(self, gen):
        gen.client.messages.create.return_value = api_response(stop_reason="end_turn")
        tools = [{"name": "search_course_content", "input_schema": {}}]

        gen.generate_response(query="q", tools=tools)

        kwargs = gen.client.messages.create.call_args.kwargs
        assert "tools" in kwargs
        assert kwargs["tools"] == tools

    def test_tool_choice_auto_when_tools_provided(self, gen):
        gen.client.messages.create.return_value = api_response(stop_reason="end_turn")

        gen.generate_response(query="q", tools=[{"name": "any"}])

        kwargs = gen.client.messages.create.call_args.kwargs
        assert kwargs.get("tool_choice") == {"type": "auto"}

    def test_tools_absent_from_params_when_not_provided(self, gen):
        gen.client.messages.create.return_value = api_response(stop_reason="end_turn")

        gen.generate_response(query="q")

        kwargs = gen.client.messages.create.call_args.kwargs
        assert "tools" not in kwargs
        assert "tool_choice" not in kwargs

    def test_empty_tools_list_treated_as_falsy(self, gen):
        """An empty tools list should not add tools/tool_choice to the call."""
        gen.client.messages.create.return_value = api_response(stop_reason="end_turn")

        gen.generate_response(query="q", tools=[])

        kwargs = gen.client.messages.create.call_args.kwargs
        assert "tools" not in kwargs


# ---------------------------------------------------------------------------
# Two-pass tool-use flow
# ---------------------------------------------------------------------------


class TestToolUseFlow:

    def test_two_api_calls_when_tool_use(self, gen):
        tool_block = make_tool_use_block()
        first = api_response("tool_use", [tool_block])
        second = api_response("end_turn", [make_text_block("Final answer")])
        gen.client.messages.create.side_effect = [first, second]

        mock_tm = MagicMock()
        mock_tm.execute_tool.return_value = "Vector store results"

        gen.generate_response(
            query="q", tools=[{"name": "search_course_content"}], tool_manager=mock_tm
        )

        assert gen.client.messages.create.call_count == 2

    def test_final_answer_text_returned(self, gen):
        tool_block = make_tool_use_block()
        first = api_response("tool_use", [tool_block])
        second = api_response("end_turn", [make_text_block("Final synthesized answer")])
        gen.client.messages.create.side_effect = [first, second]

        mock_tm = MagicMock()
        mock_tm.execute_tool.return_value = "results"

        result = gen.generate_response(query="q", tools=[{}], tool_manager=mock_tm)

        assert result == "Final synthesized answer"

    def test_tool_manager_execute_called_with_correct_name_and_inputs(self, gen):
        tool_block = make_tool_use_block(
            tool_name="search_course_content",
            inputs={"query": "what is RAG?", "course_name": "RAG Course"},
        )
        first = api_response("tool_use", [tool_block])
        second = api_response("end_turn", [make_text_block("Answer")])
        gen.client.messages.create.side_effect = [first, second]

        mock_tm = MagicMock()
        mock_tm.execute_tool.return_value = "Tool output"

        gen.generate_response(query="q", tools=[{}], tool_manager=mock_tm)

        mock_tm.execute_tool.assert_called_once_with(
            "search_course_content",
            query="what is RAG?",
            course_name="RAG Course",
        )

    def test_second_call_messages_contain_tool_result(self, gen):
        tool_block = make_tool_use_block(tool_id="toolu_abc")
        first = api_response("tool_use", [tool_block])
        second = api_response("end_turn", [make_text_block("Done")])
        gen.client.messages.create.side_effect = [first, second]

        mock_tm = MagicMock()
        mock_tm.execute_tool.return_value = "The search results"

        gen.generate_response(query="q", tools=[{}], tool_manager=mock_tm)

        second_kwargs = gen.client.messages.create.call_args_list[1].kwargs
        messages = second_kwargs["messages"]
        # [user query, assistant tool_use, user tool_result]
        assert len(messages) == 3
        last = messages[-1]
        assert last["role"] == "user"
        content = last["content"]
        assert content[0]["type"] == "tool_result"
        assert content[0]["tool_use_id"] == "toolu_abc"
        assert content[0]["content"] == "The search results"

    def test_final_call_excludes_tools_and_tool_choice(self, gen):
        """The second Claude call must NOT include tools – it should synthesise only."""
        tool_block = make_tool_use_block()
        first = api_response("tool_use", [tool_block])
        second = api_response("end_turn", [make_text_block("Answer")])
        gen.client.messages.create.side_effect = [first, second]

        mock_tm = MagicMock()
        mock_tm.execute_tool.return_value = "results"

        gen.generate_response(
            query="q", tools=[{"name": "search_course_content"}], tool_manager=mock_tm
        )

        second_kwargs = gen.client.messages.create.call_args_list[1].kwargs
        assert "tools" not in second_kwargs
        assert "tool_choice" not in second_kwargs


# ---------------------------------------------------------------------------
# Latent bug: tool_use response with no tool_manager
# ---------------------------------------------------------------------------


class TestToolUseWithoutToolManager:

    def test_raises_clear_error_when_tool_use_but_no_tool_manager(self, gen):
        """
        When Claude requests a tool call (stop_reason='tool_use') but no
        tool_manager was supplied, generate_response() must raise a clear
        ValueError rather than falling through to response.content[0].text
        (which would raise an opaque AttributeError on a real ToolUseBlock).
        """
        response = MagicMock()
        response.stop_reason = "tool_use"
        response.content = [RealToolUseBlock()]  # no .text attribute
        gen.client.messages.create.return_value = response

        with pytest.raises(ValueError, match="tool_manager"):
            # tool_manager intentionally omitted
            gen.generate_response(query="q", tools=[{"name": "search_course_content"}])
