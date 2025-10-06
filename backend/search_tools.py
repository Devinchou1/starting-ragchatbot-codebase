from abc import ABC, abstractmethod
from typing import Any

from vector_store import SearchResults, VectorStore


class Tool(ABC):
    """Abstract base class for all tools"""

    @abstractmethod
    def get_tool_definition(self) -> dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool with given parameters"""
        pass


class CourseSearchTool(Tool):
    """Tool for searching course content with semantic course name matching"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last search

    def get_tool_definition(self) -> dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "search_course_content",
            "description": "Search course materials with smart course name matching and lesson filtering",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in the course content",
                    },
                    "course_name": {
                        "type": "string",
                        "description": "Course title (partial matches work, e.g. 'MCP', 'Introduction')",
                    },
                    "lesson_number": {
                        "type": "integer",
                        "description": "Specific lesson number to search within (e.g. 1, 2, 3)",
                    },
                },
                "required": ["query"],
            },
        }

    def execute(
        self, query: str, course_name: str | None = None, lesson_number: int | None = None
    ) -> str:
        """
        Execute the search tool with given parameters.

        Args:
            query: What to search for
            course_name: Optional course filter
            lesson_number: Optional lesson filter

        Returns:
            Formatted search results or error message
        """

        # Use the vector store's unified search interface
        results = self.store.search(
            query=query, course_name=course_name, lesson_number=lesson_number
        )

        # Handle errors
        if results.error:
            return results.error

        # Handle empty results
        if results.is_empty():
            filter_info = ""
            if course_name:
                filter_info += f" in course '{course_name}'"
            if lesson_number:
                filter_info += f" in lesson {lesson_number}"
            return f"No relevant content found{filter_info}."

        # Format and return results
        return self._format_results(results)

    def _format_results(self, results: SearchResults) -> str:
        """Format search results with course and lesson context"""
        formatted = []
        sources = []  # Track sources for the UI with links

        for doc, meta in zip(results.documents, results.metadata, strict=False):
            course_title = meta.get("course_title", "unknown")
            lesson_num = meta.get("lesson_number")

            # Build context header
            header = f"[{course_title}"
            if lesson_num is not None:
                header += f" - Lesson {lesson_num}"
            header += "]"

            # Track source for the UI with lesson link
            source_text = course_title
            if lesson_num is not None:
                source_text += f" - Lesson {lesson_num}"

            # Get lesson link from vector store
            lesson_link = None
            if lesson_num is not None:
                lesson_link = self.store.get_lesson_link(course_title, lesson_num)

            # Store source as object with text and URL
            sources.append({"text": source_text, "url": lesson_link})

            formatted.append(f"{header}\n{doc}")

        # Store sources for retrieval
        self.last_sources = sources

        return "\n\n".join(formatted)


class CourseOutlineTool(Tool):
    """Tool for retrieving course outline with metadata and lesson list"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last outline request

    def get_tool_definition(self) -> dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "get_course_outline",
            "description": "Get comprehensive course outline including title, instructor, link, and complete lesson list with titles",
            "input_schema": {
                "type": "object",
                "properties": {
                    "course_name": {
                        "type": "string",
                        "description": "Course title or partial name (e.g. 'MCP', 'Introduction to Python')",
                    }
                },
                "required": ["course_name"],
            },
        }

    def execute(self, course_name: str) -> str:
        """
        Execute the course outline tool to retrieve course structure.

        Args:
            course_name: Course name or partial match

        Returns:
            Formatted course outline or error message
        """
        import json

        # Resolve course name to exact title
        course_title = self.store._resolve_course_name(course_name)

        if not course_title:
            return f"No course found matching '{course_name}'"

        # Retrieve course metadata from catalog
        try:
            results = self.store.course_catalog.get(ids=[course_title])

            if not results or not results.get("metadatas") or not results["metadatas"]:
                return f"Course '{course_title}' found but metadata unavailable"

            metadata = results["metadatas"][0]

            # Extract course information
            title = metadata.get("title", course_title)
            instructor = metadata.get("instructor", "N/A")
            course_link = metadata.get("course_link")
            lessons_json = metadata.get("lessons_json")

            # Parse lessons
            lessons = []
            if lessons_json:
                lessons = json.loads(lessons_json)

            # Format the outline
            outline = self._format_outline(title, instructor, course_link, lessons)

            # Store source for UI
            self.last_sources = [{"text": title, "url": course_link}]

            return outline

        except Exception as e:
            return f"Error retrieving course outline: {str(e)}"

    def _format_outline(
        self, title: str, instructor: str, course_link: str | None, lessons: list
    ) -> str:
        """Format course outline as readable text"""
        lines = []

        # Course header
        lines.append(f"**{title}**")
        lines.append(f"Instructor: {instructor}")

        if course_link:
            lines.append(f"Course Link: {course_link}")

        # Lesson list
        if lessons:
            lines.append(f"\n**Lessons ({len(lessons)} total):**")
            for lesson in lessons:
                lesson_num = lesson.get("lesson_number")
                lesson_title = lesson.get("lesson_title", "Untitled")
                lines.append(f"  Lesson {lesson_num}: {lesson_title}")
        else:
            lines.append("\nNo lessons available")

        return "\n".join(lines)


class ToolManager:
    """Manages available tools for the AI"""

    def __init__(self):
        self.tools = {}
        self.accumulated_sources = []  # Accumulate sources across multiple tool executions

    def register_tool(self, tool: Tool):
        """Register any tool that implements the Tool interface"""
        tool_def = tool.get_tool_definition()
        tool_name = tool_def.get("name")
        if not tool_name:
            raise ValueError("Tool must have a 'name' in its definition")
        self.tools[tool_name] = tool

    def get_tool_definitions(self) -> list:
        """Get all tool definitions for Anthropic tool calling"""
        return [tool.get_tool_definition() for tool in self.tools.values()]

    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a tool by name with given parameters and accumulate sources"""
        if tool_name not in self.tools:
            return f"Tool '{tool_name}' not found"

        result = self.tools[tool_name].execute(**kwargs)

        # Accumulate sources from this tool call
        if hasattr(self.tools[tool_name], "last_sources"):
            tool_sources = self.tools[tool_name].last_sources
            if tool_sources:
                self.accumulated_sources.extend(tool_sources)

        return result

    def get_last_sources(self) -> list:
        """Get accumulated sources from all tool executions"""
        return self.accumulated_sources

    def reset_sources(self):
        """Reset accumulated sources and individual tool sources"""
        self.accumulated_sources = []
        for tool in self.tools.values():
            if hasattr(tool, "last_sources"):
                tool.last_sources = []
