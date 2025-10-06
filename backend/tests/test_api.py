"""
Integration tests for FastAPI endpoints in the RAG system.
"""

import pytest


@pytest.mark.integration
class TestQueryEndpoint:
    """Tests for /api/query endpoint"""

    def test_query_with_session_id(self, test_client, test_app, mock_rag_system):
        """Test querying with an existing session ID"""
        # Setup mock
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.query.return_value = (
            "Python is a programming language",
            [{"text": "Python documentation", "url": "https://docs.python.org"}],
        )

        # Make request
        response = test_client.post(
            "/api/query", json={"query": "What is Python?", "session_id": "existing-session-123"}
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Python is a programming language"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "Python documentation"
        assert data["session_id"] == "existing-session-123"

        # Verify RAG system was called correctly
        mock_rag_system.query.assert_called_once_with("What is Python?", "existing-session-123")

    def test_query_without_session_id_creates_new_session(
        self, test_client, test_app, mock_rag_system
    ):
        """Test that a new session is created when no session_id is provided"""
        # Setup mock
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.session_manager.create_session.return_value = "new-session-456"
        mock_rag_system.query.return_value = (
            "Answer to query",
            [{"text": "Source text", "url": "http://example.com"}],
        )

        # Make request without session_id
        response = test_client.post("/api/query", json={"query": "Tell me about RAG"})

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "new-session-456"
        assert data["answer"] == "Answer to query"

        # Verify session was created
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_query_with_empty_query(self, test_client, test_app, mock_rag_system):
        """Test querying with an empty query string"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.query.return_value = ("Empty query response", [])

        response = test_client.post("/api/query", json={"query": "", "session_id": "test-123"})

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Empty query response"
        assert data["sources"] == []

    def test_query_with_multiple_sources(self, test_client, test_app, mock_rag_system):
        """Test query response with multiple sources"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.query.return_value = (
            "Comprehensive answer",
            [
                {"text": "Source 1", "url": "http://example.com/1"},
                {"text": "Source 2", "url": "http://example.com/2"},
                {"text": "Source 3", "url": None},  # Source without URL
            ],
        )

        response = test_client.post(
            "/api/query", json={"query": "Complex question", "session_id": "test-123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) == 3
        assert data["sources"][0]["url"] == "http://example.com/1"
        assert data["sources"][2]["url"] is None

    def test_query_endpoint_handles_rag_system_error(self, test_client, test_app, mock_rag_system):
        """Test that RAG system errors are handled gracefully"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.query.side_effect = ValueError("RAG system error")

        response = test_client.post(
            "/api/query", json={"query": "Test query", "session_id": "test-123"}
        )

        assert response.status_code == 500
        assert "RAG system error" in response.json()["detail"]

    def test_query_endpoint_validates_request_schema(self, test_client):
        """Test that invalid request bodies are rejected"""
        # Missing required 'query' field
        response = test_client.post("/api/query", json={"session_id": "test-123"})

        assert response.status_code == 422  # Unprocessable Entity

    def test_query_with_long_query_text(self, test_client, test_app, mock_rag_system):
        """Test handling of very long query strings"""
        test_app.state.mock_rag_system = mock_rag_system
        long_query = "What is Python? " * 100  # Very long query
        mock_rag_system.query.return_value = ("Answer to long query", [])

        response = test_client.post(
            "/api/query", json={"query": long_query, "session_id": "test-123"}
        )

        assert response.status_code == 200
        # Verify long query was passed to RAG system
        mock_rag_system.query.assert_called_once()
        call_args = mock_rag_system.query.call_args[0]
        assert call_args[0] == long_query

    def test_query_with_special_characters(self, test_client, test_app, mock_rag_system):
        """Test queries containing special characters"""
        test_app.state.mock_rag_system = mock_rag_system
        special_query = "What is C++ & Python? (basics)"
        mock_rag_system.query.return_value = ("Answer with special chars", [])

        response = test_client.post(
            "/api/query", json={"query": special_query, "session_id": "test-123"}
        )

        assert response.status_code == 200
        mock_rag_system.query.assert_called_with(special_query, "test-123")

    def test_query_response_format_matches_schema(self, test_client, test_app, mock_rag_system):
        """Test that response matches QueryResponse model exactly"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.query.return_value = (
            "Test answer",
            [{"text": "Source", "url": "http://test.com"}],
        )

        response = test_client.post("/api/query", json={"query": "Test", "session_id": "test-123"})

        data = response.json()
        # Verify all required fields present
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        # Verify types
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)


@pytest.mark.integration
class TestCoursesEndpoint:
    """Tests for /api/courses endpoint"""

    def test_get_course_stats_success(self, test_client, test_app, mock_rag_system):
        """Test successful retrieval of course statistics"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 5,
            "course_titles": [
                "Python Basics",
                "Advanced Python",
                "Data Science",
                "Machine Learning",
                "Deep Learning",
            ],
        }

        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 5
        assert len(data["course_titles"]) == 5
        assert "Python Basics" in data["course_titles"]

    def test_get_course_stats_empty_database(self, test_client, test_app, mock_rag_system):
        """Test getting stats when no courses are loaded"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }

        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_get_course_stats_handles_error(self, test_client, test_app, mock_rag_system):
        """Test error handling when analytics retrieval fails"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.get_course_analytics.side_effect = Exception("Database connection error")

        response = test_client.get("/api/courses")

        assert response.status_code == 500
        assert "Database connection error" in response.json()["detail"]

    def test_course_stats_response_format(self, test_client, test_app, mock_rag_system):
        """Test that response matches CourseStats model"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": ["Course A", "Course B"],
        }

        response = test_client.get("/api/courses")

        data = response.json()
        # Verify schema
        assert "total_courses" in data
        assert "course_titles" in data
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)

    def test_course_stats_no_query_params_needed(self, test_client, test_app, mock_rag_system):
        """Test that endpoint works without query parameters"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 1,
            "course_titles": ["Test Course"],
        }

        # GET request without any parameters
        response = test_client.get("/api/courses")

        assert response.status_code == 200

    def test_course_stats_method_not_allowed(self, test_client):
        """Test that POST/PUT/DELETE are not allowed on courses endpoint"""
        # This endpoint should only accept GET requests
        response = test_client.post("/api/courses", json={})
        assert response.status_code == 405  # Method Not Allowed


@pytest.mark.integration
class TestCORSMiddleware:
    """Tests for CORS configuration"""

    def test_cors_headers_present(self, test_client, test_app, mock_rag_system):
        """Test that CORS headers are properly set"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.query.return_value = ("Answer", [])

        response = test_client.post(
            "/api/query", json={"query": "test"}, headers={"Origin": "http://localhost:3000"}
        )

        # Check CORS headers
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "*"

    def test_preflight_request(self, test_client):
        """Test CORS preflight OPTIONS request"""
        response = test_client.options(
            "/api/query",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


@pytest.mark.integration
class TestEndpointIntegration:
    """Integration tests combining multiple endpoints"""

    def test_query_then_get_stats_workflow(self, test_client, test_app, mock_rag_system):
        """Test typical workflow: query then check stats"""
        test_app.state.mock_rag_system = mock_rag_system

        # Setup mocks
        mock_rag_system.query.return_value = ("Answer", [])
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": ["Course 1", "Course 2", "Course 3"],
        }

        # First query
        query_response = test_client.post("/api/query", json={"query": "What is Python?"})
        assert query_response.status_code == 200

        # Then get stats
        stats_response = test_client.get("/api/courses")
        assert stats_response.status_code == 200
        assert stats_response.json()["total_courses"] == 3

    def test_multiple_queries_same_session(self, test_client, test_app, mock_rag_system):
        """Test multiple queries using the same session ID"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.query.return_value = ("Answer", [])

        session_id = "consistent-session-789"

        # First query
        response1 = test_client.post(
            "/api/query", json={"query": "First question", "session_id": session_id}
        )
        assert response1.json()["session_id"] == session_id

        # Second query with same session
        response2 = test_client.post(
            "/api/query", json={"query": "Second question", "session_id": session_id}
        )
        assert response2.json()["session_id"] == session_id

        # Verify RAG system was called twice with same session
        assert mock_rag_system.query.call_count == 2

    def test_concurrent_different_sessions(self, test_client, test_app, mock_rag_system):
        """Test handling multiple sessions concurrently"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.query.return_value = ("Answer", [])

        # Simulate concurrent requests with different sessions
        response1 = test_client.post(
            "/api/query", json={"query": "Query 1", "session_id": "session-1"}
        )
        response2 = test_client.post(
            "/api/query", json={"query": "Query 2", "session_id": "session-2"}
        )
        response3 = test_client.post(
            "/api/query", json={"query": "Query 3", "session_id": "session-3"}
        )

        assert response1.json()["session_id"] == "session-1"
        assert response2.json()["session_id"] == "session-2"
        assert response3.json()["session_id"] == "session-3"


@pytest.mark.integration
class TestErrorHandling:
    """Tests for error handling across endpoints"""

    def test_invalid_json_request(self, test_client):
        """Test handling of malformed JSON"""
        response = test_client.post(
            "/api/query", data="not valid json", headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_wrong_content_type(self, test_client):
        """Test handling of incorrect Content-Type header"""
        response = test_client.post(
            "/api/query",
            data="query=test",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # Should fail due to missing JSON body
        assert response.status_code == 422

    def test_nonexistent_endpoint(self, test_client):
        """Test accessing non-existent endpoint"""
        response = test_client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_extra_fields_in_request_ignored(self, test_client, test_app, mock_rag_system):
        """Test that extra fields in request are ignored (Pydantic behavior)"""
        test_app.state.mock_rag_system = mock_rag_system
        mock_rag_system.query.return_value = ("Answer", [])

        response = test_client.post(
            "/api/query",
            json={"query": "Test", "session_id": "test-123", "extra_field": "should be ignored"},
        )

        # Should succeed, extra field ignored
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
