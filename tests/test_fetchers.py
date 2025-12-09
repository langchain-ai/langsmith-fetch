"""Tests for fetchers module."""

import pytest
import responses
import json

from langsmith_cli import fetchers
from tests.conftest import TEST_TRACE_ID, TEST_THREAD_ID, TEST_PROJECT_UUID, TEST_API_KEY


class TestFetchTrace:
    """Tests for fetch_trace function."""

    @responses.activate
    def test_fetch_trace_success(self, sample_trace_response):
        """Test successful trace fetching."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200
        )

        messages = fetchers.fetch_trace(TEST_TRACE_ID, TEST_API_KEY)

        assert isinstance(messages, list)
        assert len(messages) == 3
        assert messages[0]['type'] == 'human'
        assert 'jane@example.com' in messages[0]['content']

    @responses.activate
    def test_fetch_trace_not_found(self):
        """Test fetch_trace with 404 error."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json={"error": "Not found"},
            status=404
        )

        with pytest.raises(Exception):
            fetchers.fetch_trace(TEST_TRACE_ID, TEST_API_KEY)

    @responses.activate
    def test_fetch_trace_api_key_sent(self, sample_trace_response):
        """Test that API key is sent in headers."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200
        )

        fetchers.fetch_trace(TEST_TRACE_ID, TEST_API_KEY)

        # Check that the request was made with correct headers
        assert len(responses.calls) == 1
        assert responses.calls[0].request.headers['X-API-Key'] == TEST_API_KEY


class TestFetchThread:
    """Tests for fetch_thread function."""

    @responses.activate
    def test_fetch_thread_success(self, sample_thread_response):
        """Test successful thread fetching."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
            json=sample_thread_response,
            status=200
        )

        messages = fetchers.fetch_thread(TEST_THREAD_ID, TEST_PROJECT_UUID, TEST_API_KEY)

        assert isinstance(messages, list)
        assert len(messages) == 3
        assert messages[0]['role'] == 'user'
        assert 'jane@example.com' in messages[0]['content']

    @responses.activate
    def test_fetch_thread_params_sent(self, sample_thread_response):
        """Test that correct params are sent in thread request."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
            json=sample_thread_response,
            status=200
        )

        fetchers.fetch_thread(TEST_THREAD_ID, TEST_PROJECT_UUID, TEST_API_KEY)

        # Check that the request was made with correct params
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.headers['X-API-Key'] == TEST_API_KEY
        # Check query params
        assert 'select=all_messages' in request.url
        assert f'session_id={TEST_PROJECT_UUID}' in request.url

    @responses.activate
    def test_fetch_thread_not_found(self):
        """Test fetch_thread with 404 error."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
            json={"error": "Not found"},
            status=404
        )

        with pytest.raises(Exception):
            fetchers.fetch_thread(TEST_THREAD_ID, TEST_PROJECT_UUID, TEST_API_KEY)

    @responses.activate
    def test_fetch_thread_parses_multiline_json(self, sample_thread_response):
        """Test that thread fetcher correctly parses newline-separated JSON."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
            json=sample_thread_response,
            status=200
        )

        messages = fetchers.fetch_thread(TEST_THREAD_ID, TEST_PROJECT_UUID, TEST_API_KEY)

        # Should have parsed all messages from newline-separated format
        assert len(messages) == 3
        # Each message should be a valid dict
        for msg in messages:
            assert isinstance(msg, dict)
            assert 'role' in msg or 'type' in msg


class TestFetchRecentThreads:
    """Tests for fetch_recent_threads function."""

    @responses.activate
    def test_fetch_recent_threads_success(self, sample_thread_response):
        """Test successful recent threads fetching."""
        # Mock runs query
        responses.add(
            responses.POST,
            "https://api.smith.langchain.com/runs/query",
            json={
                "runs": [
                    {
                        "id": "run-1",
                        "start_time": "2024-01-02T00:00:00Z",
                        "extra": {
                            "metadata": {
                                "thread_id": "thread-1"
                            }
                        }
                    },
                    {
                        "id": "run-2",
                        "start_time": "2024-01-01T00:00:00Z",
                        "extra": {
                            "metadata": {
                                "thread_id": "thread-2"
                            }
                        }
                    }
                ]
            },
            status=200
        )

        # Mock thread fetches
        responses.add(
            responses.GET,
            "https://api.smith.langchain.com/runs/threads/thread-1",
            json=sample_thread_response,
            status=200
        )
        responses.add(
            responses.GET,
            "https://api.smith.langchain.com/runs/threads/thread-2",
            json=sample_thread_response,
            status=200
        )

        results = fetchers.fetch_recent_threads(TEST_PROJECT_UUID, TEST_API_KEY, limit=10)

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
            "https://api.smith.langchain.com/runs/query",
            json={
                "runs": [
                    {
                        "id": "run-1",
                        "start_time": "2024-01-03T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-1"}}
                    },
                    {
                        "id": "run-2",
                        "start_time": "2024-01-02T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-2"}}
                    },
                    {
                        "id": "run-3",
                        "start_time": "2024-01-01T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-3"}}
                    }
                ]
            },
            status=200
        )

        # Mock only 2 thread fetches (because limit=2)
        for i in [1, 2]:
            responses.add(
                responses.GET,
                f"https://api.smith.langchain.com/runs/threads/thread-{i}",
                json=sample_thread_response,
                status=200
            )

        results = fetchers.fetch_recent_threads(TEST_PROJECT_UUID, TEST_API_KEY, limit=2)

        assert len(results) == 2
        assert results[0][0] == "thread-1"
        assert results[1][0] == "thread-2"

    @responses.activate
    def test_fetch_recent_threads_handles_missing_thread_id(self, sample_thread_response):
        """Test that runs without thread_id are skipped."""
        responses.add(
            responses.POST,
            "https://api.smith.langchain.com/runs/query",
            json={
                "runs": [
                    {
                        "id": "run-1",
                        "start_time": "2024-01-02T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-1"}}
                    },
                    {
                        "id": "run-2",
                        "start_time": "2024-01-01T00:00:00Z",
                        "extra": {"metadata": {}}  # No thread_id
                    }
                ]
            },
            status=200
        )

        responses.add(
            responses.GET,
            "https://api.smith.langchain.com/runs/threads/thread-1",
            json=sample_thread_response,
            status=200
        )

        results = fetchers.fetch_recent_threads(TEST_PROJECT_UUID, TEST_API_KEY, limit=10)

        assert len(results) == 1
        assert results[0][0] == "thread-1"

    @responses.activate
    def test_fetch_recent_threads_deduplicates(self, sample_thread_response):
        """Test that duplicate thread_ids are deduplicated."""
        responses.add(
            responses.POST,
            "https://api.smith.langchain.com/runs/query",
            json={
                "runs": [
                    {
                        "id": "run-1",
                        "start_time": "2024-01-02T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-1"}}
                    },
                    {
                        "id": "run-2",
                        "start_time": "2024-01-01T00:00:00Z",
                        "extra": {"metadata": {"thread_id": "thread-1"}}  # Duplicate
                    }
                ]
            },
            status=200
        )

        responses.add(
            responses.GET,
            "https://api.smith.langchain.com/runs/threads/thread-1",
            json=sample_thread_response,
            status=200
        )

        results = fetchers.fetch_recent_threads(TEST_PROJECT_UUID, TEST_API_KEY, limit=10)

        # Should only have one result even though thread-1 appeared twice
        assert len(results) == 1
        assert results[0][0] == "thread-1"
