"""Tests for public module."""

import pytest

from langsmith_cli.public import parse_langsmith_url


class TestParseLangsmithUrl:
    """Tests for parse_langsmith_url function."""

    def test_parse_langsmith_url_public_simple(self):
        """Test parsing simple public URL."""
        url = "https://smith.langchain.com/public/abc123-def456-ghi789/r"
        result = parse_langsmith_url(url)

        assert result["trace_id"] == "abc123-def456-ghi789"
        assert result["is_public"] is True
        assert result["org_slug"] is None
        assert result["url_type"] == "public_share"

    def test_parse_langsmith_url_public_with_org(self):
        """Test parsing public URL with org slug."""
        url = "https://smith.langchain.com/public/myorg/abc123-def456/r"
        result = parse_langsmith_url(url)

        assert result["trace_id"] == "abc123-def456"
        assert result["is_public"] is True
        assert result["org_slug"] == "myorg"
        assert result["url_type"] == "public_share"

    def test_parse_langsmith_url_public_no_r_suffix(self):
        """Test parsing public URL without /r suffix."""
        url = "https://smith.langchain.com/public/abc123-def456"
        result = parse_langsmith_url(url)

        assert result["trace_id"] == "abc123-def456"
        assert result["is_public"] is True

    def test_parse_langsmith_url_project_trace(self):
        """Test parsing authenticated project URL."""
        url = "https://smith.langchain.com/o/org-123/projects/p/proj-456/r/run-789"
        result = parse_langsmith_url(url)

        assert result["trace_id"] == "run-789"
        assert result["is_public"] is False
        assert result["org_slug"] == "org-123"
        assert result["project_id"] == "proj-456"
        assert result["url_type"] == "project_trace"

    def test_parse_langsmith_url_project_trace_with_share(self):
        """Test parsing project URL with share=true."""
        url = "https://smith.langchain.com/o/org-123/projects/p/proj-456/r/run-789?share=true"
        result = parse_langsmith_url(url)

        assert result["trace_id"] == "run-789"
        assert result["is_public"] is True
        assert result["url_type"] == "project_trace"

    def test_parse_langsmith_url_invalid_not_langsmith(self):
        """Test that invalid URLs raise ValueError."""
        with pytest.raises(ValueError, match="Not a LangSmith URL"):
            parse_langsmith_url("https://example.com/public/abc123/r")

    def test_parse_langsmith_url_invalid_format(self):
        """Test that unrecognized format raises ValueError."""
        with pytest.raises(ValueError, match="Unrecognized LangSmith URL format"):
            parse_langsmith_url("https://smith.langchain.com/unknown/path")

    def test_parse_langsmith_url_uuid_trace_id(self):
        """Test parsing URL with UUID trace ID."""
        url = "https://smith.langchain.com/public/3b0b15fe-1e3a-4aef-afa8-48df15879cfe/r"
        result = parse_langsmith_url(url)

        assert result["trace_id"] == "3b0b15fe-1e3a-4aef-afa8-48df15879cfe"
        assert result["is_public"] is True

    def test_parse_langsmith_url_direct_run(self):
        """Test parsing direct run URL."""
        url = "https://smith.langchain.com/runs/3b0b15fe-1e3a-4aef-afa8-48df15879cfe"
        result = parse_langsmith_url(url)

        assert result["trace_id"] == "3b0b15fe-1e3a-4aef-afa8-48df15879cfe"
        assert result["url_type"] == "direct_run"

    def test_parse_langsmith_url_preserves_case(self):
        """Test that trace IDs preserve case sensitivity."""
        url = "https://smith.langchain.com/public/AbC123-DeF456/r"
        result = parse_langsmith_url(url)

        assert result["trace_id"] == "AbC123-DeF456"

    def test_parse_langsmith_url_with_trailing_slash(self):
        """Test URL with trailing slash."""
        url = "https://smith.langchain.com/public/abc123/r/"
        result = parse_langsmith_url(url)

        # Should handle trailing slash gracefully
        assert result["is_public"] is True

    def test_parse_langsmith_url_with_query_params(self):
        """Test URL with additional query params."""
        url = "https://smith.langchain.com/public/abc123/r?tab=details&foo=bar"
        result = parse_langsmith_url(url)

        assert result["trace_id"] == "abc123"
        assert result["is_public"] is True
