"""Core fetching logic for LangSmith threads and traces."""

import json
import requests
from typing import List, Dict, Any, Optional, Tuple
from collections import OrderedDict


BASE_URL = "https://api.smith.langchain.com"


def fetch_thread(thread_id: str, project_uuid: str, api_key: str) -> List[Dict[str, Any]]:
    """
    Fetch messages for a LangGraph thread by thread_id.

    Args:
        thread_id: LangGraph thread_id (e.g., 'test-email-agent-thread')
        project_uuid: LangSmith project UUID (session_id)
        api_key: LangSmith API key

    Returns:
        List of message dictionaries

    Raises:
        requests.HTTPError: If the API request fails
    """
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    url = f"{BASE_URL}/runs/threads/{thread_id}"
    params = {
        "select": "all_messages",
        "session_id": project_uuid
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    data = response.json()
    messages_text = data['previews']['all_messages']

    # Parse the JSON messages (newline-separated JSON objects)
    messages = []
    for line in messages_text.strip().split('\n\n'):
        if line.strip():
            messages.append(json.loads(line))

    return messages


def fetch_trace(trace_id: str, api_key: str) -> List[Dict[str, Any]]:
    """
    Fetch messages for a single trace by trace ID.

    Args:
        trace_id: LangSmith trace UUID
        api_key: LangSmith API key

    Returns:
        List of message dictionaries with structured content

    Raises:
        requests.HTTPError: If the API request fails
    """
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    url = f"{BASE_URL}/runs/{trace_id}"

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()

    # Extract messages from outputs
    outputs = data.get('outputs', {})
    messages = outputs.get('messages', [])

    return messages


def fetch_recent_threads(
    project_uuid: str, 
    api_key: str, 
    limit: int = 10
) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """
    Fetch recent threads for a project.

    Args:
        project_uuid: LangSmith project UUID (session_id)
        api_key: LangSmith API key
        limit: Maximum number of threads to return (default: 10)

    Returns:
        List of tuples (thread_id, messages) for each thread

    Raises:
        requests.HTTPError: If the API request fails
    """
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    # Query for root runs in the project, sorted by start time descending
    url = f"{BASE_URL}/runs/query"
    body = {
        "session": [project_uuid],
        "is_root": True,
        "select": ["id", "extra", "start_time"],
        "limit": 1000,  # Fetch more runs to find unique threads
    }

    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()

    data = response.json()
    runs = data.get('runs', [])

    # Extract unique thread_ids with their most recent timestamp
    thread_info = OrderedDict()  # Maintains insertion order (most recent first)
    
    for run in runs:
        # Check if run has thread_id in metadata
        extra = run.get('extra', {})
        metadata = extra.get('metadata', {})
        thread_id = metadata.get('thread_id')
        
        if thread_id and thread_id not in thread_info:
            thread_info[thread_id] = run.get('start_time')
            
            # Stop if we've found enough unique threads
            if len(thread_info) >= limit:
                break

    # Fetch messages for each thread
    results = []
    for thread_id in thread_info.keys():
        try:
            messages = fetch_thread(thread_id, project_uuid, api_key)
            results.append((thread_id, messages))
        except Exception as e:
            # Log error but continue with other threads
            print(f"Warning: Failed to fetch thread {thread_id}: {e}")
            continue

    return results
