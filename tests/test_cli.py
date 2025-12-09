"""Tests for CLI commands."""

import pytest
import json
from click.testing import CliRunner
import responses
from unittest.mock import patch

from langsmith_cli.cli import main
from tests.conftest import TEST_TRACE_ID, TEST_THREAD_ID, TEST_PROJECT_UUID, TEST_API_KEY


class TestTraceCommand:
    """Tests for trace command."""

    @responses.activate
    def test_trace_default_format(self, sample_trace_response, mock_env_api_key):
        """Test trace command with default (pretty) format."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200
        )

        runner = CliRunner()
        result = runner.invoke(main, ['trace', TEST_TRACE_ID])

        assert result.exit_code == 0
        # Check for Rich panel indicators
        assert "Message 1:" in result.output
        assert "HUMAN" in result.output or "USER" in result.output

    @responses.activate
    def test_trace_pretty_format(self, sample_trace_response, mock_env_api_key):
        """Test trace command with explicit pretty format."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200
        )

        runner = CliRunner()
        result = runner.invoke(main, ['trace', TEST_TRACE_ID, '--format', 'pretty'])

        assert result.exit_code == 0
        assert "Message 1:" in result.output

    @responses.activate
    def test_trace_json_format(self, sample_trace_response, mock_env_api_key):
        """Test trace command with json format."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200
        )

        runner = CliRunner()
        result = runner.invoke(main, ['trace', TEST_TRACE_ID, '--format', 'json'])

        assert result.exit_code == 0
        # Output should be valid JSON with pretty formatting
        assert '"type": "human"' in result.output or '"type": "user"' in result.output
        assert "jane@ex" in result.output  # Partial match for truncated output

    @responses.activate
    def test_trace_raw_format(self, sample_trace_response, mock_env_api_key):
        """Test trace command with raw format."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200
        )

        runner = CliRunner()
        result = runner.invoke(main, ['trace', TEST_TRACE_ID, '--format', 'raw'])

        assert result.exit_code == 0
        # Should contain JSON array markers and message content
        assert '[' in result.output
        assert ']' in result.output
        assert 'type' in result.output or 'role' in result.output

    def test_trace_no_api_key(self, monkeypatch):
        """Test trace command fails without API key."""
        monkeypatch.delenv('LANGSMITH_API_KEY', raising=False)

        runner = CliRunner()
        result = runner.invoke(main, ['trace', TEST_TRACE_ID])

        assert result.exit_code == 1
        assert "LANGSMITH_API_KEY not found" in result.output

    @responses.activate
    def test_trace_api_error(self, mock_env_api_key):
        """Test trace command handles API errors."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json={"error": "Not found"},
            status=404
        )

        runner = CliRunner()
        result = runner.invoke(main, ['trace', TEST_TRACE_ID])

        assert result.exit_code == 1
        assert "Error fetching trace" in result.output


class TestThreadCommand:
    """Tests for thread command."""

    @responses.activate
    def test_thread_default_format_with_config(self, sample_thread_response, mock_env_api_key, temp_config_dir):
        """Test thread command with default format and config."""
        # Set up config
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                from langsmith_cli.config import set_config_value
                set_config_value('project-uuid', TEST_PROJECT_UUID)

                responses.add(
                    responses.GET,
                    f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
                    json=sample_thread_response,
                    status=200
                )

                runner = CliRunner()
                result = runner.invoke(main, ['thread', TEST_THREAD_ID])

                assert result.exit_code == 0
                assert "Message 1:" in result.output

    @responses.activate
    def test_thread_pretty_format(self, sample_thread_response, mock_env_api_key, temp_config_dir):
        """Test thread command with explicit pretty format."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                from langsmith_cli.config import set_config_value
                set_config_value('project-uuid', TEST_PROJECT_UUID)

                responses.add(
                    responses.GET,
                    f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
                    json=sample_thread_response,
                    status=200
                )

                runner = CliRunner()
                result = runner.invoke(main, ['thread', TEST_THREAD_ID, '--format', 'pretty'])

                assert result.exit_code == 0
                assert "Message 1:" in result.output

    @responses.activate
    def test_thread_json_format(self, sample_thread_response, mock_env_api_key, temp_config_dir):
        """Test thread command with json format."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                from langsmith_cli.config import set_config_value
                set_config_value('project-uuid', TEST_PROJECT_UUID)

                responses.add(
                    responses.GET,
                    f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
                    json=sample_thread_response,
                    status=200
                )

                runner = CliRunner()
                result = runner.invoke(main, ['thread', TEST_THREAD_ID, '--format', 'json'])

                assert result.exit_code == 0
                assert '"role":' in result.output

    @responses.activate
    def test_thread_raw_format(self, sample_thread_response, mock_env_api_key, temp_config_dir):
        """Test thread command with raw format."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                from langsmith_cli.config import set_config_value
                set_config_value('project-uuid', TEST_PROJECT_UUID)

                responses.add(
                    responses.GET,
                    f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
                    json=sample_thread_response,
                    status=200
                )

                runner = CliRunner()
                result = runner.invoke(main, ['thread', TEST_THREAD_ID, '--format', 'raw'])

                assert result.exit_code == 0
                # Should contain JSON array markers and message content
                assert '[' in result.output
                assert ']' in result.output
                assert 'role' in result.output or 'type' in result.output

    @responses.activate
    def test_thread_with_project_uuid_override(self, sample_thread_response, mock_env_api_key):
        """Test thread command with --project-uuid override."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
            json=sample_thread_response,
            status=200
        )

        runner = CliRunner()
        result = runner.invoke(main, [
            'thread', TEST_THREAD_ID,
            '--project-uuid', TEST_PROJECT_UUID
        ])

        assert result.exit_code == 0

    def test_thread_no_project_uuid(self, mock_env_api_key, temp_config_dir):
        """Test thread command fails without project UUID."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                runner = CliRunner()
                result = runner.invoke(main, ['thread', TEST_THREAD_ID])

                assert result.exit_code == 1
                assert "project-uuid required" in result.output

    def test_thread_no_api_key(self, monkeypatch, temp_config_dir):
        """Test thread command fails without API key."""
        monkeypatch.delenv('LANGSMITH_API_KEY', raising=False)

        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                from langsmith_cli.config import set_config_value
                set_config_value('project-uuid', TEST_PROJECT_UUID)

                runner = CliRunner()
                result = runner.invoke(main, ['thread', TEST_THREAD_ID])

                assert result.exit_code == 1
                assert "LANGSMITH_API_KEY not found" in result.output


class TestThreadsCommand:
    """Tests for threads command."""

    @responses.activate
    def test_threads_default_limit(self, sample_thread_response, mock_env_api_key, temp_config_dir, tmp_path):
        """Test threads command with default limit."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                from langsmith_cli.config import set_config_value
                set_config_value('project-uuid', TEST_PROJECT_UUID)

                # Mock the runs query endpoint
                responses.add(
                    responses.POST,
                    "https://api.smith.langchain.com/runs/query",
                    json={
                        "runs": [
                            {
                                "id": "run-1",
                                "start_time": "2024-01-01T00:00:00Z",
                                "extra": {
                                    "metadata": {
                                        "thread_id": "thread-1"
                                    }
                                }
                            },
                            {
                                "id": "run-2",
                                "start_time": "2024-01-02T00:00:00Z",
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

                # Mock the thread fetch endpoints
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

                runner = CliRunner()
                output_dir = tmp_path / "threads"
                result = runner.invoke(main, ['threads', '--output-dir', str(output_dir)])

                assert result.exit_code == 0
                assert "Found 2 thread(s)" in result.output
                assert "Successfully saved 2 thread(s)" in result.output
                
                # Check that files were created
                assert (output_dir / "thread-1.json").exists()
                assert (output_dir / "thread-2.json").exists()

    @responses.activate
    def test_threads_custom_limit(self, sample_thread_response, mock_env_api_key, temp_config_dir, tmp_path):
        """Test threads command with custom limit."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                from langsmith_cli.config import set_config_value
                set_config_value('project-uuid', TEST_PROJECT_UUID)

                # Mock the runs query endpoint
                responses.add(
                    responses.POST,
                    "https://api.smith.langchain.com/runs/query",
                    json={
                        "runs": [
                            {
                                "id": "run-1",
                                "start_time": "2024-01-01T00:00:00Z",
                                "extra": {
                                    "metadata": {
                                        "thread_id": "thread-1"
                                    }
                                }
                            }
                        ]
                    },
                    status=200
                )

                # Mock the thread fetch endpoint
                responses.add(
                    responses.GET,
                    "https://api.smith.langchain.com/runs/threads/thread-1",
                    json=sample_thread_response,
                    status=200
                )

                runner = CliRunner()
                output_dir = tmp_path / "threads"
                result = runner.invoke(main, ['threads', '--limit', '5', '--output-dir', str(output_dir)])

                assert result.exit_code == 0
                assert "thread-1" in result.output

    def test_threads_no_project_uuid(self, mock_env_api_key, temp_config_dir):
        """Test threads command fails without project UUID."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                runner = CliRunner()
                result = runner.invoke(main, ['threads'])

                assert result.exit_code == 1
                assert "project-uuid required" in result.output
