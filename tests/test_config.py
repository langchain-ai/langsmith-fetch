"""Tests for config commands."""

import pytest
from click.testing import CliRunner
from unittest.mock import patch

from langsmith_cli.cli import main
from langsmith_cli import config
from tests.conftest import TEST_PROJECT_UUID, TEST_API_KEY


class TestConfigSet:
    """Tests for config set command."""

    def test_set_project_uuid(self, temp_config_dir):
        """Test setting project UUID."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                runner = CliRunner()
                result = runner.invoke(main, [
                    'config', 'set', 'project-uuid', TEST_PROJECT_UUID
                ])

                assert result.exit_code == 0
                assert "Set project-uuid" in result.output
                assert TEST_PROJECT_UUID in result.output

                # Verify it was saved
                from langsmith_cli.config import get_config_value
                assert get_config_value('project-uuid') == TEST_PROJECT_UUID

    def test_set_api_key(self, temp_config_dir):
        """Test setting API key."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                runner = CliRunner()
                result = runner.invoke(main, [
                    'config', 'set', 'api-key', TEST_API_KEY
                ])

                assert result.exit_code == 0
                assert "Set api-key" in result.output

                # Verify it was saved
                from langsmith_cli.config import get_config_value
                assert get_config_value('api-key') == TEST_API_KEY

    def test_set_default_format_pretty(self, temp_config_dir):
        """Test setting default format to pretty."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                runner = CliRunner()
                result = runner.invoke(main, [
                    'config', 'set', 'default-format', 'pretty'
                ])

                assert result.exit_code == 0
                assert "Set default-format" in result.output
                assert "pretty" in result.output

                # Verify it was saved
                from langsmith_cli.config import get_config_value
                assert get_config_value('default-format') == 'pretty'

    def test_set_default_format_json(self, temp_config_dir):
        """Test setting default format to json."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                runner = CliRunner()
                result = runner.invoke(main, [
                    'config', 'set', 'default-format', 'json'
                ])

                assert result.exit_code == 0
                from langsmith_cli.config import get_config_value
                assert get_config_value('default-format') == 'json'

    def test_set_default_format_raw(self, temp_config_dir):
        """Test setting default format to raw."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                runner = CliRunner()
                result = runner.invoke(main, [
                    'config', 'set', 'default-format', 'raw'
                ])

                assert result.exit_code == 0
                from langsmith_cli.config import get_config_value
                assert get_config_value('default-format') == 'raw'


class TestConfigShow:
    """Tests for config show command."""

    def test_show_empty_config(self, temp_config_dir):
        """Test showing config when empty."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                runner = CliRunner()
                result = runner.invoke(main, ['config', 'show'])

                assert result.exit_code == 0
                assert "No configuration found" in result.output

    def test_show_with_project_uuid(self, temp_config_dir):
        """Test showing config with project UUID."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                # Set config
                from langsmith_cli.config import set_config_value
                set_config_value('project-uuid', TEST_PROJECT_UUID)

                runner = CliRunner()
                result = runner.invoke(main, ['config', 'show'])

                assert result.exit_code == 0
                assert "Current configuration:" in result.output
                assert TEST_PROJECT_UUID in result.output

    def test_show_with_api_key_masked(self, temp_config_dir):
        """Test showing config with API key (should be masked)."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                # Set config
                from langsmith_cli.config import set_config_value
                set_config_value('api-key', TEST_API_KEY)

                runner = CliRunner()
                result = runner.invoke(main, ['config', 'show'])

                assert result.exit_code == 0
                # Should show only first 10 chars
                assert TEST_API_KEY[:10] in result.output
                assert "..." in result.output
                # Should not show full key
                assert TEST_API_KEY not in result.output

    def test_show_all_config_options(self, temp_config_dir):
        """Test showing config with all options set."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                # Set all config options
                from langsmith_cli.config import set_config_value
                set_config_value('project-uuid', TEST_PROJECT_UUID)
                set_config_value('api-key', TEST_API_KEY)
                set_config_value('default-format', 'json')

                runner = CliRunner()
                result = runner.invoke(main, ['config', 'show'])

                assert result.exit_code == 0
                assert "Current configuration:" in result.output
                assert TEST_PROJECT_UUID in result.output
                assert TEST_API_KEY[:10] in result.output
                assert "json" in result.output


class TestConfigFunctions:
    """Tests for config module functions."""

    def test_get_api_key_from_config(self, temp_config_dir, monkeypatch):
        """Test getting API key from config."""
        monkeypatch.delenv('LANGSMITH_API_KEY', raising=False)

        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                from langsmith_cli.config import set_config_value, get_api_key
                set_config_value('api-key', TEST_API_KEY)

                assert get_api_key() == TEST_API_KEY

    def test_get_api_key_from_env(self, temp_config_dir, monkeypatch):
        """Test getting API key from environment variable."""
        monkeypatch.setenv('LANGSMITH_API_KEY', 'env_api_key')

        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                from langsmith_cli.config import get_api_key
                # Env var should take precedence over config
                assert get_api_key() == 'env_api_key'

    def test_get_project_uuid(self, temp_config_dir):
        """Test getting project UUID from config."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                from langsmith_cli.config import set_config_value, get_project_uuid
                set_config_value('project-uuid', TEST_PROJECT_UUID)

                assert get_project_uuid() == TEST_PROJECT_UUID

    def test_get_default_format(self, temp_config_dir):
        """Test getting default format from config."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                from langsmith_cli.config import set_config_value, get_default_format

                # Default should be 'pretty'
                assert get_default_format() == 'pretty'

                # Set to 'json'
                set_config_value('default-format', 'json')
                assert get_default_format() == 'json'

    def test_config_key_with_hyphen_and_underscore(self, temp_config_dir):
        """Test that config keys work with both hyphens and underscores."""
        with patch('langsmith_cli.config.CONFIG_DIR', temp_config_dir):
            with patch('langsmith_cli.config.CONFIG_FILE', temp_config_dir / 'config.yaml'):
                from langsmith_cli.config import set_config_value, get_config_value

                # Set with hyphen
                set_config_value('project-uuid', TEST_PROJECT_UUID)

                # Get with underscore should also work
                assert get_config_value('project_uuid') == TEST_PROJECT_UUID
                # Get with hyphen should work
                assert get_config_value('project-uuid') == TEST_PROJECT_UUID
