"""Tests for config commands."""

from unittest.mock import patch

from click.testing import CliRunner

from langsmith_cli.cli import main
from tests.conftest import TEST_API_KEY, TEST_PROJECT_UUID


class TestConfigShow:
    """Tests for config show command."""

    def test_show_empty_config(self, temp_config_dir):
        """Test showing config when empty."""
        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                runner = CliRunner()
                result = runner.invoke(main, ["config", "show"])

                assert result.exit_code == 0
                assert "No configuration found" in result.output

    def test_show_with_project_uuid(self, temp_config_dir):
        """Test showing config with project UUID."""
        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                # Set config
                from langsmith_cli.config import set_config_value

                set_config_value("project-uuid", TEST_PROJECT_UUID)

                runner = CliRunner()
                result = runner.invoke(main, ["config", "show"])

                assert result.exit_code == 0
                assert "Current configuration:" in result.output
                assert TEST_PROJECT_UUID in result.output

    def test_show_with_api_key_masked(self, temp_config_dir):
        """Test showing config with API key (should be masked)."""
        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                # Set config
                from langsmith_cli.config import set_config_value

                set_config_value("api-key", TEST_API_KEY)

                runner = CliRunner()
                result = runner.invoke(main, ["config", "show"])

                assert result.exit_code == 0
                # Should show only first 10 chars
                assert TEST_API_KEY[:10] in result.output
                assert "..." in result.output
                # Should not show full key
                assert TEST_API_KEY not in result.output

    def test_show_all_config_options(self, temp_config_dir):
        """Test showing config with all options set."""
        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                # Set all config options
                from langsmith_cli.config import set_config_value

                set_config_value("project-uuid", TEST_PROJECT_UUID)
                set_config_value("api-key", TEST_API_KEY)
                set_config_value("default-format", "json")

                runner = CliRunner()
                result = runner.invoke(main, ["config", "show"])

                assert result.exit_code == 0
                assert "Current configuration:" in result.output
                assert TEST_PROJECT_UUID in result.output
                assert TEST_API_KEY[:10] in result.output
                assert "json" in result.output


class TestConfigFunctions:
    """Tests for config module functions."""

    def test_get_api_key_from_config(self, temp_config_dir, monkeypatch):
        """Test getting API key from config."""
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import get_api_key, set_config_value

                set_config_value("api-key", TEST_API_KEY)

                assert get_api_key() == TEST_API_KEY

    def test_get_api_key_from_env(self, temp_config_dir, monkeypatch):
        """Test getting API key from environment variable."""
        monkeypatch.setenv("LANGSMITH_API_KEY", "env_api_key")

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import get_api_key

                # Env var should take precedence over config
                assert get_api_key() == "env_api_key"

    def test_get_project_uuid(self, temp_config_dir, monkeypatch):
        """Test getting project UUID from config when no env var set."""
        # Clear env vars to test config fallback behavior
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
        monkeypatch.delenv("LANGSMITH_PROJECT_UUID", raising=False)

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import get_project_uuid, set_config_value

                set_config_value("project-uuid", TEST_PROJECT_UUID)

                assert get_project_uuid() == TEST_PROJECT_UUID

    def test_get_default_format(self, temp_config_dir):
        """Test getting default format from config."""
        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import get_default_format, set_config_value

                # Default should be 'pretty'
                assert get_default_format() == "pretty"

                # Set to 'json'
                set_config_value("default-format", "json")
                assert get_default_format() == "json"

    def test_config_key_with_hyphen_and_underscore(self, temp_config_dir):
        """Test that config keys work with both hyphens and underscores."""
        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch(
                "langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"
            ):
                from langsmith_cli.config import get_config_value, set_config_value

                # Set with hyphen
                set_config_value("project-uuid", TEST_PROJECT_UUID)

                # Get with underscore should also work
                assert get_config_value("project_uuid") == TEST_PROJECT_UUID
                # Get with hyphen should work
                assert get_config_value("project-uuid") == TEST_PROJECT_UUID


class TestProjectLookup:
    """Tests for automatic project UUID lookup from LANGSMITH_PROJECT."""

    def test_get_project_uuid_priority_explicit_uuid_wins(self, temp_config_dir, monkeypatch):
        """Test that LANGSMITH_PROJECT_UUID env var takes highest priority."""
        monkeypatch.setenv("LANGSMITH_PROJECT", "my-project")
        monkeypatch.setenv("LANGSMITH_PROJECT_UUID", "env-uuid")

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                from langsmith_cli.config import get_project_uuid, set_config_value

                set_config_value("project-uuid", "config-uuid")
                set_config_value("project-name", "old-project")

                # LANGSMITH_PROJECT_UUID should always win (highest priority)
                assert get_project_uuid() == "env-uuid"

    def test_get_project_uuid_priority_env_uuid_no_lookup(self, temp_config_dir, monkeypatch):
        """Test that LANGSMITH_PROJECT_UUID env var bypasses API lookup."""
        monkeypatch.setenv("LANGSMITH_PROJECT", "my-project")
        monkeypatch.setenv("LANGSMITH_PROJECT_UUID", "env-uuid")

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                from langsmith_cli.config import get_project_uuid

                # LANGSMITH_PROJECT_UUID should be used without API lookup
                assert get_project_uuid() == "env-uuid"

    def test_lookup_project_uuid_success(self, temp_config_dir, monkeypatch):
        """Test successful project lookup via API."""
        from unittest.mock import Mock, MagicMock

        monkeypatch.setenv("LANGSMITH_PROJECT", "test-project")
        monkeypatch.setenv("LANGSMITH_API_KEY", TEST_API_KEY)

        # Mock LangSmith Client
        mock_project = Mock()
        mock_project.id = "looked-up-uuid"
        mock_project.name = "test-project"

        mock_client = MagicMock()
        mock_client.read_project.return_value = mock_project

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                with patch("langsmith.Client", return_value=mock_client):
                    from langsmith_cli.config import get_project_uuid

                    result = get_project_uuid()
                    assert result == "looked-up-uuid"
                    mock_client.read_project.assert_called_once_with(project_name="test-project")

    def test_lookup_project_uuid_no_match(self, temp_config_dir, monkeypatch):
        """Test error handling when project not found."""
        from unittest.mock import MagicMock

        monkeypatch.setenv("LANGSMITH_PROJECT", "nonexistent")
        monkeypatch.setenv("LANGSMITH_API_KEY", TEST_API_KEY)

        mock_client = MagicMock()
        mock_client.read_project.side_effect = Exception("Project not found")

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                with patch("langsmith.Client", return_value=mock_client):
                    from langsmith_cli.config import get_project_uuid

                    # Should return None and print error to stderr
                    result = get_project_uuid()
                    assert result is None

    def test_lookup_caching(self, temp_config_dir, monkeypatch):
        """Test that lookup result is cached for session."""
        from unittest.mock import Mock, MagicMock

        monkeypatch.setenv("LANGSMITH_PROJECT", "cached-project")
        monkeypatch.setenv("LANGSMITH_API_KEY", TEST_API_KEY)

        mock_project = Mock()
        mock_project.id = "cached-uuid"
        mock_project.name = "cached-project"

        mock_client = MagicMock()
        mock_client.read_project.return_value = mock_project

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                with patch("langsmith.Client", return_value=mock_client):
                    from langsmith_cli.config import get_project_uuid, _project_uuid_cache

                    # Clear cache first
                    _project_uuid_cache.clear()

                    # First call should hit API
                    result1 = get_project_uuid()
                    assert result1 == "cached-uuid"
                    assert mock_client.read_project.call_count == 1

                    # Second call should use cache
                    result2 = get_project_uuid()
                    assert result2 == "cached-uuid"
                    assert mock_client.read_project.call_count == 1  # Still 1

    def test_lookup_no_api_key(self, temp_config_dir, monkeypatch):
        """Test graceful handling when API key is missing."""
        monkeypatch.setenv("LANGSMITH_PROJECT", "test-project")
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                from langsmith_cli.config import get_project_uuid

                # Should return None with warning
                result = get_project_uuid()
                assert result is None

    def test_project_name_change_triggers_refetch(self, temp_config_dir, monkeypatch):
        """Test that changing project name triggers UUID re-fetch."""
        from unittest.mock import Mock, MagicMock

        monkeypatch.setenv("LANGSMITH_PROJECT", "new-project")
        monkeypatch.setenv("LANGSMITH_API_KEY", TEST_API_KEY)

        mock_project = Mock()
        mock_project.id = "new-uuid"
        mock_project.name = "new-project"

        mock_client = MagicMock()
        mock_client.read_project.return_value = mock_project

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                with patch("langsmith.Client", return_value=mock_client):
                    from langsmith_cli.config import get_project_uuid, set_config_value, get_config_value, _project_uuid_cache

                    # Clear cache
                    _project_uuid_cache.clear()

                    # Set old config
                    set_config_value("project-name", "old-project")
                    set_config_value("project-uuid", "old-uuid")

                    # Should detect mismatch and fetch new UUID
                    result = get_project_uuid()
                    assert result == "new-uuid"
                    assert mock_client.read_project.call_count == 1

                    # Verify config was updated with both fields
                    assert get_config_value("project-name") == "new-project"
                    assert get_config_value("project-uuid") == "new-uuid"

    def test_project_name_match_uses_cache(self, temp_config_dir, monkeypatch):
        """Test that matching project name uses cached UUID without API call."""
        from unittest.mock import MagicMock

        monkeypatch.setenv("LANGSMITH_PROJECT", "test-project")
        monkeypatch.setenv("LANGSMITH_API_KEY", TEST_API_KEY)

        mock_client = MagicMock()

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                with patch("langsmith.Client", return_value=mock_client):
                    from langsmith_cli.config import get_project_uuid, set_config_value, _project_uuid_cache

                    # Clear cache
                    _project_uuid_cache.clear()

                    # Set matching config
                    set_config_value("project-name", "test-project")
                    set_config_value("project-uuid", "test-uuid")

                    # Should use cached UUID without API call
                    result = get_project_uuid()
                    assert result == "test-uuid"
                    assert mock_client.read_project.call_count == 0

    def test_legacy_config_migration(self, temp_config_dir, monkeypatch):
        """Test that legacy config (only project_uuid) triggers re-fetch and migration."""
        from unittest.mock import Mock, MagicMock

        monkeypatch.setenv("LANGSMITH_PROJECT", "test-project")
        monkeypatch.setenv("LANGSMITH_API_KEY", TEST_API_KEY)

        mock_project = Mock()
        mock_project.id = "fetched-uuid"
        mock_project.name = "test-project"

        mock_client = MagicMock()
        mock_client.read_project.return_value = mock_project

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                with patch("langsmith.Client", return_value=mock_client):
                    from langsmith_cli.config import get_project_uuid, set_config_value, get_config_value, _project_uuid_cache

                    # Clear cache
                    _project_uuid_cache.clear()

                    # Set legacy config (only UUID, no name)
                    set_config_value("project-uuid", "old-uuid")

                    # Should detect missing project_name and fetch new UUID
                    result = get_project_uuid()
                    assert result == "fetched-uuid"

                    # Verify config was updated with both fields
                    assert get_config_value("project-name") == "test-project"
                    assert get_config_value("project-uuid") == "fetched-uuid"

    def test_no_env_var_uses_config_default(self, temp_config_dir, monkeypatch):
        """Test that no env var uses config as default."""
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
        monkeypatch.delenv("LANGSMITH_PROJECT_UUID", raising=False)

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                from langsmith_cli.config import get_project_uuid, set_config_value

                # Set config
                set_config_value("project-name", "default-project")
                set_config_value("project-uuid", "default-uuid")

                # Should use config UUID without env var
                result = get_project_uuid()
                assert result == "default-uuid"

    def test_explicit_uuid_override(self, temp_config_dir, monkeypatch):
        """Test that LANGSMITH_PROJECT_UUID overrides everything."""
        monkeypatch.setenv("LANGSMITH_PROJECT", "test-project")
        monkeypatch.setenv("LANGSMITH_PROJECT_UUID", "override-uuid")

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                from langsmith_cli.config import get_project_uuid, set_config_value

                # Set config
                set_config_value("project-name", "config-project")
                set_config_value("project-uuid", "config-uuid")

                # LANGSMITH_PROJECT_UUID should override everything
                result = get_project_uuid()
                assert result == "override-uuid"

    def test_api_failure_handling(self, temp_config_dir, monkeypatch):
        """Test that API failure is handled gracefully."""
        from unittest.mock import MagicMock

        monkeypatch.setenv("LANGSMITH_PROJECT", "nonexistent")
        monkeypatch.setenv("LANGSMITH_API_KEY", TEST_API_KEY)

        mock_client = MagicMock()
        mock_client.read_project.side_effect = Exception("Project not found")

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                with patch("langsmith.Client", return_value=mock_client):
                    from langsmith_cli.config import get_project_uuid, get_config_value, set_config_value, _project_uuid_cache

                    # Clear cache
                    _project_uuid_cache.clear()

                    # Set old config
                    set_config_value("project-name", "old-project")
                    set_config_value("project-uuid", "old-uuid")

                    # Should return None on API failure
                    result = get_project_uuid()
                    assert result is None

                    # Verify config was NOT updated (preserves last known good state)
                    assert get_config_value("project-name") == "old-project"
                    assert get_config_value("project-uuid") == "old-uuid"

    def test_cache_clears_on_manual_update(self, temp_config_dir):
        """Test that in-memory cache clears when project_uuid is manually set."""
        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                from langsmith_cli.config import set_config_value, _project_uuid_cache

                # Populate cache
                _project_uuid_cache["test-project"] = "cached-uuid"

                # Manually set project_uuid
                set_config_value("project-uuid", "new-uuid")

                # Cache should be cleared
                assert len(_project_uuid_cache) == 0

    def test_in_memory_cache_updates_config(self, temp_config_dir, monkeypatch):
        """Test that in-memory cache updates config when out of sync."""
        monkeypatch.setenv("LANGSMITH_PROJECT", "cached-project")

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                from langsmith_cli.config import get_project_uuid, set_config_value, get_config_value, _project_uuid_cache

                # Set old config
                set_config_value("project-name", "old-project")
                set_config_value("project-uuid", "old-uuid")

                # Populate in-memory cache with different project
                _project_uuid_cache["cached-project"] = "cached-uuid"

                # Should use cache and update config
                result = get_project_uuid()
                assert result == "cached-uuid"

                # Verify config was updated
                assert get_config_value("project-name") == "cached-project"
                assert get_config_value("project-uuid") == "cached-uuid"

    def test_empty_project_name_handling(self, temp_config_dir, monkeypatch):
        """Test graceful handling of empty project name."""
        monkeypatch.setenv("LANGSMITH_PROJECT", "")

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                from langsmith_cli.config import get_project_uuid, set_config_value

                # Set config
                set_config_value("project-uuid", "config-uuid")

                # Empty string should be treated as no env var
                result = get_project_uuid()
                assert result == "config-uuid"

    def test_project_uuid_persists_after_lookup(self, temp_config_dir, monkeypatch):
        """Test that both project_name and project_uuid persist after lookup."""
        from unittest.mock import Mock, MagicMock

        monkeypatch.setenv("LANGSMITH_PROJECT", "persist-project")
        monkeypatch.setenv("LANGSMITH_API_KEY", TEST_API_KEY)

        mock_project = Mock()
        mock_project.id = "persist-uuid"
        mock_project.name = "persist-project"

        mock_client = MagicMock()
        mock_client.read_project.return_value = mock_project

        with patch("langsmith_cli.config.CONFIG_DIR", temp_config_dir):
            with patch("langsmith_cli.config.CONFIG_FILE", temp_config_dir / "config.yaml"):
                with patch("langsmith.Client", return_value=mock_client):
                    from langsmith_cli.config import get_project_uuid, get_config_value, _project_uuid_cache

                    # Clear cache
                    _project_uuid_cache.clear()

                    # First call should fetch and persist
                    result = get_project_uuid()
                    assert result == "persist-uuid"

                    # Verify both fields were persisted
                    assert get_config_value("project-name") == "persist-project"
                    assert get_config_value("project-uuid") == "persist-uuid"
