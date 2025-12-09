"""Output formatting utilities for messages."""

import json
from typing import List, Dict, Any
from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel
from rich.table import Table


console = Console()


def format_messages(messages: List[Dict[str, Any]], format_type: str) -> str:
    """
    Format messages according to the specified format.

    Args:
        messages: List of message dictionaries
        format_type: Output format ('raw', 'json', or 'pretty')

    Returns:
        Formatted string representation of messages
    """
    if format_type == 'raw':
        return _format_raw(messages)
    elif format_type == 'json':
        return _format_json(messages)
    elif format_type == 'pretty':
        return _format_pretty(messages)
    else:
        raise ValueError(f"Unknown format type: {format_type}")


def _format_raw(messages: List[Dict[str, Any]]) -> str:
    """Format as raw JSON (compact)."""
    return json.dumps(messages)


def _format_json(messages: List[Dict[str, Any]]) -> str:
    """Format as pretty-printed JSON."""
    return json.dumps(messages, indent=2)


def _format_pretty(messages: List[Dict[str, Any]]) -> str:
    """Format as human-readable structured text with Rich."""
    output_parts = []

    for i, msg in enumerate(messages, 1):
        msg_type = msg.get('type') or msg.get('role', 'unknown')

        # Create header
        header = f"Message {i}: {msg_type}"
        output_parts.append("=" * 60)
        output_parts.append(header)
        output_parts.append("-" * 60)

        # Format content based on message type
        content = msg.get('content', '')

        if isinstance(content, str):
            output_parts.append(content)
        elif isinstance(content, list):
            # Handle structured content (tool calls, etc.)
            for item in content:
                if isinstance(item, dict):
                    if 'text' in item:
                        output_parts.append(item['text'])
                    elif 'type' in item and item['type'] == 'tool_use':
                        output_parts.append(f"\nTool Call: {item.get('name', 'unknown')}")
                        if 'input' in item:
                            output_parts.append(f"Input: {json.dumps(item['input'], indent=2)}")
                else:
                    output_parts.append(str(item))
        else:
            output_parts.append(str(content))

        # Handle tool calls (different format)
        if 'tool_calls' in msg:
            for tool_call in msg['tool_calls']:
                if isinstance(tool_call, dict):
                    func = tool_call.get('function', {})
                    output_parts.append(f"\nTool Call: {func.get('name', 'unknown')}")
                    if 'arguments' in func:
                        output_parts.append(f"Arguments: {func['arguments']}")

        # Handle tool responses
        if msg_type == 'tool' or msg.get('name'):
            tool_name = msg.get('name', 'unknown')
            output_parts.append(f"Tool: {tool_name}")

        output_parts.append("")  # Empty line between messages

    return "\n".join(output_parts)


def print_formatted(messages: List[Dict[str, Any]], format_type: str, output_file: str = None):
    """
    Print formatted messages directly to console with Rich formatting, or save to file.

    Args:
        messages: List of message dictionaries
        format_type: Output format ('raw', 'json', or 'pretty')
        output_file: Optional file path to save output instead of printing
    """
    # If output_file is specified, save to file
    if output_file:
        content = format_messages(messages, format_type)
        with open(output_file, 'w') as f:
            f.write(content)
        return
    
    # Otherwise, print to console with Rich formatting
    if format_type == 'json':
        # Use Rich's syntax highlighting for JSON
        json_str = _format_json(messages)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
        console.print(syntax)
    elif format_type == 'pretty':
        # Use Rich formatting for pretty output
        for i, msg in enumerate(messages, 1):
            msg_type = msg.get('type') or msg.get('role', 'unknown')
            title = f"Message {i}: {msg_type.upper()}"

            # Format content
            content = msg.get('content', '')
            if isinstance(content, str):
                panel_content = content
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if 'text' in item:
                            parts.append(item['text'])
                        elif 'type' in item and item['type'] == 'tool_use':
                            parts.append(f"[bold]Tool:[/bold] {item.get('name', 'unknown')}")
                    else:
                        parts.append(str(item))
                panel_content = "\n".join(parts)
            else:
                panel_content = str(content)

            # Handle tool calls
            if 'tool_calls' in msg:
                tool_parts = []
                for tool_call in msg['tool_calls']:
                    if isinstance(tool_call, dict):
                        func = tool_call.get('function', {})
                        tool_parts.append(f"[bold]Tool:[/bold] {func.get('name', 'unknown')}")
                if tool_parts:
                    panel_content += "\n" + "\n".join(tool_parts)

            # Create panel
            panel = Panel(panel_content, title=title, border_style="blue")
            console.print(panel)
    else:
        # Raw format - just print
        console.print(_format_raw(messages))
