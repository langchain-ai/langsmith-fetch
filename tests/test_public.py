"""Tests for public module."""

import pytest
import responses

from langsmith_cli.public import (
    fetch_public_run,
    fetch_public_trace_tree,
    parse_langsmith_url,
)


TEST_BASE_URL = "https://api.smith.langchain.com"


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


class TestFetchPublicTraceTree:
    """Tests for fetch_public_trace_tree function."""

    @responses.activate
    def test_fetch_public_trace_tree_success(self):
        """Test successful public trace tree fetch."""
        trace_id = "abc123-def456"

        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/public/{trace_id}/runs/query",
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
                        "total_tokens": 50,
                        "total_cost": 0.005,
                        "extra": {},
                    },
                ]
            },
            status=200,
        )

        result = fetch_public_trace_tree(trace_id, base_url=TEST_BASE_URL)

        assert result["trace_id"] == trace_id
        assert result["total_runs"] == 2
        assert result["tree"] is not None
        assert result["summary"]["total_runs"] == 2

    @responses.activate
    def test_fetch_public_trace_tree_from_url(self):
        """Test fetching public trace tree from a URL."""
        trace_id = "abc123-def456"
        url = f"https://smith.langchain.com/public/{trace_id}/r"

        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/public/{trace_id}/runs/query",
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
                        "extra": {},
                    },
                ]
            },
            status=200,
        )

        result = fetch_public_trace_tree(url, base_url=TEST_BASE_URL)

        assert result["trace_id"] == trace_id
        assert result["total_runs"] == 1

    @responses.activate
    def test_fetch_public_trace_tree_with_org_slug(self):
        """Test fetching with org slug in URL."""
        org_slug = "myorg"
        trace_id = "abc123-def456"
        url = f"https://smith.langchain.com/public/{org_slug}/{trace_id}/r"

        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/public/{org_slug}/{trace_id}/runs/query",
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
                        "extra": {},
                    },
                ]
            },
            status=200,
        )

        result = fetch_public_trace_tree(url, base_url=TEST_BASE_URL)

        assert result["trace_id"] == trace_id

    @responses.activate
    def test_fetch_public_trace_tree_403_forbidden(self):
        """Test 403 error raises ValueError."""
        trace_id = "private-trace"

        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/public/{trace_id}/runs/query",
            json={"error": "Forbidden"},
            status=403,
        )

        with pytest.raises(ValueError, match="not publicly shared"):
            fetch_public_trace_tree(trace_id, base_url=TEST_BASE_URL)

    @responses.activate
    def test_fetch_public_trace_tree_404_not_found(self):
        """Test 404 error raises ValueError."""
        trace_id = "nonexistent-trace"

        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/public/{trace_id}/runs/query",
            json={"error": "Not found"},
            status=404,
        )

        # Try alternative endpoint
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/public/{trace_id}/runs",
            json={"error": "Not found"},
            status=404,
        )

        with pytest.raises(ValueError, match="not found"):
            fetch_public_trace_tree(trace_id, base_url=TEST_BASE_URL)

    @responses.activate
    def test_fetch_public_trace_tree_empty_runs(self):
        """Test empty runs raises ValueError."""
        trace_id = "empty-trace"

        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/public/{trace_id}/runs/query",
            json={"runs": []},
            status=200,
        )

        with pytest.raises(ValueError, match="No runs found"):
            fetch_public_trace_tree(trace_id, base_url=TEST_BASE_URL)

    def test_fetch_public_trace_tree_non_public_url(self):
        """Test non-public URL raises ValueError."""
        url = "https://smith.langchain.com/o/org-123/projects/p/proj-456/r/run-789"

        with pytest.raises(ValueError, match="not appear to be a public share link"):
            fetch_public_trace_tree(url, base_url=TEST_BASE_URL)

    @responses.activate
    def test_fetch_public_trace_tree_list_response(self):
        """Test handling response as list (alternative format)."""
        trace_id = "abc123"

        # First request returns 404
        responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/public/{trace_id}/runs/query",
            status=404,
        )

        # Fallback returns list directly
        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/public/{trace_id}/runs",
            json=[
                {
                    "id": "root-run",
                    "name": "rootRun",
                    "run_type": "chain",
                    "parent_run_id": None,
                    "child_run_ids": [],
                    "dotted_order": "1",
                    "status": "success",
                    "extra": {},
                },
            ],
            status=200,
        )

        result = fetch_public_trace_tree(trace_id, base_url=TEST_BASE_URL)

        assert result["trace_id"] == trace_id
        assert result["total_runs"] == 1


class TestFetchPublicRun:
    """Tests for fetch_public_run function."""

    @responses.activate
    def test_fetch_public_run_success(self):
        """Test successful public run fetch."""
        run_id = "run-123-456"

        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/public/{run_id}/runs/{run_id}",
            json={
                "id": run_id,
                "name": "testRun",
                "run_type": "llm",
                "status": "success",
                "inputs": {"prompt": "Hello"},
                "outputs": {"text": "Hi there"},
            },
            status=200,
        )

        result = fetch_public_run(run_id, base_url=TEST_BASE_URL)

        assert result["id"] == run_id
        assert result["name"] == "testRun"
        assert result["inputs"]["prompt"] == "Hello"

    @responses.activate
    def test_fetch_public_run_with_share_token(self):
        """Test fetching with separate share token."""
        run_id = "run-123-456"
        share_token = "share-token-abc"

        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/public/{share_token}/runs/{run_id}",
            json={
                "id": run_id,
                "name": "testRun",
                "status": "success",
            },
            status=200,
        )

        result = fetch_public_run(run_id, share_token=share_token, base_url=TEST_BASE_URL)

        assert result["id"] == run_id

    @responses.activate
    def test_fetch_public_run_403_forbidden(self):
        """Test 403 error raises ValueError."""
        run_id = "private-run"

        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/public/{run_id}/runs/{run_id}",
            json={"error": "Forbidden"},
            status=403,
        )

        with pytest.raises(ValueError, match="not publicly accessible"):
            fetch_public_run(run_id, base_url=TEST_BASE_URL)

    @responses.activate
    def test_fetch_public_run_404_not_found(self):
        """Test 404 error raises ValueError."""
        run_id = "nonexistent-run"

        responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/public/{run_id}/runs/{run_id}",
            json={"error": "Not found"},
            status=404,
        )

        with pytest.raises(ValueError, match="not found"):
            fetch_public_run(run_id, base_url=TEST_BASE_URL)
