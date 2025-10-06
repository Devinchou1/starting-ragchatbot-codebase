"""
Pytest configuration and shared fixtures for RAG system tests.
"""

import os
import sys
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ============================================================================
# TEST APP FIXTURES
# ============================================================================


@pytest.fixture
def test_app():
    """
    Create a test FastAPI app with only API endpoints (no static file mounting).
    This avoids dependency on frontend files during testing.
    """
    from fastapi import HTTPException
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="Course Materials RAG System - Test")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Define request/response models inline
    class QueryRequest(BaseModel):
        query: str
        session_id: str | None = None

    class QueryResponse(BaseModel):
        answer: str
        sources: list[dict[str, str | None]]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: list[str]

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            # Access RAG system from app.state (set by tests)
            rag_system = app.state.mock_rag_system
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()

            answer, sources = rag_system.query(request.query, session_id)

            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            # Access RAG system from app.state (set by tests)
            rag_system = app.state.mock_rag_system
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"], course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Initialize with a default mock (will be replaced by test fixtures)
    app.state.mock_rag_system = Mock()

    return app


@pytest.fixture
def test_client(test_app):
    """FastAPI test client"""
    return TestClient(test_app)


# ============================================================================
# MOCK RAG SYSTEM FIXTURES
# ============================================================================


@pytest.fixture
def mock_rag_system():
    """Mock RAGSystem with common default behaviors"""
    rag_system = Mock()

    # Default query behavior
    rag_system.query.return_value = (
        "This is a test answer",
        [{"text": "Source 1", "url": "http://example.com"}],
    )

    # Default analytics behavior
    rag_system.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course 1", "Course 2"],
    }

    # Mock session manager
    rag_system.session_manager = Mock()
    rag_system.session_manager.create_session.return_value = "test-session-123"

    return rag_system


@pytest.fixture
def mock_vector_store():
    """Mock VectorStore for testing search functionality"""
    vector_store = Mock()

    # Default search behavior
    vector_store.search.return_value = [
        {
            "text": "Sample course content",
            "metadata": {"course_title": "Test Course", "lesson_number": 1},
            "distance": 0.1,
        }
    ]

    vector_store.get_all_course_titles.return_value = ["Course 1", "Course 2"]

    return vector_store


@pytest.fixture
def mock_ai_generator():
    """Mock AIGenerator for testing response generation"""
    generator = Mock()
    generator.generate_response.return_value = "Generated AI response"
    return generator


@pytest.fixture
def mock_tool_manager():
    """Mock ToolManager for testing tool execution"""
    manager = Mock()
    manager.execute_tool.return_value = "Tool execution result"
    manager.get_tool_definitions.return_value = [
        {
            "name": "search_course_content",
            "description": "Search for course content",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        }
    ]
    return manager


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================


@pytest.fixture
def sample_query_request():
    """Sample query request data"""
    return {"query": "What is Python?", "session_id": "test-session-123"}


@pytest.fixture
def sample_query_response():
    """Sample query response data"""
    return {
        "answer": "Python is a high-level programming language.",
        "sources": [{"text": "Python basics from Lesson 1", "url": "http://example.com/lesson1"}],
        "session_id": "test-session-123",
    }


@pytest.fixture
def sample_course_stats():
    """Sample course statistics data"""
    return {
        "total_courses": 3,
        "course_titles": ["Python Basics", "Advanced Python", "Data Science"],
    }


# ============================================================================
# ANTHROPIC API MOCK FIXTURES
# ============================================================================


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic API client"""
    client = Mock()

    # Mock message response
    mock_response = Mock()
    mock_response.stop_reason = "end_turn"

    text_block = Mock()
    text_block.type = "text"
    text_block.text = "Mocked AI response"
    mock_response.content = [text_block]

    client.messages.create.return_value = mock_response

    return client


@pytest.fixture
def mock_tool_use_response():
    """Mock Anthropic API response with tool use"""
    response = Mock()
    response.stop_reason = "tool_use"

    tool_block = Mock()
    tool_block.type = "tool_use"
    tool_block.id = "toolu_test123"
    tool_block.name = "search_course_content"
    tool_block.input = {"query": "test query"}

    response.content = [tool_block]

    return response


@pytest.fixture
def mock_text_response():
    """Mock Anthropic API response with text only"""
    response = Mock()
    response.stop_reason = "end_turn"

    text_block = Mock()
    text_block.type = "text"
    text_block.text = "This is a text response"

    response.content = [text_block]

    return response


# ============================================================================
# ENVIRONMENT FIXTURES
# ============================================================================


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set mock environment variables for testing"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key-123")
    monkeypatch.setenv("CHROMA_PATH", "./test_chroma_db")


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
def cleanup_test_artifacts():
    """Auto-cleanup fixture that runs after each test"""
    yield
    # Cleanup code can go here if needed
    # For example, removing test database files
