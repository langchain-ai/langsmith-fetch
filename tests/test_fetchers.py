"""Tests for fetchers module."""

import pytest
import responses
import json
from unittest.mock import Mock, patch
from datetime import datetime, timezone

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


class TestFetchLatestTrace:
    """Tests for fetch_latest_trace function."""

    @responses.activate
    @patch('langsmith.Client')
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
            status=200
        )

        messages = fetchers.fetch_latest_trace(api_key=TEST_API_KEY)

        # Verify Client was instantiated with correct API key
        mock_client_class.assert_called_once_with(api_key=TEST_API_KEY)

        # Verify list_runs was called with correct parameters
        mock_client.list_runs.assert_called_once()
        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs['is_root'] is True
        assert call_kwargs['limit'] == 1

        # Verify the messages were fetched correctly
        assert isinstance(messages, list)
        assert len(messages) == 3

    @patch('langsmith.Client')
    def test_fetch_latest_trace_no_traces_found(self, mock_client_class):
        """Test fetch_latest_trace when no traces are found."""
        # Mock empty list_runs result
        mock_client = Mock()
        mock_client.list_runs.return_value = []
        mock_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="No traces found matching criteria"):
            fetchers.fetch_latest_trace(api_key=TEST_API_KEY)

    @responses.activate
    @patch('langsmith.Client')
    def test_fetch_latest_trace_with_project_uuid(self, mock_client_class, sample_trace_response):
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
            status=200
        )

        messages = fetchers.fetch_latest_trace(
            api_key=TEST_API_KEY,
            project_uuid=TEST_PROJECT_UUID
        )

        # Verify list_runs was called with project_id
        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs['project_id'] == TEST_PROJECT_UUID
        assert call_kwargs['is_root'] is True
        assert call_kwargs['limit'] == 1

        assert isinstance(messages, list)

    @responses.activate
    @patch('langsmith.Client')
    def test_fetch_latest_trace_with_time_window(self, mock_client_class, sample_trace_response):
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
            status=200
        )

        messages = fetchers.fetch_latest_trace(
            api_key=TEST_API_KEY,
            last_n_minutes=30
        )

        # Verify list_runs was called with start_time
        call_kwargs = mock_client.list_runs.call_args[1]
        assert 'start_time' in call_kwargs
        assert isinstance(call_kwargs['start_time'], datetime)
        assert call_kwargs['is_root'] is True

        assert isinstance(messages, list)

    @responses.activate
    @patch('langsmith.Client')
    def test_fetch_latest_trace_with_since_timestamp(self, mock_client_class, sample_trace_response):
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
            status=200
        )

        since_timestamp = '2025-12-09T10:00:00Z'
        messages = fetchers.fetch_latest_trace(
            api_key=TEST_API_KEY,
            since=since_timestamp
        )

        # Verify list_runs was called with start_time
        call_kwargs = mock_client.list_runs.call_args[1]
        assert 'start_time' in call_kwargs
        assert isinstance(call_kwargs['start_time'], datetime)
        assert call_kwargs['is_root'] is True

        assert isinstance(messages, list)

    @responses.activate
    @patch('langsmith.Client')
    def test_fetch_latest_trace_without_project_uuid(self, mock_client_class, sample_trace_response):
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
            status=200
        )

        messages = fetchers.fetch_latest_trace(api_key=TEST_API_KEY, project_uuid=None)

        # Verify list_runs was called WITHOUT project_id parameter
        call_kwargs = mock_client.list_runs.call_args[1]
        assert 'project_id' not in call_kwargs
        assert call_kwargs['is_root'] is True
        assert call_kwargs['limit'] == 1

        assert isinstance(messages, list)
