"""Core fetching logic for LangSmith threads and traces."""

import json
import requests
from typing import List, Dict, Any


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
