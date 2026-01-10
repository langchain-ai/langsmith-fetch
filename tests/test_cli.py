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
        assert "human" in result.output.lower() or "user" in result.output.lower()

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

    @responses.activate
    def test_trace_with_metadata_flag(self, sample_trace_response, mock_env_api_key):
        """Test trace command with --include-metadata flag."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}?include_messages=true",
            json=sample_trace_response,
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(
            main, ["trace", TEST_TRACE_ID, "--include-metadata", "--format", "json"]
        )

        assert result.exit_code == 0
        # When metadata is included, output should contain metadata structure
        assert "metadata" in result.output or "trace_id" in result.output

    @responses.activate
    def test_trace_without_metadata_default(
        self, sample_trace_response, mock_env_api_key
    ):
        """Test trace command defaults to no metadata."""
        responses.add(
            responses.GET,
            f"https://api.smith.langchain.com/runs/{TEST_TRACE_ID}?include_messages=true",
            json=sample_trace_response,
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["trace", TEST_TRACE_ID, "--format", "json"])

        assert result.exit_code == 0
        # Without flags, should just return messages array
        output_lower = result.output.lower()
        # Check that it contains message content but not metadata wrapper
        assert "jane" in output_lower


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

    def test_threads_rejects_uuid_as_directory(self, mock_env_api_key):
        """Test threads command rejects UUID passed as directory."""
        runner = CliRunner()
        # Pass a valid UUID instead of a directory path
        fake_uuid = "3a12d0b2-bda5-4500-8732-c1984f647df5"
        result = runner.invoke(
            main, ["threads", fake_uuid, "--project-uuid", TEST_PROJECT_UUID]
        )

        assert result.exit_code == 1
        assert "looks like a UUID" in result.output
        assert "langsmith-fetch thread <thread-id>" in result.output
        assert "langsmith-fetch threads <directory-path>" in result.output


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

    def test_traces_rejects_uuid_as_directory(self, mock_env_api_key):
        """Test traces command rejects UUID passed as directory."""
        runner = CliRunner()
        # Pass a valid UUID instead of a directory path
        fake_uuid = "3a12d0b2-bda5-4500-8732-c1984f647df5"
        result = runner.invoke(main, ["traces", fake_uuid, "--include-metadata"])

        assert result.exit_code == 1
        assert "looks like a trace ID" in result.output
        assert "langsmith-fetch trace <trace-id>" in result.output
        assert "langsmith-fetch traces <directory-path>" in result.output


class TestTreeCommand:
    """Tests for tree command."""

    @responses.activate
    def test_tree_pretty_format(self, mock_env_api_key):
        """Test tree command with default pretty format."""
        trace_id = TEST_TRACE_ID
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/runs/query",
            json={
                "runs": [
                    {
                        "id": "root-run",
                        "name": "rootRun",
                        "run_type": "chain",
                        "parent_run_id": None,
                        "child_run_ids": ["child-1"],
                        "dotted_order": "1",
                        "status": "success",
                        "start_time": "2025-01-10T12:00:00Z",
                        "end_time": "2025-01-10T12:01:00Z",
                        "total_tokens": 100,
                        "total_cost": 0.01,
                        "extra": {},
                    },
                    {
                        "id": "child-1",
                        "name": "childRun",
                        "run_type": "llm",
                        "parent_run_id": "root-run",
                        "child_run_ids": [],
                        "dotted_order": "1.1",
                        "status": "success",
                        "start_time": "2025-01-10T12:00:10Z",
                        "end_time": "2025-01-10T12:00:50Z",
                        "total_tokens": 100,
                        "total_cost": 0.01,
                        "extra": {"metadata": {"ls_model_name": "gpt-4"}},
                    },
                ]
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["tree", trace_id])

        assert result.exit_code == 0
        assert "rootRun" in result.output
        assert "childRun" in result.output
        assert "TRACE SUMMARY" in result.output

    @responses.activate
    def test_tree_json_format(self, mock_env_api_key):
        """Test tree command with json format."""
        trace_id = TEST_TRACE_ID
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/runs/query",
            json={
                "runs": [
                    {
                        "id": "root-run",
                        "name": "rootRun",
                        "run_type": "chain",
                        "parent_run_id": None,
                        "child_run_ids": [],
                        "dotted_order": "1",
                        "status": "success",
                        "total_tokens": 100,
                        "total_cost": 0.01,
                        "extra": {},
                    },
                ]
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["tree", trace_id, "--format", "json"])

        assert result.exit_code == 0
        assert "trace_id" in result.output
        assert "total_runs" in result.output

    @responses.activate
    def test_tree_summary_format(self, mock_env_api_key):
        """Test tree command with summary format."""
        trace_id = TEST_TRACE_ID
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/runs/query",
            json={
                "runs": [
                    {
                        "id": "root-run",
                        "name": "rootRun",
                        "run_type": "chain",
                        "parent_run_id": None,
                        "child_run_ids": [],
                        "dotted_order": "1",
                        "status": "success",
                        "start_time": "2025-01-10T12:00:00Z",
                        "end_time": "2025-01-10T12:01:00Z",
                        "total_tokens": 500,
                        "total_cost": 0.05,
                        "extra": {},
                    },
                ]
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["tree", trace_id, "--format", "summary"])

        assert result.exit_code == 0
        assert "Total runs:" in result.output
        assert "Total tokens:" in result.output

    @responses.activate
    def test_tree_output_dir(self, mock_env_api_key, tmp_path):
        """Test tree command with output directory."""
        trace_id = TEST_TRACE_ID
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/runs/query",
            json={
                "runs": [
                    {
                        "id": "root-run",
                        "name": "rootRun",
                        "run_type": "chain",
                        "parent_run_id": None,
                        "child_run_ids": [],
                        "dotted_order": "1",
                        "status": "success",
                        "total_tokens": 100,
                        "total_cost": 0.01,
                        "extra": {},
                    },
                ]
            },
            status=200,
        )

        output_dir = tmp_path / "trace-data"
        runner = CliRunner()
        result = runner.invoke(main, ["tree", trace_id, "--output-dir", str(output_dir)])

        assert result.exit_code == 0
        assert "Saved tree.json" in result.output
        assert "Saved summary.json" in result.output
        assert "Saved NAVIGATION.md" in result.output
        assert (output_dir / "tree.json").exists()
        assert (output_dir / "summary.json").exists()
        assert (output_dir / "NAVIGATION.md").exists()
        assert (output_dir / "runs" / ".gitkeep").exists()

    def test_tree_no_api_key(self, monkeypatch):
        """Test tree command fails without API key."""
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(main, ["tree", TEST_TRACE_ID])

        assert result.exit_code == 1
        assert "LANGSMITH_API_KEY" in result.output

    @responses.activate
    def test_tree_not_found(self, mock_env_api_key):
        """Test tree command handles 404."""
        trace_id = TEST_TRACE_ID
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/runs/query",
            json={"runs": []},
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["tree", trace_id])

        assert result.exit_code == 1
        assert "No runs found" in result.output

    @responses.activate
    def test_tree_show_ids(self, mock_env_api_key):
        """Test tree command with --show-ids flag."""
        trace_id = TEST_TRACE_ID
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/runs/query",
            json={
                "runs": [
                    {
                        "id": "root-run-uuid-123",
                        "name": "rootRun",
                        "run_type": "chain",
                        "parent_run_id": None,
                        "child_run_ids": [],
                        "dotted_order": "1",
                        "status": "success",
                        "total_tokens": 100,
                        "total_cost": 0.01,
                        "extra": {},
                    },
                ]
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["tree", trace_id, "--show-ids"])

        assert result.exit_code == 0
        assert "root-run-uuid-123" in result.output


class TestRunCommand:
    """Tests for run command."""

    @responses.activate
    def test_run_pretty_format(self, mock_env_api_key):
        """Test run command with default pretty format."""
        run_id = "test-run-uuid"
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/{run_id}",
            json={
                "id": run_id,
                "name": "testRun",
                "run_type": "llm",
                "status": "success",
                "inputs": {"messages": [{"role": "user", "content": "Hello"}]},
                "outputs": {"result": "Hi there!"},
                "metadata": {"duration_ms": 1000},
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["run", run_id])

        assert result.exit_code == 0
        assert "testRun" in result.output
        assert "Status: success" in result.output

    @responses.activate
    def test_run_json_format(self, mock_env_api_key):
        """Test run command with json format."""
        run_id = "test-run-uuid"
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/{run_id}",
            json={
                "id": run_id,
                "name": "testRun",
                "run_type": "llm",
                "status": "success",
                "inputs": {},
                "outputs": {},
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["run", run_id, "--format", "json"])

        assert result.exit_code == 0
        assert '"id"' in result.output
        assert '"name"' in result.output

    @responses.activate
    def test_run_raw_format(self, mock_env_api_key):
        """Test run command with raw format."""
        run_id = "test-run-uuid"
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/{run_id}",
            json={
                "id": run_id,
                "name": "testRun",
                "run_type": "llm",
                "status": "success",
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["run", run_id, "--format", "raw"])

        assert result.exit_code == 0
        # Raw format should be compact JSON
        import json
        parsed = json.loads(result.output.strip())
        assert parsed["id"] == run_id

    @responses.activate
    def test_run_output_dir(self, mock_env_api_key, tmp_path):
        """Test run command with output directory."""
        run_id = "test-run-uuid"
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/{run_id}",
            json={
                "id": run_id,
                "name": "testRun",
                "run_type": "llm",
                "status": "success",
                "inputs": {"prompt": "Hello"},
                "outputs": {"text": "Hi"},
                "metadata": {"model": "gpt-4"},
            },
            status=200,
        )

        output_dir = tmp_path / "trace-data"
        runner = CliRunner()
        result = runner.invoke(main, ["run", run_id, "--output-dir", str(output_dir)])

        assert result.exit_code == 0
        assert "Saved run.json" in result.output
        assert "Saved inputs.json" in result.output
        assert "Saved outputs.json" in result.output
        assert "Saved metadata.json" in result.output

        run_dir = output_dir / "runs" / run_id
        assert (run_dir / "run.json").exists()
        assert (run_dir / "inputs.json").exists()
        assert (run_dir / "outputs.json").exists()
        assert (run_dir / "metadata.json").exists()

    @responses.activate
    def test_run_extract_field(self, mock_env_api_key):
        """Test run command with --extract option."""
        run_id = "test-run-uuid"
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/{run_id}",
            json={
                "id": run_id,
                "inputs": {
                    "messages": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi"},
                    ]
                },
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["run", run_id, "--extract", "inputs.messages", "--format", "json"])

        assert result.exit_code == 0
        assert "user" in result.output
        assert "Hello" in result.output

    @responses.activate
    def test_run_extract_nested_index(self, mock_env_api_key):
        """Test run command with --extract option for array index."""
        run_id = "test-run-uuid"
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/{run_id}",
            json={
                "id": run_id,
                "inputs": {
                    "messages": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi"},
                    ]
                },
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["run", run_id, "--extract", "inputs.messages.0", "--format", "raw"])

        assert result.exit_code == 0
        import json
        parsed = json.loads(result.output.strip())
        assert parsed["role"] == "user"
        assert parsed["content"] == "Hello"

    @responses.activate
    def test_run_extract_invalid_field(self, mock_env_api_key):
        """Test run command with --extract for invalid field."""
        run_id = "test-run-uuid"
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/{run_id}",
            json={"id": run_id, "inputs": {}},
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["run", run_id, "--extract", "nonexistent.field"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_run_no_api_key(self, monkeypatch):
        """Test run command fails without API key."""
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(main, ["run", "some-run-id"])

        assert result.exit_code == 1
        assert "LANGSMITH_API_KEY" in result.output

    @responses.activate
    def test_run_not_found(self, mock_env_api_key):
        """Test run command handles 404."""
        run_id = "nonexistent-run"
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/{run_id}",
            json={"error": "Not found"},
            status=404,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["run", run_id])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output

    @responses.activate
    def test_run_with_events(self, mock_env_api_key):
        """Test run command with --include-events flag."""
        run_id = "test-run-uuid"
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/runs/{run_id}",
            json={
                "id": run_id,
                "name": "testRun",
                "status": "success",
                "events": [{"event": "start"}, {"event": "end"}],
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["run", run_id, "--include-events", "--format", "json"])

        assert result.exit_code == 0
        assert "events" in result.output
