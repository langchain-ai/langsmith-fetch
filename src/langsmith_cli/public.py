"""Public trace support for LangSmith-Fetch."""

import re
from typing import Any
from urllib.parse import urlparse

import requests

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


def _fetch_public_runs_batch(
    share_token: str,
    base_url: str,
    max_runs: int = 1000,
) -> list[dict]:
    """
    Fetch all runs from a public trace using batch requests.

    Uses the id filter in /runs/query to fetch multiple runs per request,
    which is much more efficient than fetching one at a time.
    """
    headers = {"Content-Type": "application/json"}
    all_runs: list[dict] = []
    visited: set[str] = set()
    to_fetch: list[str] = []

    # Fetch the root run first
    root_url = f"{base_url}/public/{share_token}/run"
    response = requests.get(root_url, headers=headers, timeout=30)

    if response.status_code == 403:
        raise ValueError(
            "Trace is not publicly shared. "
            "Set LANGSMITH_API_KEY for authenticated access."
        )
    if response.status_code == 404:
        raise ValueError(f"Public trace not found: {share_token}")

    response.raise_for_status()
    root = response.json()

    root_id = root.get("id")
    visited.add(root_id)
    all_runs.append(root)

    # Queue all child IDs for batch fetching
    to_fetch = list(root.get("child_run_ids") or [])

    # Batch fetch children level by level
    query_url = f"{base_url}/public/{share_token}/runs/query"

    while to_fetch and len(all_runs) < max_runs:
        # Take up to 100 IDs per batch (API limit)
        batch = to_fetch[:100]
        to_fetch = to_fetch[100:]

        # Skip already visited IDs
        batch = [rid for rid in batch if rid not in visited]
        if not batch:
            continue

        body = {"id": batch, "limit": 100}
        response = requests.post(query_url, headers=headers, json=body, timeout=30)

        if response.status_code != 200:
            # If batch fetch fails, skip this batch
            continue

        data = response.json()
        runs = data.get("runs", [])

        for run in runs:
            run_id = run.get("id")
            if run_id not in visited:
                visited.add(run_id)
                all_runs.append(run)

                # Queue this run's children
                child_ids = run.get("child_run_ids") or []
                for cid in child_ids:
                    if cid not in visited and cid not in to_fetch:
                        to_fetch.append(cid)

            if len(all_runs) >= max_runs:
                break

    return all_runs


def fetch_public_trace_tree(
    url_or_trace_id: str,
    *,
    base_url: str = "https://api.smith.langchain.com",
    max_runs: int = 1000,
) -> dict[str, Any]:
    """
    Fetch trace tree from a public share URL (no auth required).

    Args:
        url_or_trace_id: Public URL or share token
        base_url: API base URL (default: production LangSmith)
        max_runs: Maximum runs to fetch (default 1000)

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

    Note:
        The public API requires fetching each run individually and
        recursively traversing child_run_ids to build the full tree.
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
        share_token = parsed["trace_id"]
    else:
        share_token = url_or_trace_id

    # Fetch all runs using batch requests
    all_runs = _fetch_public_runs_batch(share_token, base_url, max_runs)

    if not all_runs:
        raise ValueError(f"No runs found for public trace: {share_token}")

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
        "trace_id": share_token,
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
