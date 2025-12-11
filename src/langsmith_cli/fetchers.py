"""Core fetching logic for LangSmith threads and traces."""

import json
import sys
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter
from typing import Any

import requests
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

try:
    from langsmith import Client  # noqa: F401

    HAS_LANGSMITH = True
except ImportError:
    HAS_LANGSMITH = False


def fetch_thread(
    thread_id: str, project_uuid: str, *, base_url: str, api_key: str
) -> list[dict[str, Any]]:
    """
    Fetch messages for a LangGraph thread by thread_id.

    Args:
        thread_id: LangGraph thread_id (e.g., 'test-email-agent-thread')
        project_uuid: LangSmith project UUID (session_id)
        base_url: LangSmith base URL
        api_key: LangSmith API key

    Returns:
        List of message dictionaries

    Raises:
        requests.HTTPError: If the API request fails
    """
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    url = f"{base_url}/runs/threads/{thread_id}"
    params = {"select": "all_messages", "session_id": project_uuid}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    data = response.json()
    messages_text = data["previews"]["all_messages"]

    # Parse the JSON messages (newline-separated JSON objects)
    messages = []
    for line in messages_text.strip().split("\n\n"):
        if line.strip():
            messages.append(json.loads(line))

    return messages


def fetch_trace(trace_id: str, *, base_url: str, api_key: str) -> list[dict[str, Any]]:
    """
    Fetch messages for a single trace by trace ID.

    Args:
        trace_id: LangSmith trace UUID
        base_url: LangSmith base URL
        api_key: LangSmith API key

    Returns:
        List of message dictionaries with structured content

    Raises:
        requests.HTTPError: If the API request fails
    """
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    url = f"{base_url}/runs/{trace_id}?include_messages=true"

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()

    # Extract messages from outputs
    messages = data.get("messages")
    output_messages = (data.get("outputs") or {}).get("messages")
    return messages or output_messages or []


def fetch_recent_threads(
    project_uuid: str,
    base_url: str,
    api_key: str,
    limit: int = 10,
    last_n_minutes: int | None = None,
    since: str | None = None,
) -> list[tuple[str, list[dict[str, Any]]]]:
    """
    Fetch recent threads for a project.

    Args:
        project_uuid: LangSmith project UUID (session_id)
        base_url: LangSmith base URL
        api_key: LangSmith API key
        limit: Maximum number of threads to return (default: 10)
        last_n_minutes: Optional time window to limit search. Only returns threads
            from the last N minutes. Mutually exclusive with `since`.
        since: Optional ISO timestamp string (e.g., "2025-12-09T10:00:00Z").
            Only returns threads since this time. Mutually exclusive with `last_n_minutes`.

    Returns:
        List of tuples (thread_id, messages) for each thread

    Raises:
        requests.HTTPError: If the API request fails
    """
    from datetime import datetime, timedelta, timezone

    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    # Query for root runs in the project
    url = f"{base_url}/runs/query"
    body = {"session": [project_uuid], "is_root": True}

    # Add time filtering if specified
    if last_n_minutes is not None:
        start_time = datetime.now(timezone.utc) - timedelta(minutes=last_n_minutes)
        body["start_time"] = start_time.isoformat()
    elif since is not None:
        # Parse ISO timestamp (handle both 'Z' and explicit timezone)
        since_clean = since.replace("Z", "+00:00")
        start_time = datetime.fromisoformat(since_clean)
        body["start_time"] = start_time.isoformat()

    response = requests.post(url, headers=headers, data=json.dumps(body))

    # Add better error handling
    try:
        response.raise_for_status()
    except requests.HTTPError:
        # Print response content for debugging
        print(f"API Error Response ({response.status_code}): {response.text}")
        print(f"Request body was: {json.dumps(body, indent=2)}")
        raise

    data = response.json()

    # The response should have a 'runs' key
    runs = data.get("runs", [])

    # Extract unique thread_ids with their most recent timestamp
    thread_info = OrderedDict()  # Maintains insertion order (most recent first)

    for run in runs:
        # Check if run has thread_id in metadata
        extra = run.get("extra", {})
        metadata = extra.get("metadata", {})
        thread_id = metadata.get("thread_id")

        if thread_id and thread_id not in thread_info:
            thread_info[thread_id] = run.get("start_time")

            # Stop if we've found enough unique threads
            if len(thread_info) >= limit:
                break

    # Fetch messages for each thread
    results = []
    for thread_id in thread_info.keys():
        try:
            messages = fetch_thread(
                thread_id, project_uuid, base_url=base_url, api_key=api_key
            )
            results.append((thread_id, messages))
        except Exception as e:
            # Log error but continue with other threads
            print(f"Warning: Failed to fetch thread {thread_id}: {e}")
            continue

    return results


def fetch_latest_trace(
    api_key: str,
    base_url: str,
    project_uuid: str | None = None,
    last_n_minutes: int | None = None,
    since: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch the most recent root trace from LangSmith.

    Uses the LangSmith SDK to list runs and find the latest trace, then
    fetches the full messages using the existing fetch_trace function.

    Args:
        api_key: LangSmith API key
        base_url: LangSmith base URL
        project_uuid: Optional project UUID to filter traces (if None, searches all projects)
        last_n_minutes: Optional time window in minutes to limit search
        since: Optional ISO timestamp string to limit search (e.g., '2025-12-09T10:00:00Z')

    Returns:
        List of message dictionaries from the latest trace

    Raises:
        ValueError: If no traces found matching criteria
        Exception: If API request fails
    """
    from datetime import datetime, timedelta, timezone

    from langsmith import Client

    # Initialize langsmith client
    client = Client(api_key=api_key)

    # Build filter parameters
    filter_params = {
        "filter": 'and(eq(is_root, true), neq(status, "pending"))',
        "limit": 1,
    }

    # Add project filter if provided
    if project_uuid is not None:
        filter_params["project_id"] = project_uuid

    # Add time filtering if specified
    if last_n_minutes is not None:
        start_time = datetime.now(timezone.utc) - timedelta(minutes=last_n_minutes)
        filter_params["start_time"] = start_time
    elif since is not None:
        # Parse ISO timestamp
        start_time = datetime.fromisoformat(since.replace("Z", "+00:00"))
        filter_params["start_time"] = start_time

    # Fetch latest run
    runs = list(client.list_runs(**filter_params))

    if not runs:
        raise ValueError("No traces found matching criteria")

    latest_run = runs[0]
    trace_id = str(latest_run.id)

    # Reuse existing fetch_trace to get full messages
    return fetch_trace(trace_id, base_url=base_url, api_key=api_key)


def _fetch_trace_safe(
    trace_id: str, base_url: str, api_key: str
) -> tuple[str, list[dict[str, Any]] | None, Exception | None]:
    """Fetch a single trace with error handling.

    Returns:
        Tuple of (trace_id, messages or None, error or None)
    """
    try:
        messages = fetch_trace(trace_id, base_url=base_url, api_key=api_key)
        return (trace_id, messages, None)
    except Exception as e:
        return (trace_id, None, e)


def _fetch_traces_concurrent(
    runs: list,
    base_url: str,
    api_key: str,
    max_workers: int = 5,
    show_progress: bool = True,
) -> tuple[list[tuple[str, list[dict[str, Any]]]], dict[str, float]]:
    """Fetch multiple traces concurrently with optional progress display.

    Args:
        runs: List of run objects from client.list_runs()
        base_url: LangSmith base URL
        api_key: LangSmith API key
        max_workers: Maximum number of concurrent requests (default: 5)
        show_progress: Whether to show progress bar (default: True)

    Returns:
        Tuple of (results list, timing_info dict)
    """
    results = []
    timing_info = {
        "fetch_start": perf_counter(),
        "traces_attempted": len(runs),
        "traces_succeeded": 0,
        "traces_failed": 0,
    }

    # For single trace, use simple sequential fetch (no progress overhead)
    if len(runs) == 1:
        trace_id = str(runs[0].id)
        try:
            start = perf_counter()
            messages = fetch_trace(trace_id, base_url=base_url, api_key=api_key)
            duration = perf_counter() - start
            results.append((trace_id, messages))
            timing_info["traces_succeeded"] = 1
            timing_info["individual_timings"] = [duration]
        except Exception as e:
            print(f"Warning: Failed to fetch trace {trace_id}: {e}", file=sys.stderr)
            timing_info["traces_failed"] = 1
            timing_info["individual_timings"] = []

        timing_info["fetch_duration"] = perf_counter() - timing_info["fetch_start"]
        return results, timing_info

    # Concurrent fetching with progress for multiple traces
    individual_timings = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all fetch tasks
        future_to_trace = {
            executor.submit(_fetch_trace_safe, str(run.id), base_url, api_key): str(run.id)
            for run in runs
        }

        # Setup progress bar if requested
        if show_progress:
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=Console(stderr=True),
            )
            progress.start()
            task = progress.add_task(
                f"[cyan]Fetching {len(runs)} traces...",
                total=len(runs),
            )

        # Collect results as they complete
        for future in as_completed(future_to_trace):
            trace_id, messages, error = future.result()

            if error:
                msg = f"Warning: Failed to fetch trace {trace_id}: {error}"
                if show_progress:
                    progress.console.print(f"[yellow]{msg}[/yellow]")
                else:
                    print(msg, file=sys.stderr)
                timing_info["traces_failed"] += 1
            else:
                results.append((trace_id, messages))
                timing_info["traces_succeeded"] += 1

            if show_progress:
                progress.update(task, advance=1)

        if show_progress:
            progress.stop()

    timing_info["fetch_duration"] = perf_counter() - timing_info["fetch_start"]
    timing_info["individual_timings"] = individual_timings
    if timing_info["traces_succeeded"] > 0:
        timing_info["avg_per_trace"] = (
            timing_info["fetch_duration"] / timing_info["traces_succeeded"]
        )

    return results, timing_info


def fetch_recent_traces(
    api_key: str,
    base_url: str,
    limit: int = 1,
    project_uuid: str | None = None,
    last_n_minutes: int | None = None,
    since: str | None = None,
    max_workers: int = 5,
    show_progress: bool = True,
    return_timing: bool = False,
) -> list[tuple[str, list[dict[str, Any]]]] | tuple[list[tuple[str, list[dict[str, Any]]]], dict]:
    """Fetch multiple recent traces from LangSmith with concurrent fetching.

    Searches for recent root traces by chronological timestamp and returns
    their messages. Uses concurrent fetching for improved performance when
    fetching multiple traces.

    Args:
        api_key: LangSmith API key for authentication
        base_url: LangSmith base URL (e.g., https://api.smith.langchain.com)
        limit: Maximum number of traces to fetch (default: 1)
        project_uuid: Optional project UUID to filter traces to a specific project.
            If not provided, searches across all projects.
        last_n_minutes: Optional time window to limit search. Only returns traces
            from the last N minutes. Mutually exclusive with `since`.
        since: Optional ISO timestamp string (e.g., "2025-12-09T10:00:00Z").
            Only returns traces since this time. Mutually exclusive with `last_n_minutes`.
        max_workers: Maximum number of concurrent fetch requests (default: 5)
        show_progress: Whether to show progress bar during fetching (default: True)
        return_timing: Whether to return timing information along with results (default: False)

    Returns:
        If return_timing=False (default):
            List of tuples (trace_id, messages) for each trace, ordered by most recent first.
        If return_timing=True:
            Tuple of (traces list, timing_dict) where timing_dict contains performance metrics.

    Raises:
        ValueError: If no traces found matching the criteria
        Exception: If API request fails or langsmith package not installed

    Example:
        >>> traces = fetch_recent_traces(
        ...     api_key="lsv2_...",
        ...     base_url="https://api.smith.langchain.com",
        ...     limit=5,
        ...     project_uuid="80f1ecb3-a16b-411e-97ae-1c89adbb5c49",
        ...     last_n_minutes=30,
        ...     max_workers=5
        ... )
        >>> for trace_id, messages in traces:
        ...     print(f"Trace {trace_id}: {len(messages)} messages")
    """
    if not HAS_LANGSMITH:
        raise Exception(
            "langsmith package required for fetching multiple traces. "
            "Install with: pip install langsmith"
        )

    from datetime import datetime, timedelta, timezone

    from langsmith import Client

    # Initialize client
    client = Client(api_key=api_key)

    # Build filter parameters
    filter_params = {
        "filter": 'and(eq(is_root, true), neq(status, "pending"))',
        "limit": limit,
    }

    if project_uuid is not None:
        filter_params["project_id"] = project_uuid

    # Add time filtering
    if last_n_minutes is not None:
        start_time = datetime.now(timezone.utc) - timedelta(minutes=last_n_minutes)
        filter_params["start_time"] = start_time
    elif since is not None:
        # Parse ISO timestamp (handle both 'Z' and explicit timezone)
        since_clean = since.replace("Z", "+00:00")
        start_time = datetime.fromisoformat(since_clean)
        filter_params["start_time"] = start_time

    # Fetch runs
    list_start = perf_counter()
    runs = list(client.list_runs(**filter_params))
    list_duration = perf_counter() - list_start

    if not runs:
        raise ValueError("No traces found matching criteria")

    # Fetch messages for each trace using concurrent fetching
    results, timing_info = _fetch_traces_concurrent(
        runs=runs,
        base_url=base_url,
        api_key=api_key,
        max_workers=max_workers,
        show_progress=show_progress,
    )

    if not results:
        raise ValueError(
            f"Successfully queried {len(runs)} traces but failed to fetch messages for all of them"
        )

    # Add list_runs timing to timing info
    timing_info["list_runs_duration"] = list_duration
    timing_info["total_duration"] = list_duration + timing_info["fetch_duration"]

    if return_timing:
        return results, timing_info
    return results
