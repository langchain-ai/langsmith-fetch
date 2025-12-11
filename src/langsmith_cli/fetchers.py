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
    max_workers: int = 5,
    show_progress: bool = True,
) -> list[tuple[str, list[dict[str, Any]]]]:
    """
    Fetch recent threads for a project with concurrent fetching.

    Args:
        project_uuid: LangSmith project UUID (session_id)
        base_url: LangSmith base URL
        api_key: LangSmith API key
        limit: Maximum number of threads to return (default: 10)
        last_n_minutes: Optional time window to limit search. Only returns threads
            from the last N minutes. Mutually exclusive with `since`.
        since: Optional ISO timestamp string (e.g., "2025-12-09T10:00:00Z").
            Only returns threads since this time. Mutually exclusive with `last_n_minutes`.
        max_workers: Maximum concurrent thread fetches (default: 5)
        show_progress: Whether to show progress bar (default: True)

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

    # Fetch messages for each thread with concurrent fetching and progress bar
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    import sys

    def _fetch_thread_safe(thread_id: str) -> tuple[str, list[dict[str, Any]] | None]:
        """Safe wrapper for fetch_thread that returns (thread_id, messages or None)."""
        try:
            messages = fetch_thread(
                thread_id, project_uuid, base_url=base_url, api_key=api_key
            )
            return (thread_id, messages)
        except Exception as e:
            print(f"Warning: Failed to fetch thread {thread_id}: {e}", file=sys.stderr)
            return (thread_id, None)

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all fetch tasks
        future_to_thread = {
            executor.submit(_fetch_thread_safe, thread_id): thread_id
            for thread_id in thread_info.keys()
        }

        # Use progress bar if requested
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Fetching {task.completed}/{task.total} threads..."),
                BarColumn(),
                TaskProgressColumn(),
            ) as progress:
                task = progress.add_task("fetch", total=len(future_to_thread))

                for future in as_completed(future_to_thread):
                    thread_id, messages = future.result()
                    if messages is not None:
                        results.append((thread_id, messages))
                    progress.update(task, advance=1)
        else:
            # No progress bar - just collect results
            for future in as_completed(future_to_thread):
                thread_id, messages = future.result()
                if messages is not None:
                    results.append((thread_id, messages))

    # Sort results to match original chronological order from thread_info
    thread_id_order = list(thread_info.keys())
    results.sort(key=lambda x: thread_id_order.index(x[0]))

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
    include_metadata: bool = False,
    include_feedback: bool = False,
) -> tuple[list[tuple[str, list[dict[str, Any]] | dict[str, Any]]], dict[str, float]]:
    """Fetch multiple traces concurrently with optional progress display.

    Args:
        runs: List of run objects from client.list_runs()
        base_url: LangSmith base URL
        api_key: LangSmith API key
        max_workers: Maximum number of concurrent requests (default: 5)
        show_progress: Whether to show progress bar (default: True)
        include_metadata: Whether to include metadata in results (default: False)
        include_feedback: Whether to fetch full feedback objects (default: False)

    Returns:
        Tuple of (results list, timing_info dict)
        If include_metadata=False: results are (trace_id, messages) tuples (backward compatible)
        If include_metadata=True: results are (trace_id, trace_data_dict) tuples
    """
    results = []
    timing_info = {
        "fetch_start": perf_counter(),
        "traces_attempted": len(runs),
        "traces_succeeded": 0,
        "traces_failed": 0,
    }

    # Extract metadata from Run objects we already have (no extra API calls!)
    run_metadata_map = {}
    runs_with_feedback = []
    if include_metadata:
        for run in runs:
            trace_id = str(run.id)
            run_metadata_map[trace_id] = _extract_run_metadata_from_sdk_run(run)
            if include_feedback and _sdk_run_has_feedback(run):
                runs_with_feedback.append(trace_id)

    # Concurrent fetching with progress (for all traces, including single)
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
                if include_metadata:
                    trace_data = {
                        "trace_id": trace_id,
                        "messages": messages,
                        "metadata": run_metadata_map.get(trace_id, {}),
                        "feedback": [],
                    }
                    results.append((trace_id, trace_data))
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

    # Batch fetch feedback for all runs that have it
    if include_metadata and include_feedback and runs_with_feedback:
        feedback_start = perf_counter()
        feedback_map = _fetch_feedback_batch(runs_with_feedback, api_key, max_workers)
        timing_info["feedback_duration"] = perf_counter() - feedback_start

        # Add feedback to corresponding traces
        for idx, (trace_id, trace_data) in enumerate(results):
            if trace_id in feedback_map:
                trace_data["feedback"] = feedback_map[trace_id]

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
    include_metadata: bool = False,
    include_feedback: bool = False,
) -> list[tuple[str, list[dict[str, Any]] | dict[str, Any]]] | tuple[list[tuple[str, list[dict[str, Any]] | dict[str, Any]]], dict]:
    """Fetch multiple recent traces from LangSmith with concurrent fetching.

    Searches for recent root traces by chronological timestamp and returns
    their messages with metadata and feedback. Uses concurrent fetching for
    improved performance when fetching multiple traces.

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
        include_metadata: Whether to include metadata in results (default: True)
        include_feedback: Whether to fetch full feedback objects (default: True)

    Returns:
        If return_timing=False (default):
            If include_metadata=False: List of (trace_id, messages) tuples
            If include_metadata=True: List of (trace_id, trace_data_dict) tuples where
                trace_data_dict contains messages, metadata, and feedback
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
        >>> for trace_id, trace_data in traces:
        ...     print(f"Trace {trace_id}: {len(trace_data['messages'])} messages")
        ...     print(f"  Status: {trace_data['metadata']['status']}")
        ...     print(f"  Feedback: {len(trace_data['feedback'])} items")
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

    # Fetch messages (and metadata/feedback if requested) for each trace using concurrent fetching
    results, timing_info = _fetch_traces_concurrent(
        runs=runs,
        base_url=base_url,
        api_key=api_key,
        max_workers=max_workers,
        show_progress=show_progress,
        include_metadata=include_metadata,
        include_feedback=include_feedback,
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


# ============================================================================
# Metadata and Feedback Extraction Helpers
# ============================================================================


def _extract_run_metadata(run_data: dict) -> dict[str, Any]:
    """Extract metadata from a Run object (REST API response).

    Args:
        run_data: Run object dict from REST API response

    Returns:
        Dictionary with extracted metadata fields
    """
    from datetime import datetime

    extra = run_data.get("extra") or {}
    custom_metadata = extra.get("metadata") or {}

    # Calculate duration if we have both start and end times
    duration_ms = None
    start_time = run_data.get("start_time")
    end_time = run_data.get("end_time")
    if start_time and end_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
        except (ValueError, AttributeError):
            pass

    return {
        "status": run_data.get("status"),
        "start_time": start_time,
        "end_time": end_time,
        "duration_ms": duration_ms,
        "custom_metadata": custom_metadata,
        "token_usage": {
            "prompt_tokens": run_data.get("prompt_tokens"),
            "completion_tokens": run_data.get("completion_tokens"),
            "total_tokens": run_data.get("total_tokens"),
        },
        "costs": {
            "prompt_cost": run_data.get("prompt_cost"),
            "completion_cost": run_data.get("completion_cost"),
            "total_cost": run_data.get("total_cost"),
        },
        "first_token_time": run_data.get("first_token_time"),
        "feedback_stats": run_data.get("feedback_stats") or {},
    }


def _extract_run_metadata_from_sdk_run(run) -> dict[str, Any]:
    """Extract metadata from an SDK Run object.

    Args:
        run: Run object from langsmith SDK

    Returns:
        Dictionary with extracted metadata fields
    """
    # Calculate duration if we have both start and end times
    duration_ms = None
    if hasattr(run, "start_time") and hasattr(run, "end_time") and run.start_time and run.end_time:
        try:
            duration_ms = int((run.end_time - run.start_time).total_seconds() * 1000)
        except (AttributeError, TypeError):
            pass

    # Extract custom metadata from extra field
    custom_metadata = {}
    if hasattr(run, "extra") and run.extra:
        custom_metadata = run.extra.get("metadata") or {}

    return {
        "status": getattr(run, "status", None),
        "start_time": run.start_time.isoformat() if hasattr(run, "start_time") and run.start_time else None,
        "end_time": run.end_time.isoformat() if hasattr(run, "end_time") and run.end_time else None,
        "duration_ms": duration_ms,
        "custom_metadata": custom_metadata,
        "token_usage": {
            "prompt_tokens": getattr(run, "prompt_tokens", None),
            "completion_tokens": getattr(run, "completion_tokens", None),
            "total_tokens": getattr(run, "total_tokens", None),
        },
        "costs": {
            "prompt_cost": getattr(run, "prompt_cost", None),
            "completion_cost": getattr(run, "completion_cost", None),
            "total_cost": getattr(run, "total_cost", None),
        },
        "first_token_time": getattr(run, "first_token_time", None),
        "feedback_stats": getattr(run, "feedback_stats", None) or {},
    }


def _has_feedback(metadata: dict) -> bool:
    """Check if metadata indicates feedback exists.

    Args:
        metadata: Metadata dict with feedback_stats

    Returns:
        True if feedback_stats shows any feedback exists
    """
    feedback_stats = metadata.get("feedback_stats") or {}
    if not feedback_stats:
        return False

    # Check if any feedback count is positive
    return any(
        isinstance(v, (int, float)) and v > 0
        for v in feedback_stats.values()
    )


def _sdk_run_has_feedback(run) -> bool:
    """Check if SDK Run object has feedback.

    Args:
        run: SDK Run object

    Returns:
        True if feedback_stats shows any feedback exists
    """
    feedback_stats = getattr(run, "feedback_stats", None) or {}
    if not feedback_stats:
        return False

    return any(
        isinstance(v, (int, float)) and v > 0
        for v in feedback_stats.values()
    )


def _serialize_feedback(fb) -> dict[str, Any]:
    """Convert SDK Feedback object to dictionary.

    Args:
        fb: Feedback object from langsmith SDK

    Returns:
        Dictionary with feedback fields
    """
    return {
        "id": str(fb.id) if hasattr(fb, "id") else None,
        "key": getattr(fb, "key", None),
        "score": getattr(fb, "score", None),
        "value": getattr(fb, "value", None),
        "comment": getattr(fb, "comment", None),
        "correction": getattr(fb, "correction", None),
        "created_at": fb.created_at.isoformat() if hasattr(fb, "created_at") and fb.created_at else None,
    }


def _fetch_feedback(run_id: str, *, api_key: str) -> list[dict[str, Any]]:
    """Fetch full feedback objects for a single run.

    Args:
        run_id: Run UUID to fetch feedback for
        api_key: LangSmith API key

    Returns:
        List of feedback dictionaries
    """
    if not HAS_LANGSMITH:
        return []

    from langsmith import Client

    try:
        client = Client(api_key=api_key)
        feedback_list = list(client.list_feedback(run_id=run_id))
        return [_serialize_feedback(fb) for fb in feedback_list]
    except Exception as e:
        print(f"Warning: Failed to fetch feedback for run {run_id}: {e}", file=sys.stderr)
        return []


def _fetch_feedback_batch(
    run_ids: list[str],
    api_key: str,
    max_workers: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch feedback for multiple runs concurrently.

    Args:
        run_ids: List of run UUIDs to fetch feedback for
        api_key: LangSmith API key
        max_workers: Maximum concurrent requests (default: 5)

    Returns:
        Dictionary mapping run_id -> list of feedback dicts
    """
    if not HAS_LANGSMITH or not run_ids:
        return {}

    def fetch_single(run_id: str) -> tuple[str, list[dict[str, Any]]]:
        """Fetch feedback for a single run with error handling."""
        try:
            feedback = _fetch_feedback(run_id, api_key=api_key)
            return run_id, feedback
        except Exception:
            return run_id, []

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_single, rid) for rid in run_ids]
        for future in as_completed(futures):
            run_id, feedback = future.result()
            if feedback:
                results[run_id] = feedback

    return results


# ============================================================================
# New Fetchers with Metadata and Feedback Support
# ============================================================================


def fetch_trace_with_metadata(
    trace_id: str,
    *,
    base_url: str,
    api_key: str,
    include_feedback: bool = True,
) -> dict[str, Any]:
    """Fetch trace with metadata and optional feedback.

    Args:
        trace_id: LangSmith trace UUID
        base_url: LangSmith base URL
        api_key: LangSmith API key
        include_feedback: Whether to fetch full feedback objects (default: True)

    Returns:
        Dictionary with keys:
            - trace_id: Trace UUID
            - messages: List of message dictionaries
            - metadata: Metadata dict with status, timing, tokens, costs, etc.
            - feedback: List of feedback dicts (empty if no feedback or include_feedback=False)

    Raises:
        requests.HTTPError: If the API request fails
    """
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    url = f"{base_url}/runs/{trace_id}?include_messages=true"

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()

    # Extract messages
    messages = data.get("messages") or (data.get("outputs") or {}).get("messages") or []

    # Extract metadata from the full Run object
    metadata = _extract_run_metadata(data)

    # Fetch feedback if requested and feedback exists
    feedback = []
    if include_feedback and _has_feedback(metadata):
        feedback = _fetch_feedback(trace_id, api_key=api_key)

    return {
        "trace_id": trace_id,
        "messages": messages,
        "metadata": metadata,
        "feedback": feedback,
    }


def fetch_thread_with_metadata(
    thread_id: str,
    project_uuid: str,
    *,
    base_url: str,
    api_key: str,
    include_feedback: bool = True,
) -> dict[str, Any]:
    """Fetch thread with metadata from root run and optional feedback.

    Args:
        thread_id: LangGraph thread_id
        project_uuid: LangSmith project UUID
        base_url: LangSmith base URL
        api_key: LangSmith API key
        include_feedback: Whether to fetch full feedback objects (default: True)

    Returns:
        Dictionary with keys:
            - thread_id: Thread ID
            - messages: List of message dictionaries
            - metadata: Metadata from most recent root run (empty dict if no run found)
            - feedback: List of feedback dicts

    Raises:
        requests.HTTPError: If the API request fails
    """
    # Fetch messages using existing function
    messages = fetch_thread(thread_id, project_uuid, base_url=base_url, api_key=api_key)

    # Try to find the root run for this thread to get metadata
    metadata = {}
    feedback = []

    if HAS_LANGSMITH:
        try:
            from langsmith import Client

            client = Client(api_key=api_key)

            # Query for root runs with this thread_id (most recent first)
            runs = list(
                client.list_runs(
                    project_id=project_uuid,
                    filter=f'and(eq(is_root, true), eq(extra.metadata.thread_id, "{thread_id}"))',
                    limit=1,
                )
            )

            if runs:
                root_run = runs[0]
                metadata = _extract_run_metadata_from_sdk_run(root_run)

                # Fetch feedback if requested and feedback exists
                if include_feedback and _sdk_run_has_feedback(root_run):
                    feedback = _fetch_feedback(str(root_run.id), api_key=api_key)

        except Exception as e:
            print(
                f"Warning: Failed to fetch metadata for thread {thread_id}: {e}",
                file=sys.stderr,
            )

    return {
        "thread_id": thread_id,
        "messages": messages,
        "metadata": metadata,
        "feedback": feedback,
    }
