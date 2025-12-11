"""Tests for fetchers module."""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import requests
import responses

from langsmith_cli import fetchers
from tests.conftest import (
    TEST_API_KEY,
    TEST_BASE_URL,
    TEST_PROJECT_UUID,
    TEST_THREAD_ID,
    TEST_TRACE_ID,
)


class TestFetchTrace:
    """Tests for fetch_trace function."""

    @responses.activate
    def test_fetch_trace_success(self, sample_trace_response):
        """Test successful trace fetching."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        messages = fetchers.fetch_trace(
            TEST_TRACE_ID, base_url=TEST_BASE_URL, api_key=TEST_API_KEY
        )

        assert isinstance(messages, list)
        assert len(messages) == 3
        assert messages[0]["type"] == "human"
        assert "jane@example.com" in messages[0]["content"]

    @responses.activate
    def test_fetch_trace_not_found(self):
        """Test fetch_trace with 404 error."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json={"error": "Not found"},
            status=404,
        )

        with pytest.raises(requests.HTTPError):
            fetchers.fetch_trace(
                TEST_TRACE_ID, base_url=TEST_BASE_URL, api_key=TEST_API_KEY
            )

    @responses.activate
    def test_fetch_trace_api_key_sent(self, sample_trace_response):
        """Test that API key is sent in headers."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        fetchers.fetch_trace(
            TEST_TRACE_ID, base_url=TEST_BASE_URL, api_key=TEST_API_KEY
        )

        # Check that the request was made with correct headers
        assert len(responses.calls) == 1
        assert responses.calls[0].request.headers["X-API-Key"] == TEST_API_KEY


class TestFetchThread:
    """Tests for fetch_thread function."""

    @responses.activate
    def test_fetch_thread_success(self, sample_thread_response):
        """Test successful thread fetching."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
            json=sample_thread_response,
            status=200,
        )

        messages = fetchers.fetch_thread(
            TEST_THREAD_ID,
            TEST_PROJECT_UUID,
            base_url=TEST_BASE_URL,
            api_key=TEST_API_KEY,
        )

        assert isinstance(messages, list)
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert "jane@example.com" in messages[0]["content"]

    @responses.activate
    def test_fetch_thread_params_sent(self, sample_thread_response):
        """Test that correct params are sent in thread request."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
            json=sample_thread_response,
            status=200,
        )

        fetchers.fetch_thread(
            TEST_THREAD_ID,
            TEST_PROJECT_UUID,
            base_url=TEST_BASE_URL,
            api_key=TEST_API_KEY,
        )

        # Check that the request was made with correct params
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.headers["X-API-Key"] == TEST_API_KEY
        # Check query params
        assert "select=all_messages" in request.url
        assert f"session_id={TEST_PROJECT_UUID}" in request.url

    @responses.activate
    def test_fetch_thread_not_found(self):
        """Test fetch_thread with 404 error."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
            json={"error": "Not found"},
            status=404,
        )

        with pytest.raises(requests.HTTPError):
            fetchers.fetch_thread(
                TEST_THREAD_ID,
                TEST_PROJECT_UUID,
                base_url=TEST_BASE_URL,
                api_key=TEST_API_KEY,
            )

    @responses.activate
    def test_fetch_thread_parses_multiline_json(self, sample_thread_response):
        """Test that thread fetcher correctly parses newline-separated JSON."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
            json=sample_thread_response,
            status=200,
        )

        messages = fetchers.fetch_thread(
            TEST_THREAD_ID,
            TEST_PROJECT_UUID,
            base_url=TEST_BASE_URL,
            api_key=TEST_API_KEY,
        )

        # Should have parsed all messages from newline-separated format
        assert len(messages) == 3
        # Each message should be a valid dict
        for msg in messages:
            assert isinstance(msg, dict)
            assert "role" in msg or "type" in msg


class TestFetchLatestTrace:
    """Tests for fetch_latest_trace function."""

    @responses.activate
    @patch("langsmith.Client")
    def test_fetch_latest_trace_success(self, mock_client_class, sample_trace_response):
        """Test successful latest trace fetching."""
        # Mock the Client and its list_runs method
        mock_client = Mock()
        mock_run = Mock()
        mock_run.id = TEST_TRACE_ID
        mock_client.list_runs.return_value = [mock_run]
        mock_client_class.return_value = mock_client

        # Mock the REST API call for fetch_trace
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        messages = fetchers.fetch_latest_trace(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL
        )

        # Verify Client was instantiated with correct API key
        mock_client_class.assert_called_once_with(api_key=TEST_API_KEY)

        # Verify list_runs was called with correct parameters
        mock_client.list_runs.assert_called_once()
        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs["filter"] == 'and(eq(is_root, true), neq(status, "pending"))'
        assert call_kwargs["limit"] == 1

        # Verify the messages were fetched correctly
        assert isinstance(messages, list)
        assert len(messages) == 3

    @patch("langsmith.Client")
    def test_fetch_latest_trace_no_traces_found(self, mock_client_class):
        """Test fetch_latest_trace when no traces are found."""
        # Mock empty list_runs result
        mock_client = Mock()
        mock_client.list_runs.return_value = []
        mock_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="No traces found matching criteria"):
            fetchers.fetch_latest_trace(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)

    @responses.activate
    @patch("langsmith.Client")
    def test_fetch_latest_trace_with_project_uuid(
        self, mock_client_class, sample_trace_response
    ):
        """Test latest trace fetching with project UUID filter."""
        # Mock the Client
        mock_client = Mock()
        mock_run = Mock()
        mock_run.id = TEST_TRACE_ID
        mock_client.list_runs.return_value = [mock_run]
        mock_client_class.return_value = mock_client

        # Mock the REST API call
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        messages = fetchers.fetch_latest_trace(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL, project_uuid=TEST_PROJECT_UUID
        )

        # Verify list_runs was called with project_id
        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs["project_id"] == TEST_PROJECT_UUID
        assert call_kwargs["filter"] == 'and(eq(is_root, true), neq(status, "pending"))'
        assert call_kwargs["limit"] == 1

        assert isinstance(messages, list)

    @responses.activate
    @patch("langsmith.Client")
    def test_fetch_latest_trace_with_time_window(
        self, mock_client_class, sample_trace_response
    ):
        """Test latest trace fetching with last_n_minutes filter."""
        # Mock the Client
        mock_client = Mock()
        mock_run = Mock()
        mock_run.id = TEST_TRACE_ID
        mock_client.list_runs.return_value = [mock_run]
        mock_client_class.return_value = mock_client

        # Mock the REST API call
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        messages = fetchers.fetch_latest_trace(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL, last_n_minutes=30
        )

        # Verify list_runs was called with start_time
        call_kwargs = mock_client.list_runs.call_args[1]
        assert "start_time" in call_kwargs
        assert isinstance(call_kwargs["start_time"], datetime)
        assert call_kwargs["filter"] == 'and(eq(is_root, true), neq(status, "pending"))'

        assert isinstance(messages, list)

    @responses.activate
    @patch("langsmith.Client")
    def test_fetch_latest_trace_with_since_timestamp(
        self, mock_client_class, sample_trace_response
    ):
        """Test latest trace fetching with since timestamp filter."""
        # Mock the Client
        mock_client = Mock()
        mock_run = Mock()
        mock_run.id = TEST_TRACE_ID
        mock_client.list_runs.return_value = [mock_run]
        mock_client_class.return_value = mock_client

        # Mock the REST API call
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        since_timestamp = "2025-12-09T10:00:00Z"
        messages = fetchers.fetch_latest_trace(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL, since=since_timestamp
        )

        # Verify list_runs was called with start_time
        call_kwargs = mock_client.list_runs.call_args[1]
        assert "start_time" in call_kwargs
        assert isinstance(call_kwargs["start_time"], datetime)
        assert call_kwargs["filter"] == 'and(eq(is_root, true), neq(status, "pending"))'

        assert isinstance(messages, list)

    @responses.activate
    @patch("langsmith.Client")
    def test_fetch_latest_trace_without_project_uuid(
        self, mock_client_class, sample_trace_response
    ):
        """Test latest trace searches all projects when project_uuid is None."""
        # Mock the Client
        mock_client = Mock()
        mock_run = Mock()
        mock_run.id = TEST_TRACE_ID
        mock_client.list_runs.return_value = [mock_run]
        mock_client_class.return_value = mock_client

        # Mock the REST API call
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        messages = fetchers.fetch_latest_trace(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL, project_uuid=None
        )

        # Verify list_runs was called WITHOUT project_id parameter
        call_kwargs = mock_client.list_runs.call_args[1]
        assert "project_id" not in call_kwargs
        assert call_kwargs["filter"] == 'and(eq(is_root, true), neq(status, "pending"))'
        assert call_kwargs["limit"] == 1

        assert isinstance(messages, list)


class TestFetchRecentTraces:
    """Tests for fetch_recent_traces function."""

    @responses.activate
    @patch("langsmith.Client")
    def test_fetch_recent_traces_success(
        self, mock_client_class, sample_trace_response
    ):
        """Test successful recent traces fetching."""
        # Mock the Client and its list_runs method
        mock_client = Mock()
        mock_run1 = Mock()
        mock_run1.id = "trace-id-1"
        mock_run1.feedback_stats = {}  # Empty dict, not a Mock
        mock_run1.start_time = None
        mock_run1.end_time = None
        mock_run1.extra = {}
        mock_run2 = Mock()
        mock_run2.id = "trace-id-2"
        mock_run2.feedback_stats = {}  # Empty dict, not a Mock
        mock_run2.start_time = None
        mock_run2.end_time = None
        mock_run2.extra = {}
        mock_client.list_runs.return_value = [mock_run1, mock_run2]
        mock_client_class.return_value = mock_client

        # Mock the REST API calls for fetch_trace
        responses.add(
            responses.GET,
            "https://api.smith.langchain.com/runs/trace-id-1",
            json=sample_trace_response,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.smith.langchain.com/runs/trace-id-2",
            json=sample_trace_response,
            status=200,
        )

        traces_data = fetchers.fetch_recent_traces(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL, limit=2,
            include_metadata=False, include_feedback=False
        )

        # Verify Client was instantiated with correct API key
        mock_client_class.assert_called_once_with(api_key=TEST_API_KEY)

        # Verify list_runs was called with correct parameters
        mock_client.list_runs.assert_called_once()
        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs["filter"] == 'and(eq(is_root, true), neq(status, "pending"))'
        assert call_kwargs["limit"] == 2

        # Verify the traces were fetched correctly
        assert isinstance(traces_data, list)
        assert len(traces_data) == 2
        # Order doesn't matter with concurrent fetching, just check both IDs present
        trace_ids = {trace_id for trace_id, _ in traces_data}
        assert trace_ids == {"trace-id-1", "trace-id-2"}
        assert all(isinstance(messages, list) for _, messages in traces_data)

    @patch("langsmith.Client")
    def test_fetch_recent_traces_no_traces_found(self, mock_client_class):
        """Test fetch_recent_traces when no traces are found."""
        # Mock empty list_runs result
        mock_client = Mock()
        mock_client.list_runs.return_value = []
        mock_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="No traces found matching criteria"):
            fetchers.fetch_recent_traces(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)

    @responses.activate
    @patch("langsmith.Client")
    def test_fetch_recent_traces_with_project_uuid(
        self, mock_client_class, sample_trace_response
    ):
        """Test recent traces fetching with project UUID filter."""
        # Mock the Client
        mock_client = Mock()
        mock_run = Mock()
        mock_run.id = TEST_TRACE_ID
        mock_run.feedback_stats = {}
        mock_run.start_time = None
        mock_run.end_time = None
        mock_run.extra = {}
        mock_client.list_runs.return_value = [mock_run]
        mock_client_class.return_value = mock_client

        # Mock the REST API call
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        traces_data = fetchers.fetch_recent_traces(
            api_key=TEST_API_KEY,
            base_url=TEST_BASE_URL,
            limit=1,
            project_uuid=TEST_PROJECT_UUID,
            include_metadata=False,
            include_feedback=False,
        )

        # Verify list_runs was called with project_id
        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs["project_id"] == TEST_PROJECT_UUID
        assert call_kwargs["filter"] == 'and(eq(is_root, true), neq(status, "pending"))'
        assert call_kwargs["limit"] == 1

        assert isinstance(traces_data, list)
        assert len(traces_data) == 1

    @responses.activate
    @patch("langsmith.Client")
    def test_fetch_recent_traces_with_time_window(
        self, mock_client_class, sample_trace_response
    ):
        """Test recent traces fetching with last_n_minutes filter."""
        # Mock the Client
        mock_client = Mock()
        mock_run = Mock()
        mock_run.id = TEST_TRACE_ID
        mock_run.feedback_stats = {}
        mock_run.start_time = None
        mock_run.end_time = None
        mock_run.extra = {}
        mock_client.list_runs.return_value = [mock_run]
        mock_client_class.return_value = mock_client

        # Mock the REST API call
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        traces_data = fetchers.fetch_recent_traces(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL, last_n_minutes=30,
            include_metadata=False, include_feedback=False
        )

        # Verify list_runs was called with start_time
        call_kwargs = mock_client.list_runs.call_args[1]
        assert "start_time" in call_kwargs
        assert isinstance(call_kwargs["start_time"], datetime)
        assert call_kwargs["filter"] == 'and(eq(is_root, true), neq(status, "pending"))'

        assert isinstance(traces_data, list)

    @responses.activate
    @patch("langsmith.Client")
    def test_fetch_recent_traces_with_since_timestamp(
        self, mock_client_class, sample_trace_response
    ):
        """Test recent traces fetching with since timestamp filter."""
        # Mock the Client
        mock_client = Mock()
        mock_run = Mock()
        mock_run.id = TEST_TRACE_ID
        mock_run.feedback_stats = {}
        mock_run.start_time = None
        mock_run.end_time = None
        mock_run.extra = {}
        mock_client.list_runs.return_value = [mock_run]
        mock_client_class.return_value = mock_client

        # Mock the REST API call
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        since_timestamp = "2025-12-09T10:00:00Z"
        traces_data = fetchers.fetch_recent_traces(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL, since=since_timestamp,
            include_metadata=False, include_feedback=False
        )

        # Verify list_runs was called with start_time
        call_kwargs = mock_client.list_runs.call_args[1]
        assert "start_time" in call_kwargs
        assert isinstance(call_kwargs["start_time"], datetime)
        assert call_kwargs["filter"] == 'and(eq(is_root, true), neq(status, "pending"))'

        assert isinstance(traces_data, list)


class TestFetchRecentThreads:
    """Tests for fetch_recent_threads function."""

    @responses.activate
    def test_fetch_recent_threads_success(self, sample_thread_response):
        """Test successful recent threads fetching."""
        # Mock runs query
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/runs/query",
            json={
                "runs": [
                    {
                        "id": "run-1",
                        "start_time": "2024-01-02T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-1"}},
                    },
                    {
                        "id": "run-2",
                        "start_time": "2024-01-01T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-2"}},
                    },
                ]
            },
            status=200,
        )

        # Mock thread fetches
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/threads/thread-1",
            json=sample_thread_response,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/threads/thread-2",
            json=sample_thread_response,
            status=200,
        )

        results = fetchers.fetch_recent_threads(
            TEST_PROJECT_UUID, TEST_BASE_URL, TEST_API_KEY, limit=10
        )

        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0][0] == "thread-1"
        assert results[1][0] == "thread-2"
        assert len(results[0][1]) == 3  # 3 messages per thread
        assert len(results[1][1]) == 3

    @responses.activate
    def test_fetch_recent_threads_respects_limit(self, sample_thread_response):
        """Test that fetch_recent_threads respects the limit parameter."""
        # Mock runs query with 3 threads
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/runs/query",
            json={
                "runs": [
                    {
                        "id": "run-1",
                        "start_time": "2024-01-03T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-1"}},
                    },
                    {
                        "id": "run-2",
                        "start_time": "2024-01-02T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-2"}},
                    },
                    {
                        "id": "run-3",
                        "start_time": "2024-01-01T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-3"}},
                    },
                ]
            },
            status=200,
        )

        # Mock only 2 thread fetches (because limit=2)
        for i in [1, 2]:
            responses.add(
                responses.GET,
                f"{TEST_BASE_URL}/runs/threads/thread-{i}",
                json=sample_thread_response,
                status=200,
            )

        results = fetchers.fetch_recent_threads(
            TEST_PROJECT_UUID, TEST_BASE_URL, TEST_API_KEY, limit=2
        )

        assert len(results) == 2
        assert results[0][0] == "thread-1"
        assert results[1][0] == "thread-2"

    @responses.activate
    def test_fetch_recent_threads_handles_missing_thread_id(
        self, sample_thread_response
    ):
        """Test that runs without thread_id are skipped."""
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/runs/query",
            json={
                "runs": [
                    {
                        "id": "run-1",
                        "start_time": "2024-01-02T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-1"}},
                    },
                    {
                        "id": "run-2",
                        "start_time": "2024-01-01T00:00:00Z",
                        "extra": {"metadata": {}},  # No thread_id
                    },
                ]
            },
            status=200,
        )

        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/threads/thread-1",
            json=sample_thread_response,
            status=200,
        )

        results = fetchers.fetch_recent_threads(
            TEST_PROJECT_UUID, TEST_BASE_URL, TEST_API_KEY, limit=10
        )

        assert len(results) == 1
        assert results[0][0] == "thread-1"

    @responses.activate
    def test_fetch_recent_threads_deduplicates(self, sample_thread_response):
        """Test that duplicate thread_ids are deduplicated."""
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/runs/query",
            json={
                "runs": [
                    {
                        "id": "run-1",
                        "start_time": "2024-01-02T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-1"}},
                    },
                    {
                        "id": "run-2",
                        "start_time": "2024-01-01T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-1"}},  # Duplicate
                    },
                ]
            },
            status=200,
        )

        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/threads/thread-1",
            json=sample_thread_response,
            status=200,
        )

        results = fetchers.fetch_recent_threads(
            TEST_PROJECT_UUID, TEST_BASE_URL, TEST_API_KEY, limit=10
        )

        # Should only have one result even though thread-1 appeared twice
        assert len(results) == 1
        assert results[0][0] == "thread-1"

    @responses.activate
    def test_fetch_recent_threads_with_last_n_minutes(self, sample_thread_response):
        """Test that temporal filter last_n_minutes is passed to API."""
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/runs/query",
            json={
                "runs": [
                    {
                        "id": "run-1",
                        "start_time": "2024-01-02T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-1"}},
                    }
                ]
            },
            status=200,
        )

        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/threads/thread-1",
            json=sample_thread_response,
            status=200,
        )

        results = fetchers.fetch_recent_threads(
            TEST_PROJECT_UUID, TEST_BASE_URL, TEST_API_KEY, limit=10, last_n_minutes=30
        )

        # Verify the request was made with start_time in body
        assert len(responses.calls) == 2
        request_body = json.loads(responses.calls[0].request.body)
        assert "start_time" in request_body
        assert len(results) == 1

    @responses.activate
    def test_fetch_recent_threads_with_since(self, sample_thread_response):
        """Test that temporal filter since is passed to API."""
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/runs/query",
            json={
                "runs": [
                    {
                        "id": "run-1",
                        "start_time": "2024-01-02T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-1"}},
                    }
                ]
            },
            status=200,
        )

        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/threads/thread-1",
            json=sample_thread_response,
            status=200,
        )

        results = fetchers.fetch_recent_threads(
            TEST_PROJECT_UUID,
            TEST_BASE_URL,
            TEST_API_KEY,
            limit=10,
            since="2025-12-09T10:00:00Z",
        )

        # Verify the request was made with start_time in body
        assert len(responses.calls) == 2
        request_body = json.loads(responses.calls[0].request.body)
        assert "start_time" in request_body
        assert len(results) == 1
