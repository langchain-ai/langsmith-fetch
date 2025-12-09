"""Core fetching logic for LangSmith threads and traces."""

import json
import requests
from typing import List, Dict, Any, Optional


def fetch_thread(
    thread_id: str, project_uuid: str, *, base_url: str, api_key: str
) -> List[Dict[str, Any]]:
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


def fetch_trace(trace_id: str, *, base_url: str, api_key: str) -> List[Dict[str, Any]]:
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


def fetch_latest_trace(
    api_key: str,
    base_url: str,
    project_uuid: Optional[str] = None,
    last_n_minutes: Optional[int] = None,
    since: Optional[str] = None
) -> List[Dict[str, Any]]:
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
    from langsmith import Client
    from datetime import datetime, timedelta, timezone

    # Initialize langsmith client
    client = Client(api_key=api_key)

    # Build filter parameters
    filter_params = {
        "is_root": True,
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
        start_time = datetime.fromisoformat(since.replace('Z', '+00:00'))
        filter_params["start_time"] = start_time

    # Fetch latest run
    runs = list(client.list_runs(**filter_params))

    if not runs:
        raise ValueError("No traces found matching criteria")

    latest_run = runs[0]
    trace_id = str(latest_run.id)

    # Reuse existing fetch_trace to get full messages
    return fetch_trace(trace_id, base_url=base_url, api_key=api_key)
