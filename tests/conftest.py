"""Pytest configuration and fixtures."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Test IDs from examples
TEST_TRACE_ID = "3b0b15fe-1e3a-4aef-afa8-48df15879cfe"
TEST_THREAD_ID = "test-email-agent-thread"
TEST_PROJECT_UUID = "80f1ecb3-a16b-411e-97ae-1c89adbb5c49"
TEST_API_KEY = "lsv2_test_key_123"
TEST_BASE_URL = "https://api.smith.langchain.com"


@pytest.fixture
def sample_trace_response():
    """Sample trace API response."""
    return {
        "outputs": {
            "messages": [
                {
                    "content": "\n**Subject**: Quick question about next week\n**From**: jane@example.com\n**To**: lance@langchain.dev\n\nHi Lance,\n\nCan we meet next Tuesday at 2pm to discuss the project roadmap?\n\nBest,\nJane\n\n---\n",
                    "additional_kwargs": {},
                    "response_metadata": {},
                    "type": "human",
                    "id": "964d69c7-10e2-4de2-89c9-4361c9ea5da7",
                },
                {
                    "content": [
                        {
                            "id": "toolu_014c7iukFSFTMFTAJwGhqK8U",
                            "input": {
                                "reasoning": "Meeting request",
                                "classification": "respond",
                            },
                            "name": "triage_email",
                            "type": "tool_use",
                        }
                    ],
                    "additional_kwargs": {},
                    "response_metadata": {},
                    "type": "ai",
                    "id": "msg-123",
                },
                {
                    "content": "Classification Decision: respond. Reasoning: This is a meeting request.",
                    "additional_kwargs": {},
                    "type": "tool",
                    "id": "tool-123",
                },
            ]
        }
    }


@pytest.fixture
def sample_thread_response():
    """Sample thread API response."""
    return {
        "previews": {
            "all_messages": """{"role": "user", "id": "964d69c7-10e2-4de2-89c9-4361c9ea5da7", "content": "\\n**Subject**: Quick question about next week\\n**From**: jane@example.com\\n**To**: lance@langchain.dev\\n\\nHi Lance,\\n\\nCan we meet next Tuesday at 2pm to discuss the project roadmap?\\n\\nBest,\\nJane\\n\\n---\\n"}

{"role": "assistant", "tool_calls": [{"id": "toolu_014c7iukFSFTMFTAJwGhqK8U", "type": "tool_use", "name": "triage_email"}]}

{"role": "tool", "content": "Classification Decision: respond."}"""
        }
    }


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory."""
    temp_dir = tempfile.mkdtemp()
    with patch("langsmith_cli.config.CONFIG_DIR", Path(temp_dir)):
        with patch("langsmith_cli.config.CONFIG_FILE", Path(temp_dir) / "config.yaml"):
            yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_env_api_key(monkeypatch):
    """Mock LANGSMITH_API_KEY environment variable."""
    monkeypatch.setenv("LANGSMITH_API_KEY", TEST_API_KEY)


@pytest.fixture(autouse=True)
def mock_base_url(monkeypatch):
    """Mock get_base_url to return TEST_BASE_URL."""
    from langsmith_cli import config

    monkeypatch.setattr(config, "get_base_url", lambda: TEST_BASE_URL)
