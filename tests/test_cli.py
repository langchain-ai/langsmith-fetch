"""Tests for CLI commands."""

from unittest.mock import patch

import responses
from click.testing import CliRunner

from langsmith_cli.cli import main
from tests.conftest import (
    TEST_BASE_URL,
    TEST_PROJECT_UUID,
    TEST_THREAD_ID,
    TEST_TRACE_ID,
)


class TestTraceCommand:
    """Tests for trace command."""

    @responses.activate
    def test_trace_default_format(self, sample_trace_response, mock_env_api_key):
        """Test trace command with default (pretty) format."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["trace", TEST_TRACE_ID])

        assert result.exit_code == 0
        # Check for Rich panel indicators
        assert "Message 1:" in result.output
        assert "human" in result.output or "user" in result.output

    @responses.activate
    def test_trace_pretty_format(self, sample_trace_response, mock_env_api_key):
        """Test trace command with explicit pretty format."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["trace", TEST_TRACE_ID, "--format", "pretty"])

        assert result.exit_code == 0
        assert "Message 1:" in result.output

    @responses.activate
    def test_trace_json_format(self, sample_trace_response, mock_env_api_key):
        """Test trace command with json format."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["trace", TEST_TRACE_ID, "--format", "json"])

        assert result.exit_code == 0
        # Output should be valid JSON with pretty formatting
        assert '"type": "human"' in result.output or '"type": "user"' in result.output
        # Check for content from the email (should be in the JSON somewhere)
        assert "jane" in result.output.lower()  # Case-insensitive check

    @responses.activate
    def test_trace_raw_format(self, sample_trace_response, mock_env_api_key):
        """Test trace command with raw format."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json=sample_trace_response,
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["trace", TEST_TRACE_ID, "--format", "raw"])

        assert result.exit_code == 0
        # Should contain JSON array markers and message content
        assert "[" in result.output
        assert "]" in result.output
        assert "type" in result.output or "role" in result.output

    def test_trace_no_api_key(self, monkeypatch):
        """Test trace command fails without API key."""
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(main, ["trace", TEST_TRACE_ID])

        assert result.exit_code == 1
        assert "LANGSMITH_API_KEY not found" in result.output

    @responses.activate
    def test_trace_api_error(self, mock_env_api_key):
        """Test trace command handles API errors."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}",
            json={"error": "Not found"},
            status=404,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["trace", TEST_TRACE_ID])

        assert result.exit_code == 1
        assert "Error fetching trace" in result.output


class TestThreadCommand:
    """Tests for thread command."""

    @responses.activate
    def test_thread_default_format_with_config(
        self, sample_thread_response, mock_env_api_key, temp_config_dir, monkeypatch
    ):
        """Test thread command with default format and config."""
        # Clear env vars to test config fallback
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
        monkeypatch.delenv("LANGSMITH_PROJECT_UUID", raising=False)

        # Set up config
        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import set_config_value

                set_config_value("project-uuid", TEST_PROJECT_UUID)

                responses.add(
                    responses.GET,
                    f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
                    json=sample_thread_response,
                    status=200,
                )

                runner = CliRunner()
                result = runner.invoke(main, ["thread", TEST_THREAD_ID])

                assert result.exit_code == 0
                assert "Message 1:" in result.output

    @responses.activate
    def test_thread_pretty_format(
        self, sample_thread_response, mock_env_api_key, temp_config_dir, monkeypatch
    ):
        """Test thread command with explicit pretty format."""
        # Clear env vars to test config fallback
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
        monkeypatch.delenv("LANGSMITH_PROJECT_UUID", raising=False)

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import set_config_value

                set_config_value("project-uuid", TEST_PROJECT_UUID)

                responses.add(
                    responses.GET,
                    f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
                    json=sample_thread_response,
                    status=200,
                )

                runner = CliRunner()
                result = runner.invoke(
                    main, ["thread", TEST_THREAD_ID, "--format", "pretty"]
                )

                assert result.exit_code == 0
                assert "Message 1:" in result.output

    @responses.activate
    def test_thread_json_format(
        self, sample_thread_response, mock_env_api_key, temp_config_dir, monkeypatch
    ):
        """Test thread command with json format."""
        # Clear env vars to test config fallback
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
        monkeypatch.delenv("LANGSMITH_PROJECT_UUID", raising=False)

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import set_config_value

                set_config_value("project-uuid", TEST_PROJECT_UUID)

                responses.add(
                    responses.GET,
                    f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
                    json=sample_thread_response,
                    status=200,
                )

                runner = CliRunner()
                result = runner.invoke(
                    main, ["thread", TEST_THREAD_ID, "--format", "json"]
                )

                assert result.exit_code == 0
                assert '"role":' in result.output

    @responses.activate
    def test_thread_raw_format(
        self, sample_thread_response, mock_env_api_key, temp_config_dir, monkeypatch
    ):
        """Test thread command with raw format."""
        # Clear env vars to test config fallback
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
        monkeypatch.delenv("LANGSMITH_PROJECT_UUID", raising=False)

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import set_config_value

                set_config_value("project-uuid", TEST_PROJECT_UUID)

                responses.add(
                    responses.GET,
                    f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
                    json=sample_thread_response,
                    status=200,
                )

                runner = CliRunner()
                result = runner.invoke(
                    main, ["thread", TEST_THREAD_ID, "--format", "raw"]
                )

                assert result.exit_code == 0
                # Should contain JSON array markers and message content
                assert "[" in result.output
                assert "]" in result.output
                assert "role" in result.output or "type" in result.output

    @responses.activate
    def test_thread_with_project_uuid_override(
        self, sample_thread_response, mock_env_api_key
    ):
        """Test thread command with --project-uuid override."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/threads/{TEST_THREAD_ID}",
            json=sample_thread_response,
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(
            main, ["thread", TEST_THREAD_ID, "--project-uuid", TEST_PROJECT_UUID]
        )

        assert result.exit_code == 0

    def test_thread_no_project_uuid(self, mock_env_api_key, temp_config_dir):
        """Test thread command fails without project UUID."""
        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                runner = CliRunner()
                result = runner.invoke(main, ["thread", TEST_THREAD_ID])

                assert result.exit_code == 1
                assert "project-uuid required" in result.output

    def test_thread_no_api_key(self, monkeypatch, temp_config_dir):
        """Test thread command fails without API key."""
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import set_config_value

                set_config_value("project-uuid", TEST_PROJECT_UUID)

                runner = CliRunner()
                result = runner.invoke(main, ["thread", TEST_THREAD_ID])

                assert result.exit_code == 1
                assert "LANGSMITH_API_KEY not found" in result.output


class TestThreadsCommand:
    """Tests for threads command."""

    @responses.activate
    def test_threads_default_limit(
        self, sample_thread_response, mock_env_api_key, temp_config_dir, tmp_path, monkeypatch
    ):
        """Test threads command with default limit (1)."""
        # Clear env vars to test config fallback
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
        monkeypatch.delenv("LANGSMITH_PROJECT_UUID", raising=False)

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import set_config_value

                set_config_value("project-uuid", TEST_PROJECT_UUID)

                # Mock the runs query endpoint
                responses.add(
                    responses.POST,
                    f"{TEST_BASE_URL}/runs/query",
                    json={
                        "runs": [
                            {
                                "id": "run-1",
                                "start_time": "2024-01-01T00:00:00Z",
                                "extra": {"metadata": {"thread_id": "thread-1"}},
                            },
                            {
                                "id": "run-2",
                                "start_time": "2024-01-02T00:00:00Z",
                                "extra": {"metadata": {"thread_id": "thread-2"}},
                            },
                        ]
                    },
                    status=200,
                )

                # Mock the thread fetch endpoint
                responses.add(
                    responses.GET,
                    f"{TEST_BASE_URL}/runs/threads/thread-1",
                    json=sample_thread_response,
                    status=200,
                )

                runner = CliRunner()
                output_dir = tmp_path / "threads"
                result = runner.invoke(main, ["threads", str(output_dir)])

                assert result.exit_code == 0
                assert "Found 1 thread(s)" in result.output
                assert "Successfully saved 1 thread(s)" in result.output

                # Check that only one file was created (default limit is 1)
                assert (output_dir / "thread-1.json").exists()
                assert not (output_dir / "thread-2.json").exists()

    @responses.activate
    def test_threads_custom_limit(
        self, sample_thread_response, mock_env_api_key, temp_config_dir, tmp_path, monkeypatch
    ):
        """Test threads command with custom limit."""
        # Clear env vars to test config fallback
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
        monkeypatch.delenv("LANGSMITH_PROJECT_UUID", raising=False)

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import set_config_value

                set_config_value("project-uuid", TEST_PROJECT_UUID)

                # Mock the runs query endpoint
                responses.add(
                    responses.POST,
                    f"{TEST_BASE_URL}/runs/query",
                    json={
                        "runs": [
                            {
                                "id": "run-1",
                                "start_time": "2024-01-01T00:00:00Z",
                                "extra": {"metadata": {"thread_id": "thread-1"}},
                            }
                        ]
                    },
                    status=200,
                )

                # Mock the thread fetch endpoint
                responses.add(
                    responses.GET,
                    f"{TEST_BASE_URL}/runs/threads/thread-1",
                    json=sample_thread_response,
                    status=200,
                )

                runner = CliRunner()
                output_dir = tmp_path / "threads"
                result = runner.invoke(
                    main, ["threads", str(output_dir), "--limit", "5"]
                )

                assert result.exit_code == 0
                assert "thread-1" in result.output

    def test_threads_no_project_uuid(self, mock_env_api_key, temp_config_dir, tmp_path):
        """Test threads command fails without project UUID."""
        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                runner = CliRunner()
                output_dir = tmp_path / "threads"
                result = runner.invoke(main, ["threads", str(output_dir)])

                assert result.exit_code == 1
                assert "project-uuid required" in result.output

    @responses.activate
    def test_threads_custom_filename_pattern(
        self, sample_thread_response, mock_env_api_key, temp_config_dir, tmp_path, monkeypatch
    ):
        """Test threads command with custom filename pattern."""
        # Clear env vars to test config fallback
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
        monkeypatch.delenv("LANGSMITH_PROJECT_UUID", raising=False)

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import set_config_value

                set_config_value("project-uuid", TEST_PROJECT_UUID)

                # Mock the runs query endpoint
                responses.add(
                    responses.POST,
                    f"{TEST_BASE_URL}/runs/query",
                    json={
                        "runs": [
                            {
                                "id": "run-1",
                                "start_time": "2024-01-01T00:00:00Z",
                                "extra": {"metadata": {"thread_id": "thread-1"}},
                            },
                            {
                                "id": "run-2",
                                "start_time": "2024-01-02T00:00:00Z",
                                "extra": {"metadata": {"thread_id": "thread-2"}},
                            },
                        ]
                    },
                    status=200,
                )

                # Mock the thread fetch endpoints
                for thread_id in ["thread-1", "thread-2"]:
                    responses.add(
                        responses.GET,
                        f"{TEST_BASE_URL}/runs/threads/{thread_id}",
                        json=sample_thread_response,
                        status=200,
                    )

                runner = CliRunner()
                output_dir = tmp_path / "threads"
                result = runner.invoke(
                    main,
                    [
                        "threads",
                        str(output_dir),
                        "--limit",
                        "2",
                        "--filename-pattern",
                        "thread_{index:03d}.json",
                    ],
                )

                assert result.exit_code == 0
                assert "Found 2 thread(s)" in result.output

                # Check that files were created with custom pattern
                assert (output_dir / "thread_001.json").exists()
                assert (output_dir / "thread_002.json").exists()


class TestTracesCommand:
    """Tests for traces command."""

    @responses.activate
    def test_traces_default_no_metadata(
        self, sample_trace_response, mock_env_api_key, temp_config_dir, tmp_path
    ):
        """Test traces command with directory output and default (no metadata)."""
        # Mock langsmith import
        with patch("langsmith_cli.fetchers.HAS_LANGSMITH", True):
            # Mock the /info endpoint (called by Client initialization)
            responses.add(
                responses.GET,
                f"{TEST_BASE_URL}/info",
                json={"version": "1.0"},
                status=200,
            )

            # Mock the runs query endpoint (called by Client.list_runs)
            responses.add(
                responses.POST,
                f"{TEST_BASE_URL}/runs/query",
                json={
                    "runs": [
                        {
                            "id": "3b0b15fe-1e3a-4aef-afa8-48df15879cfe",
                            "name": "test_run",
                            "start_time": "2024-01-01T00:00:00Z",
                            "run_type": "chain",
                            "trace_id": "3b0b15fe-1e3a-4aef-afa8-48df15879cfe",
                        }
                    ]
                },
                status=200,
            )

            # Mock the trace fetch endpoint
            trace_id = "3b0b15fe-1e3a-4aef-afa8-48df15879cfe"
            responses.add(
                responses.GET,
                f"{TEST_BASE_URL}/runs/{trace_id}",
                json=sample_trace_response,
                status=200,
            )

            runner = CliRunner()
            output_dir = tmp_path / "traces"
            result = runner.invoke(main, ["traces", str(output_dir), "--limit", "1"])

            assert result.exit_code == 0
            assert "Found 1 trace(s)" in result.output
            assert "Successfully saved 1 trace(s)" in result.output
            assert "3 messages" in result.output  # Should show message count

            # Check that file was created and contains list (not dict)
            import json

            trace_file = output_dir / f"{trace_id}.json"
            assert trace_file.exists()
            with open(trace_file) as f:
                data = json.load(f)
                assert isinstance(data, list)  # Should be list when no metadata

    @responses.activate
    def test_traces_with_metadata(
        self, sample_trace_response, mock_env_api_key, temp_config_dir, tmp_path
    ):
        """Test traces command with --include-metadata flag."""
        with patch("langsmith_cli.fetchers.HAS_LANGSMITH", True):
            # Mock the /info endpoint
            responses.add(
                responses.GET,
                f"{TEST_BASE_URL}/info",
                json={"version": "1.0"},
                status=200,
            )

            # Mock the runs query endpoint with metadata fields
            trace_id = "3b0b15fe-1e3a-4aef-afa8-48df15879cfe"
            responses.add(
                responses.POST,
                f"{TEST_BASE_URL}/runs/query",
                json={
                    "runs": [
                        {
                            "id": trace_id,
                            "name": "test_run",
                            "start_time": "2024-01-01T00:00:00Z",
                            "end_time": "2024-01-01T00:01:00Z",
                            "run_type": "chain",
                            "trace_id": trace_id,
                            "status": "success",
                        }
                    ]
                },
                status=200,
            )

            responses.add(
                responses.GET,
                f"{TEST_BASE_URL}/runs/{trace_id}",
                json=sample_trace_response,
                status=200,
            )

            runner = CliRunner()
            output_dir = tmp_path / "traces"
            result = runner.invoke(
                main, ["traces", str(output_dir), "--limit", "1", "--include-metadata"]
            )

            assert result.exit_code == 0
            assert "Found 1 trace(s)" in result.output
            assert "3 messages, status:" in result.output  # Should show status

            # Check that file contains dict with metadata
            import json

            trace_file = output_dir / f"{trace_id}.json"
            assert trace_file.exists()
            with open(trace_file) as f:
                data = json.load(f)
                assert isinstance(data, dict)
                assert "messages" in data
                assert "metadata" in data
                assert "feedback" in data
                assert len(data["messages"]) == 3

    @responses.activate
    def test_traces_custom_limit(
        self, sample_trace_response, mock_env_api_key, temp_config_dir, tmp_path
    ):
        """Test traces command with custom limit."""
        with patch("langsmith_cli.fetchers.HAS_LANGSMITH", True):
            # Mock the /info endpoint
            responses.add(
                responses.GET,
                f"{TEST_BASE_URL}/info",
                json={"version": "1.0"},
                status=200,
            )

            # Mock the runs query endpoint
            trace_ids = [
                "3b0b15fe-1e3a-4aef-afa8-48df15879cf1",
                "3b0b15fe-1e3a-4aef-afa8-48df15879cf2",
                "3b0b15fe-1e3a-4aef-afa8-48df15879cf3",
            ]
            responses.add(
                responses.POST,
                f"{TEST_BASE_URL}/runs/query",
                json={
                    "runs": [
                        {
                            "id": tid,
                            "name": f"test_run_{i}",
                            "start_time": "2024-01-01T00:00:00Z",
                            "run_type": "chain",
                            "trace_id": tid,
                        }
                        for i, tid in enumerate(trace_ids, 1)
                    ]
                },
                status=200,
            )

            # Mock trace fetch endpoints
            for tid in trace_ids:
                responses.add(
                    responses.GET,
                    f"{TEST_BASE_URL}/runs/{tid}",
                    json=sample_trace_response,
                    status=200,
                )

            runner = CliRunner()
            output_dir = tmp_path / "traces"
            result = runner.invoke(main, ["traces", str(output_dir), "--limit", "3"])

            assert result.exit_code == 0
            assert "Found 3 trace(s)" in result.output
            assert "Successfully saved 3 trace(s)" in result.output

            # Check that all files were created
            for tid in trace_ids:
                assert (output_dir / f"{tid}.json").exists()

    @responses.activate
    def test_traces_custom_filename_pattern(
        self, sample_trace_response, mock_env_api_key, temp_config_dir, tmp_path
    ):
        """Test traces command with custom filename pattern."""
        with patch("langsmith_cli.fetchers.HAS_LANGSMITH", True):
            # Mock the /info endpoint
            responses.add(
                responses.GET,
                f"{TEST_BASE_URL}/info",
                json={"version": "1.0"},
                status=200,
            )

            # Mock the runs query endpoint
            trace_ids = [
                "3b0b15fe-1e3a-4aef-afa8-48df15879cf1",
                "3b0b15fe-1e3a-4aef-afa8-48df15879cf2",
            ]
            responses.add(
                responses.POST,
                f"{TEST_BASE_URL}/runs/query",
                json={
                    "runs": [
                        {
                            "id": tid,
                            "name": f"test_run_{i}",
                            "start_time": "2024-01-01T00:00:00Z",
                            "run_type": "chain",
                            "trace_id": tid,
                        }
                        for i, tid in enumerate(trace_ids, 1)
                    ]
                },
                status=200,
            )

            # Mock trace fetch endpoints
            for tid in trace_ids:
                responses.add(
                    responses.GET,
                    f"{TEST_BASE_URL}/runs/{tid}",
                    json=sample_trace_response,
                    status=200,
                )

            runner = CliRunner()
            output_dir = tmp_path / "traces"
            result = runner.invoke(
                main,
                [
                    "traces",
                    str(output_dir),
                    "--limit",
                    "2",
                    "--filename-pattern",
                    "trace_{index:03d}.json",
                ],
            )

            assert result.exit_code == 0
            assert "Found 2 trace(s)" in result.output

            # Check that files were created with custom pattern
            assert (output_dir / "trace_001.json").exists()
            assert (output_dir / "trace_002.json").exists()

    @responses.activate
    def test_traces_with_project_uuid(
        self, sample_trace_response, mock_env_api_key, temp_config_dir, tmp_path
    ):
        """Test traces command with --project-uuid filter."""
        with patch("langsmith_cli.fetchers.HAS_LANGSMITH", True):
            # Mock the /info endpoint
            responses.add(
                responses.GET,
                f"{TEST_BASE_URL}/info",
                json={"version": "1.0"},
                status=200,
            )

            # Mock the runs query endpoint
            trace_id = "3b0b15fe-1e3a-4aef-afa8-48df15879cfe"
            responses.add(
                responses.POST,
                f"{TEST_BASE_URL}/runs/query",
                json={
                    "runs": [
                        {
                            "id": trace_id,
                            "name": "test_run",
                            "start_time": "2024-01-01T00:00:00Z",
                            "run_type": "chain",
                            "trace_id": trace_id,
                        }
                    ]
                },
                status=200,
            )

            responses.add(
                responses.GET,
                f"{TEST_BASE_URL}/runs/{trace_id}",
                json=sample_trace_response,
                status=200,
            )

            runner = CliRunner()
            output_dir = tmp_path / "traces"
            result = runner.invoke(
                main,
                [
                    "traces",
                    str(output_dir),
                    "--limit",
                    "1",
                    "--project-uuid",
                    TEST_PROJECT_UUID,
                ],
            )

            assert result.exit_code == 0
            assert "Found 1 trace(s)" in result.output
