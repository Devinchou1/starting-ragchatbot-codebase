import os
import sys
from unittest.mock import Mock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai_generator import AIGenerator


@pytest.mark.unit
class TestSequentialToolCalling:
    """Tests for multi-round sequential tool calling behavior"""

    @pytest.fixture
    def mock_client(self):
        """Mock Anthropic client"""
        return Mock()

    @pytest.fixture
    def mock_tool_manager(self):
        """Mock tool manager"""
        manager = Mock()
        manager.execute_tool.return_value = "Tool result content"
        return manager

    @pytest.fixture
    def ai_generator(self, mock_client):
        """AIGenerator with mocked client"""
        gen = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514", max_tool_rounds=2)
        gen.client = mock_client
        return gen

    # === Test 1: No Tool Usage ===
    def test_no_tool_usage_single_call(self, ai_generator, mock_client):
        """Test that non-tool queries make only 1 API call"""
        # Mock response with text, no tool_use
        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        text_block = Mock()
        text_block.type = "text"
        text_block.text = "Direct answer"
        mock_response.content = [text_block]
        mock_client.messages.create.return_value = mock_response

        result = ai_generator.generate_response(
            query="What is Python?", tools=[{"name": "search"}], tool_manager=Mock()
        )

        assert result == "Direct answer"
        assert mock_client.messages.create.call_count == 1

    # === Test 2: Single Round Tool Usage ===
    def test_single_round_tool_usage(self, ai_generator, mock_client, mock_tool_manager):
        """Test 1 tool call → final answer (2 API calls total)"""
        # Round 1: Tool use
        tool_use_response = Mock()
        tool_use_response.stop_reason = "tool_use"
        tool_use_block = Mock()
        tool_use_block.type = "tool_use"
        tool_use_block.id = "toolu_123"
        tool_use_block.name = "search"
        tool_use_block.input = {"query": "test"}
        tool_use_response.content = [tool_use_block]

        # Round 2: Final answer
        final_response = Mock()
        final_response.stop_reason = "end_turn"
        text_block = Mock()
        text_block.type = "text"
        text_block.text = "Final answer"
        final_response.content = [text_block]

        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        result = ai_generator.generate_response(
            query="Search for something", tools=[{"name": "search"}], tool_manager=mock_tool_manager
        )

        assert result == "Final answer"
        assert mock_client.messages.create.call_count == 2
        assert mock_tool_manager.execute_tool.call_count == 1

    # === Test 3: Two Rounds Tool Usage ===
    def test_two_round_tool_usage(self, ai_generator, mock_client, mock_tool_manager):
        """Test 2 sequential tool calls → final answer (3 API calls)"""
        # Round 1: First tool use
        tool_use_1 = Mock()
        tool_use_1.stop_reason = "tool_use"
        tool_block_1 = Mock()
        tool_block_1.type = "tool_use"
        tool_block_1.id = "toolu_1"
        tool_block_1.name = "get_outline"
        tool_block_1.input = {"course": "Python"}
        tool_use_1.content = [tool_block_1]

        # Round 2: Second tool use
        tool_use_2 = Mock()
        tool_use_2.stop_reason = "tool_use"
        tool_block_2 = Mock()
        tool_block_2.type = "tool_use"
        tool_block_2.id = "toolu_2"
        tool_block_2.name = "search_content"
        tool_block_2.input = {"query": "functions"}
        tool_use_2.content = [tool_block_2]

        # Round 3: Final answer
        final = Mock()
        final.stop_reason = "end_turn"
        text_block = Mock()
        text_block.type = "text"
        text_block.text = "Comprehensive answer"
        final.content = [text_block]

        mock_client.messages.create.side_effect = [tool_use_1, tool_use_2, final]

        result = ai_generator.generate_response(
            query="Complex query", tools=[{"name": "search"}], tool_manager=mock_tool_manager
        )

        assert result == "Comprehensive answer"
        assert mock_client.messages.create.call_count == 3
        assert mock_tool_manager.execute_tool.call_count == 2

    # === Test 4: MAX_ROUNDS Limit Enforcement ===
    def test_max_rounds_enforced(self, ai_generator, mock_client, mock_tool_manager):
        """Test that after 2 rounds, a final call WITHOUT tools is made"""
        # Rounds 1 & 2: Tool use
        tool_use_response = Mock()
        tool_use_response.stop_reason = "tool_use"
        tool_block = Mock()
        tool_block.type = "tool_use"
        tool_block.id = "toolu_1"
        tool_block.name = "search"
        tool_block.input = {"query": "search_1"}
        tool_use_response.content = [tool_block]

        # Final call (without tools): Text response
        final_response = Mock()
        final_response.stop_reason = "end_turn"
        text_block = Mock()
        text_block.type = "text"
        text_block.text = "Forced final answer"
        final_response.content = [text_block]

        mock_client.messages.create.side_effect = [
            tool_use_response,  # Round 1
            tool_use_response,  # Round 2
            final_response,  # Final call without tools
        ]

        result = ai_generator.generate_response(
            query="Query", tools=[{"name": "search"}], tool_manager=mock_tool_manager
        )

        assert result == "Forced final answer"
        assert mock_client.messages.create.call_count == 3

        # Verify final call had NO tools
        final_call_kwargs = mock_client.messages.create.call_args_list[2][1]
        assert "tools" not in final_call_kwargs

    # === Test 5: Tool Execution Error Handling ===
    def test_tool_error_graceful_handling(self, ai_generator, mock_client, mock_tool_manager):
        """Test that tool errors are passed to Claude as error results"""
        # Round 1: Tool use
        tool_use = Mock()
        tool_use.stop_reason = "tool_use"
        tool_block = Mock()
        tool_block.type = "tool_use"
        tool_block.id = "toolu_err"
        tool_block.name = "failing_tool"
        tool_block.input = {}
        tool_use.content = [tool_block]

        # Tool execution raises error
        mock_tool_manager.execute_tool.side_effect = ValueError("Tool failed")

        # Final response after error
        final = Mock()
        final.stop_reason = "end_turn"
        text_block = Mock()
        text_block.type = "text"
        text_block.text = "Error explanation"
        final.content = [text_block]

        mock_client.messages.create.side_effect = [tool_use, final]

        result = ai_generator.generate_response(
            query="Query", tools=[{"name": "test"}], tool_manager=mock_tool_manager
        )

        assert result == "Error explanation"

        # Verify error was sent to Claude
        second_call_kwargs = mock_client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]

        # Last message should contain error
        error_msg = messages[-1]["content"][0]
        assert error_msg["type"] == "tool_result"
        assert error_msg["is_error"]
        assert "Tool failed" in error_msg["content"]

    # === Test 6: Message History Accumulation ===
    def test_message_history_accumulation(self, ai_generator, mock_client, mock_tool_manager):
        """Test that messages accumulate correctly across rounds"""
        # Setup responses
        tool_use = Mock()
        tool_use.stop_reason = "tool_use"
        tool_block = Mock()
        tool_block.type = "tool_use"
        tool_block.id = "t1"
        tool_block.name = "search"
        tool_block.input = {}
        tool_use.content = [tool_block]

        final = Mock()
        final.stop_reason = "end_turn"
        text_block = Mock()
        text_block.type = "text"
        text_block.text = "Answer"
        final.content = [text_block]

        mock_client.messages.create.side_effect = [tool_use, final]

        ai_generator.generate_response(
            query="Test query", tools=[{"name": "search"}], tool_manager=mock_tool_manager
        )

        # Check second API call's messages
        second_call = mock_client.messages.create.call_args_list[1][1]
        messages = second_call["messages"]

        # Should have: user query → assistant tool_use → user tool_result
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"][0]["type"] == "tool_result"

    # === Test 7: Natural Termination Before Limit ===
    def test_natural_termination_before_max_rounds(
        self, ai_generator, mock_client, mock_tool_manager
    ):
        """Test that Claude can answer after 1 round without using full budget"""
        # Round 1: Tool use
        tool_use = Mock()
        tool_use.stop_reason = "tool_use"
        tool_block = Mock()
        tool_block.type = "tool_use"
        tool_block.id = "t1"
        tool_block.name = "search"
        tool_block.input = {}
        tool_use.content = [tool_block]

        # Round 2: Claude answers directly (no more tools needed)
        final = Mock()
        final.stop_reason = "end_turn"
        text_block = Mock()
        text_block.type = "text"
        text_block.text = "Answer after 1 tool call"
        final.content = [text_block]

        mock_client.messages.create.side_effect = [tool_use, final]

        result = ai_generator.generate_response(
            query="Simple query", tools=[{"name": "search"}], tool_manager=mock_tool_manager
        )

        assert result == "Answer after 1 tool call"
        # Should be exactly 2 calls (not 3), no synthesis needed
        assert mock_client.messages.create.call_count == 2

    # === Test 8: Extract Text From Mixed Content ===
    def test_extract_text_from_mixed_content(self, ai_generator):
        """Test _extract_text_response handles mixed content blocks"""
        # Mock response with text blocks
        response = Mock()
        text_block_1 = Mock()
        text_block_1.type = "text"
        text_block_1.text = "Part 1. "

        text_block_2 = Mock()
        text_block_2.type = "text"
        text_block_2.text = "Part 2."

        # Non-text block should be ignored
        tool_block = Mock()
        tool_block.type = "tool_use"

        response.content = [text_block_1, tool_block, text_block_2]

        result = ai_generator._extract_text_response(response)
        assert result == "Part 1. Part 2."

    # === Test 9: Empty Content Handling ===
    def test_extract_text_empty_content(self, ai_generator):
        """Test _extract_text_response handles empty/no text blocks"""
        response = Mock()
        tool_block = Mock()
        tool_block.type = "tool_use"
        response.content = [tool_block]  # No text blocks

        result = ai_generator._extract_text_response(response)
        assert result == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
