import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive search and outline tools.

Tool Usage Guidelines:
- **Available tools**: `get_course_outline` (course structure/lessons), `search_course_content` (specific topics/details)
- **Tool call budget**: You may use up to 2 rounds of tool calling per query
- **Strategic approach**:
  - **Course outline queries**: Use `get_course_outline` for questions about course structure, lesson lists, or general course information
  - **Content search queries**: Use `search_course_content` for questions about specific topics, concepts, or lesson details
  - **Complex queries**: You can chain tools across rounds:
    - Example 1: Get outline first → then search specific lesson content
    - Example 2: Search one course → then search another for comparison
    - Example 3: Broad search → refine with more specific parameters
- **General knowledge**: Answer using existing knowledge without tools
- Synthesize tool results into accurate, fact-based responses
- If tools yield no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course outline questions**: Get outline first, then answer (chain to search if needed)
- **Course-specific questions**: Search first (refine if needed), then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results" or "based on the outline"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str, max_tool_rounds: int = 2):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tool_rounds = max_tool_rounds
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional sequential tool usage and conversation context.

        Supports up to MAX_TOOL_ROUNDS of sequential tool calling where Claude can:
        - Use tools in round 1, see results, then use tools again in round 2
        - Refine searches based on initial results
        - Combine information from multiple tool calls

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Initialize message history with user query
        messages = [{"role": "user", "content": query}]

        # Prepare base API call parameters
        api_params = {
            **self.base_params,
            "system": system_content
        }

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        # Sequential tool calling loop
        for round_num in range(1, self.max_tool_rounds + 1):
            # Make API call with current message history
            response = self.client.messages.create(
                **api_params,
                messages=messages
            )

            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use" and tool_manager:
                # Execute tools and accumulate results in messages
                has_error = self._execute_and_accumulate_tools(
                    response, messages, tool_manager
                )

                # If tool error occurred, make final call to let Claude respond to error
                if has_error:
                    final_response = self.client.messages.create(
                        **api_params,
                        messages=messages
                    )
                    return self._extract_text_response(final_response)

                # Continue to next round if within MAX_TOOL_ROUNDS
                continue

            else:
                # Claude provided a final text response (no tool use) or unexpected stop_reason
                return self._extract_text_response(response)

        # MAX_ROUNDS exhausted - make final API call WITHOUT tools
        # This ensures Claude provides a text answer instead of more tool calls
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content
            # Note: No tools parameter
        }

        final_response = self.client.messages.create(**final_params)
        return self._extract_text_response(final_response)

    def _execute_and_accumulate_tools(self, response, messages: List[Dict], tool_manager) -> bool:
        """
        Execute all tool calls from response and accumulate results in messages array.

        Args:
            response: API response containing tool_use blocks
            messages: Message array to accumulate into (modified in place)
            tool_manager: Manager to execute tools

        Returns:
            bool: True if any tool execution had an error, False otherwise
        """
        # Accumulate assistant's tool use message
        messages.append({
            "role": "assistant",
            "content": response.content  # Contains tool_use blocks
        })

        # Execute all requested tools
        tool_results = []
        has_error = False

        for content_block in response.content:
            if content_block.type == "tool_use":
                try:
                    tool_result = tool_manager.execute_tool(
                        content_block.name,
                        **content_block.input
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result
                    })

                except Exception as e:
                    # Tool execution failed - return error to Claude
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": f"Error executing tool: {str(e)}",
                        "is_error": True
                    })
                    has_error = True

        # Accumulate tool results
        messages.append({
            "role": "user",
            "content": tool_results
        })

        return has_error

    def _extract_text_response(self, response) -> str:
        """
        Extract text content from response, handling mixed content blocks.

        In tool calling scenarios, response.content may contain:
        - [TextBlock] - normal text response
        - [TextBlock, ToolUseBlock] - text + tool call
        - [ToolUseBlock] - only tool calls (should not happen at final response)

        Args:
            response: API response object

        Returns:
            Extracted text content as string
        """
        text_parts = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)

        return "".join(text_parts) if text_parts else ""