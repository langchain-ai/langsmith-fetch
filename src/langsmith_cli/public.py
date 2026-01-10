"""Public trace support for LangSmith-Fetch."""

import re
from typing import Any
from urllib.parse import urlparse

import requests

from .fetchers import TREE_SELECT_FIELDS
from .tree import build_tree_from_runs, calculate_tree_summary, extract_run_summary


def parse_langsmith_url(url: str) -> dict[str, Any]:
    """
    Parse a LangSmith URL and extract trace identification.

    Args:
        url: Any LangSmith trace URL (public or authenticated)

    Returns:
        {
            "trace_id": str,
            "is_public": bool,
            "org_slug": str | None,
            "project_id": str | None,
            "url_type": "public_share" | "project_trace" | "direct_run"
        }

    Raises:
        ValueError: If URL format is not recognized

    Supported URL formats:
        - https://smith.langchain.com/public/{trace_id}/r
        - https://smith.langchain.com/public/{org_slug}/{trace_id}/r
        - https://smith.langchain.com/o/{org_id}/projects/p/{project_id}/r/{run_id}
        - https://smith.langchain.com/o/{org_id}/projects/p/{project_id}/r/{run_id}?share=true

    Examples:
        >>> parse_langsmith_url("https://smith.langchain.com/public/abc123/r")
        {"trace_id": "abc123", "is_public": True, "org_slug": None, ...}

        >>> parse_langsmith_url("https://smith.langchain.com/public/myorg/abc123/r")
        {"trace_id": "abc123", "is_public": True, "org_slug": "myorg", ...}
    """
    parsed = urlparse(url)

    # Validate it's a LangSmith URL
    if "smith.langchain.com" not in parsed.netloc:
        raise ValueError(
            f"Not a LangSmith URL: {url}. "
            "Expected URL from smith.langchain.com"
        )

    path = parsed.path.strip("/")
    path_parts = path.split("/")

    # Pattern 1: /public/{trace_id}/r
    # Pattern 2: /public/{org_slug}/{trace_id}/r
    if path_parts and path_parts[0] == "public":
        if len(path_parts) == 3 and path_parts[2] == "r":
            # /public/{trace_id}/r
            return {
                "trace_id": path_parts[1],
                "is_public": True,
                "org_slug": None,
                "project_id": None,
                "url_type": "public_share",
            }
        elif len(path_parts) == 4 and path_parts[3] == "r":
            # /public/{org_slug}/{trace_id}/r
            return {
                "trace_id": path_parts[2],
                "is_public": True,
                "org_slug": path_parts[1],
                "project_id": None,
                "url_type": "public_share",
            }
        elif len(path_parts) >= 2:
            # /public/{trace_id} (without /r)
            trace_id = path_parts[1]
            org_slug = None
            if len(path_parts) >= 3 and _is_uuid_like(path_parts[2]):
                # /public/{org_slug}/{trace_id}
                org_slug = path_parts[1]
                trace_id = path_parts[2]
            return {
                "trace_id": trace_id,
                "is_public": True,
                "org_slug": org_slug,
                "project_id": None,
                "url_type": "public_share",
            }

    # Pattern 3: /o/{org_id}/projects/p/{project_id}/r/{run_id}
    if len(path_parts) >= 6 and path_parts[0] == "o" and path_parts[2] == "projects":
        # /o/{org_id}/projects/p/{project_id}/r/{run_id}
        org_id = path_parts[1]
        project_id = path_parts[4] if len(path_parts) > 4 else None
        run_id = path_parts[6] if len(path_parts) > 6 else None

        # Check if it's marked as public via query param
        is_public = "share=true" in (parsed.query or "").lower()

        return {
            "trace_id": run_id,
            "is_public": is_public,
            "org_slug": org_id,
            "project_id": project_id,
            "url_type": "project_trace",
        }

    # Pattern 4: Direct run URL patterns
    # /runs/{run_id} or /run/{run_id} or /r/{run_id}
    # Note: path is already stripped of leading/trailing slashes
    run_match = re.search(r"(?:^|/)(?:runs?|r)/([0-9a-f-]{36})(?:/|$)", path, re.IGNORECASE)
    if run_match:
        run_id = run_match.group(1)
        is_public = "share=true" in (parsed.query or "").lower() or "/public/" in path
        return {
            "trace_id": run_id,
            "is_public": is_public,
            "org_slug": None,
            "project_id": None,
            "url_type": "direct_run",
        }

    raise ValueError(
        f"Unrecognized LangSmith URL format: {url}. "
        "Expected formats: "
        "https://smith.langchain.com/public/{trace_id}/r or "
        "https://smith.langchain.com/o/{org}/projects/p/{project}/r/{run_id}"
    )


def _is_uuid_like(s: str) -> bool:
    """Check if string looks like a UUID."""
    # UUID pattern: 8-4-4-4-12 hex chars
    uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    return bool(re.match(uuid_pattern, s, re.IGNORECASE))


def fetch_public_trace_tree(
    url_or_trace_id: str,
    *,
    base_url: str = "https://api.smith.langchain.com",
) -> dict[str, Any]:
    """
    Fetch trace tree from a public share URL (no auth required).

    Args:
        url_or_trace_id: Public URL or trace ID
        base_url: API base URL (default: production LangSmith)

    Returns:
        Same structure as fetch_trace_tree():
        {
            "trace_id": str,
            "fetched_at": str,
            "total_runs": int,
            "root": {...},
            "runs_flat": [...],
            "runs_by_id": {...},
            "tree": {...},
            "summary": {...}
        }

    Raises:
        ValueError: If trace is not publicly shared
        requests.HTTPError: If API request fails
    """
    from datetime import datetime, timezone

    # Parse URL if needed
    if url_or_trace_id.startswith("http"):
        parsed = parse_langsmith_url(url_or_trace_id)
        if not parsed["is_public"]:
            raise ValueError(
                "URL does not appear to be a public share link. "
                "Use LANGSMITH_API_KEY for non-public traces."
            )
        trace_id = parsed["trace_id"]
        org_slug = parsed.get("org_slug")
    else:
        trace_id = url_or_trace_id
        org_slug = None

    # Try public API endpoint
    # The public endpoint structure varies - try different approaches
    headers = {"Content-Type": "application/json"}

    # Approach 1: Try the public share endpoint
    # POST /public/{share_token}/runs/query
    if org_slug:
        url = f"{base_url}/public/{org_slug}/{trace_id}/runs/query"
    else:
        url = f"{base_url}/public/{trace_id}/runs/query"

    body = {
        "trace_id": trace_id,
        "select": TREE_SELECT_FIELDS,
        "limit": 1000,
    }

    response = requests.post(url, headers=headers, json=body, timeout=30)

    # If the first approach fails, try alternative endpoints
    if response.status_code == 404:
        # Approach 2: Try querying by share token directly
        url = f"{base_url}/public/{trace_id}/runs"
        response = requests.get(url, headers=headers, timeout=30)

    if response.status_code == 403:
        raise ValueError(
            "Trace is not publicly shared. "
            "Set LANGSMITH_API_KEY for authenticated access."
        )
    if response.status_code == 404:
        raise ValueError(f"Public trace not found: {trace_id}")

    response.raise_for_status()

    data = response.json()

    # Handle different response formats
    if isinstance(data, list):
        all_runs = data
    else:
        all_runs = data.get("runs", [])

    if not all_runs:
        raise ValueError(f"No runs found for public trace: {trace_id}")

    # Build tree structure
    tree = build_tree_from_runs(all_runs)

    # Calculate summary statistics
    summary = calculate_tree_summary(all_runs)

    # Build runs_by_id lookup
    runs_by_id = {}
    root_summary = None
    for run in all_runs:
        run_summary = extract_run_summary(run)
        runs_by_id[run["id"]] = run_summary
        if run.get("parent_run_id") is None:
            root_summary = run_summary

    fetched_at = datetime.now(timezone.utc).isoformat()

    return {
        "trace_id": trace_id,
        "fetched_at": fetched_at,
        "total_runs": len(all_runs),
        "root": root_summary,
        "runs_flat": all_runs,
        "runs_by_id": runs_by_id,
        "tree": tree,
        "summary": summary,
    }


def fetch_public_run(
    run_id: str,
    share_token: str | None = None,
    *,
    base_url: str = "https://api.smith.langchain.com",
) -> dict[str, Any]:
    """
    Fetch complete data for a single run from a public trace.

    Args:
        run_id: The run UUID
        share_token: Optional share token if different from run_id
        base_url: API base URL

    Returns:
        Complete run data including inputs and outputs

    Raises:
        ValueError: If run is not publicly accessible
        requests.HTTPError: If API request fails
    """
    headers = {"Content-Type": "application/json"}

    # Try public endpoint
    token = share_token or run_id
    url = f"{base_url}/public/{token}/runs/{run_id}"

    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code == 403:
        raise ValueError(
            "Run is not publicly accessible. "
            "Set LANGSMITH_API_KEY for authenticated access."
        )
    if response.status_code == 404:
        raise ValueError(f"Public run not found: {run_id}")

    response.raise_for_status()

    return response.json()
