"""Output formatting utilities for messages."""

import json
from typing import Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


def format_messages(messages: list[dict[str, Any]], format_type: str) -> str:
    """
    Format messages according to the specified format.

    Args:
        messages: List of message dictionaries
        format_type: Output format ('raw', 'json', or 'pretty')

    Returns:
        Formatted string representation of messages
    """
    if format_type == "raw":
        return _format_raw(messages)
    elif format_type == "json":
        return _format_json(messages)
    elif format_type == "pretty":
        return _format_pretty(messages)
    else:
        raise ValueError(f"Unknown format type: {format_type}")


def _format_raw(messages: list[dict[str, Any]]) -> str:
    """Format as raw JSON (compact)."""
    return json.dumps(messages)


def _format_json(messages: list[dict[str, Any]]) -> str:
    """Format as pretty-printed JSON."""
    return json.dumps(messages, indent=2)


def _format_pretty(messages: list[dict[str, Any]]) -> str:
    """Format as human-readable structured text with Rich."""
    output_parts = []

    for i, msg in enumerate(messages, 1):
        msg_type = msg.get("type") or msg.get("role", "unknown")

        # Create header
        header = f"Message {i}: {msg_type}"
        output_parts.append("=" * 60)
        output_parts.append(header)
        output_parts.append("-" * 60)

        # Format content based on message type
        content = msg.get("content", "") or msg.get("kwargs", {}).get("content", "")

        if isinstance(content, str):
            output_parts.append(content)
        elif isinstance(content, list):
            # Handle structured content (tool calls, etc.)
            for item in content:
                if isinstance(item, dict):
                    if "text" in item:
                        output_parts.append(item["text"])
                    elif "type" in item and item["type"] == "tool_use":
                        output_parts.append(
                            f"\nTool Call: {item.get('name', 'unknown')}"
                        )
                        if "input" in item:
                            output_parts.append(
                                f"Input: {json.dumps(item['input'], indent=2)}"
                            )
                else:
                    output_parts.append(str(item))
        else:
            output_parts.append(str(content))

        # Handle tool calls (different format)
        if "tool_calls" in msg:
            for tool_call in msg["tool_calls"]:
                if isinstance(tool_call, dict):
                    func = tool_call.get("function", {})
                    output_parts.append(f"\nTool Call: {func.get('name', 'unknown')}")
                    if "arguments" in func:
                        output_parts.append(f"Arguments: {func['arguments']}")

        # Handle tool responses
        if msg_type == "tool" or msg.get("name"):
            tool_name = msg.get("name", "unknown")
            output_parts.append(f"Tool: {tool_name}")

        output_parts.append("")  # Empty line between messages

    return "\n".join(output_parts)


def print_formatted(
    messages: list[dict[str, Any]], format_type: str, output_file: str | None = None
):
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
        with open(output_file, "w") as f:
            f.write(content)
        return

    # Otherwise, print to console with Rich formatting
    if format_type == "json":
        # Use Rich's syntax highlighting for JSON
        json_str = _format_json(messages)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
        console.print(syntax)
    elif format_type == "pretty":
        # Use Rich formatting for pretty output
        for i, msg in enumerate(messages, 1):
            msg_type = msg.get("type") or msg.get("role", "unknown")
            title = f"Message {i}: {msg_type.upper()}"

            # Format content
            content = msg.get("content", "") or msg.get("kwargs", {}).get("content", "")
            if isinstance(content, str):
                panel_content = content
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if "text" in item:
                            parts.append(item["text"])
                        elif "type" in item and item["type"] == "tool_use":
                            parts.append(
                                f"[bold]Tool:[/bold] {item.get('name', 'unknown')}"
                            )
                    else:
                        parts.append(str(item))
                panel_content = "\n".join(parts)
            else:
                panel_content = str(content)

            # Handle tool calls
            if "tool_calls" in msg:
                tool_parts = []
                for tool_call in msg["tool_calls"]:
                    if isinstance(tool_call, dict):
                        func = tool_call.get("function", {})
                        tool_parts.append(
                            f"[bold]Tool:[/bold] {func.get('name', 'unknown')}"
                        )
                if tool_parts:
                    panel_content += "\n" + "\n".join(tool_parts)

            # Create panel
            panel = Panel(panel_content, title=title, border_style="blue")
            console.print(panel)
    else:
        # Raw format - just print
        console.print(_format_raw(messages))


# ============================================================================
# New Formatters for Trace Data with Metadata and Feedback
# ============================================================================


def format_trace_data(
    data: dict[str, Any] | list[dict[str, Any]], format_type: str
) -> str:
    """Format trace data with optional metadata and feedback.

    Args:
        data: Either a list of messages (old format) or dict with keys:
            {trace_id/thread_id, messages, metadata, feedback}
        format_type: Output format ('raw', 'json', or 'pretty')

    Returns:
        Formatted string representation
    """
    if isinstance(data, list):
        return format_messages(data, format_type)

    if format_type == "raw":
        return json.dumps(data, default=str)
    elif format_type == "json":
        return json.dumps(data, indent=2, default=str)
    elif format_type == "pretty":
        if data.get("metadata") or data.get("feedback"):
            return _format_pretty_with_metadata(data)
        elif data.get("run_type") or data.get("name"):
            return _format_pretty_run(data)
        else:
            return json.dumps(data, indent=2, default=str)
    else:
        raise ValueError(f"Unknown format type: {format_type}")


def _format_pretty_with_metadata(data: dict[str, Any]) -> str:
    """Format trace data with metadata as human-readable output."""
    parts = []

    metadata = data.get("metadata", {})
    if metadata:
        parts.append(_format_metadata_section(metadata))

    feedback = data.get("feedback", [])
    if feedback:
        parts.append(_format_feedback_section(feedback))

    if parts:
        parts.append("=" * 60)
        parts.append("MESSAGES")
        parts.append("=" * 60)

    messages = data.get("messages", [])
    if messages:
        parts.append(_format_pretty(messages))
    else:
        if data.get("inputs"):
            parts.append("Inputs:")
            parts.append(json.dumps(data["inputs"], indent=2, default=str))
        if data.get("outputs"):
            parts.append("Outputs:")
            parts.append(json.dumps(data["outputs"], indent=2, default=str))

    return "\n\n".join(parts)


def _format_pretty_run(data: dict[str, Any]) -> str:
    """Format run data as human-readable output."""
    lines = []

    if data.get("name"):
        lines.append(f"Name: {data['name']}")
    if data.get("run_type"):
        lines.append(f"Type: {data['run_type']}")
    if data.get("status"):
        lines.append(f"Status: {data['status']}")

    if data.get("start_time"):
        lines.append(f"Start: {data['start_time']}")
    if data.get("end_time"):
        lines.append(f"End: {data['end_time']}")

    if data.get("total_tokens"):
        lines.append(
            f"Tokens: {data['total_tokens']} (prompt: {data.get('prompt_tokens')}, completion: {data.get('completion_tokens')})"
        )
    if data.get("total_cost"):
        lines.append(f"Cost: ${data['total_cost']:.6f}")

    if data.get("inputs"):
        lines.append("\nInputs:")
        lines.append(json.dumps(data["inputs"], indent=2, default=str))

    if data.get("outputs"):
        lines.append("\nOutputs:")
        lines.append(json.dumps(data["outputs"], indent=2, default=str))

    if data.get("messages"):
        lines.append("\nMessages:")
        lines.append(_format_pretty(data["messages"]))

    if data.get("child_runs"):
        lines.append(f"\nChild Runs: {len(data['child_runs'])}")

    return "\n".join(lines)


def _format_metadata_section(metadata: dict[str, Any]) -> str:
    """Format metadata section for pretty output."""
    lines = ["=" * 60, "RUN METADATA", "=" * 60]

    # Status and timing
    if metadata.get("status"):
        lines.append(f"Status: {metadata['status']}")
    if metadata.get("start_time"):
        lines.append(f"Start Time: {metadata['start_time']}")
    if metadata.get("end_time"):
        lines.append(f"End Time: {metadata['end_time']}")
    if metadata.get("duration_ms"):
        lines.append(f"Duration: {metadata['duration_ms']}ms")

    # Token usage
    token_usage = metadata.get("token_usage", {})
    if any(v is not None for v in token_usage.values()):
        lines.append("\nToken Usage:")
        if token_usage.get("prompt_tokens") is not None:
            lines.append(f"  Prompt: {token_usage['prompt_tokens']}")
        if token_usage.get("completion_tokens") is not None:
            lines.append(f"  Completion: {token_usage['completion_tokens']}")
        if token_usage.get("total_tokens") is not None:
            lines.append(f"  Total: {token_usage['total_tokens']}")

    # Costs
    costs = metadata.get("costs", {})
    if any(v is not None for v in costs.values()):
        lines.append("\nCosts:")
        if costs.get("total_cost") is not None:
            lines.append(f"  Total: ${costs['total_cost']:.5f}")
        if costs.get("prompt_cost") is not None:
            lines.append(f"  Prompt: ${costs['prompt_cost']:.5f}")
        if costs.get("completion_cost") is not None:
            lines.append(f"  Completion: ${costs['completion_cost']:.5f}")

    # Custom metadata
    custom = metadata.get("custom_metadata", {})
    if custom:
        lines.append("\nCustom Metadata:")
        for key, value in custom.items():
            # Pretty print the value
            if isinstance(value, dict):
                lines.append(f"  {key}: {json.dumps(value, indent=4)}")
            else:
                lines.append(f"  {key}: {value}")

    # Feedback stats
    feedback_stats = metadata.get("feedback_stats", {})
    if feedback_stats:
        lines.append("\nFeedback Stats:")
        for key, count in feedback_stats.items():
            lines.append(f"  {key}: {count}")

    return "\n".join(lines)


def _format_feedback_section(feedback: list[dict[str, Any]]) -> str:
    """Format feedback section for pretty output."""
    lines = ["=" * 60, "FEEDBACK", "=" * 60]

    for i, fb in enumerate(feedback, 1):
        lines.append(f"\nFeedback {i}:")
        lines.append(f"  Key: {fb['key']}")
        if fb.get("score") is not None:
            lines.append(f"  Score: {fb['score']}")
        if fb.get("value") is not None:
            lines.append(f"  Value: {fb['value']}")
        if fb.get("comment"):
            lines.append(f"  Comment: {fb['comment']}")
        if fb.get("correction"):
            correction = fb["correction"]
            if isinstance(correction, str):
                lines.append(f"  Correction: {correction}")
            else:
                lines.append(f"  Correction: {json.dumps(correction, indent=4)}")
        if fb.get("created_at"):
            lines.append(f"  Created: {fb['created_at']}")

    return "\n".join(lines)


def print_formatted_trace(
    data: dict[str, Any] | list[dict[str, Any]],
    format_type: str,
    output_file: str | None = None,
):
    """Print formatted trace data with metadata and feedback.

    Args:
        data: Either list of messages (old format) or dict with trace data
        format_type: Output format ('raw', 'json', or 'pretty')
        output_file: Optional file path to save output instead of printing
    """
    # If output_file is specified, save to file
    if output_file:
        content = format_trace_data(data, format_type)
        with open(output_file, "w") as f:
            f.write(content)
        return

    # Otherwise, print to console
    if format_type == "json":
        # Use Rich's syntax highlighting for JSON
        json_str = format_trace_data(data, "json")
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
        console.print(syntax)
    elif format_type == "pretty":
        # For messages-only (list), use Rich panels
        if isinstance(data, list):
            print_formatted(data, format_type, None)
        # For trace data with metadata (dict), use plain text format
        else:
            formatted = format_trace_data(data, "pretty")
            console.print(formatted)
    else:
        # Raw format
        console.print(format_trace_data(data, "raw"))


def print_formatted_run(
    data: dict[str, Any],
    format_type: str,
    output_file: str | None = None,
    include_metadata: bool = False,
):
    """Print formatted run data with nested child runs.

    Args:
        data: Run data dictionary with optional child_runs
        format_type: Output format ('raw', 'json', or 'pretty')
        output_file: Optional file path to save output instead of printing
        include_metadata: Whether to include tokens and costs
    """
    if output_file:
        content = json.dumps(data, indent=2, default=str)
        with open(output_file, "w") as f:
            f.write(content)
        return

    if format_type == "json":
        json_str = json.dumps(data, indent=2, default=str)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
        console.print(syntax)
    elif format_type == "raw":
        console.print(json.dumps(data, default=str))
    else:
        _print_run_panel(data, include_metadata=include_metadata)


def _extract_messages(data: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Extract messages from run data, checking various locations."""
    messages = []

    if data.get("messages"):
        messages.extend(_normalize_messages(data["messages"]))

    inputs = data.get("inputs", {})
    if isinstance(inputs, dict) and inputs.get("messages"):
        msgs = inputs["messages"]
        if isinstance(msgs, list) and len(msgs) > 0:
            if isinstance(msgs[0], list):
                messages.extend(_normalize_messages(msgs[0]))
            else:
                messages.extend(_normalize_messages(msgs))

    outputs = data.get("outputs", {})
    if isinstance(outputs, dict):
        if outputs.get("messages"):
            msgs = outputs["messages"]
            if isinstance(msgs, list) and len(msgs) > 0:
                if isinstance(msgs[0], list):
                    messages.extend(_normalize_messages(msgs[0]))
                else:
                    messages.extend(_normalize_messages(msgs))
        if outputs.get("generations"):
            gens = outputs["generations"]
            if isinstance(gens, list) and len(gens) > 0:
                first_gen = gens[0]
                if isinstance(first_gen, list) and len(first_gen) > 0:
                    msg = first_gen[0].get("message", {})
                    kwargs = msg.get("kwargs", {})
                    if kwargs.get("content"):
                        content = kwargs["content"]
                        if isinstance(content, str):
                            messages.append({"role": "assistant", "content": content})
                        elif isinstance(content, list):
                            text_parts = []
                            for item in content:
                                if (
                                    isinstance(item, dict)
                                    and item.get("type") == "text"
                                ):
                                    text_parts.append(item.get("text", ""))
                            if text_parts:
                                messages.append(
                                    {
                                        "role": "assistant",
                                        "content": "\n".join(text_parts),
                                    }
                                )

    return messages if messages else None


def _normalize_messages(msgs: list) -> list[dict[str, Any]]:
    """Normalize messages from various formats to standard {role, content} format."""
    normalized = []
    for msg in msgs:
        if isinstance(msg, dict):
            if msg.get("role") and msg.get("content"):
                normalized.append(msg)
            elif msg.get("kwargs"):
                kwargs = msg.get("kwargs", {})
                msg_id = msg.get("id", [])
                msg_type = "unknown"
                if "SystemMessage" in msg_id:
                    msg_type = "system"
                elif "HumanMessage" in msg_id:
                    msg_type = "user"
                elif "AIMessage" in msg_id:
                    msg_type = "assistant"
                elif "ToolMessage" in msg_id:
                    msg_type = "tool"

                content = kwargs.get("content", "")
                normalized.append({"role": msg_type, "content": content})
            else:
                normalized.append(msg)
    return normalized


def _build_run_panel(data: dict[str, Any], include_metadata: bool = False) -> Panel:
    """Build a Rich panel for a run with optional nested child runs."""
    name = data.get("name", "Unnamed")
    run_type = data.get("run_type", "unknown")
    status = data.get("status", "unknown")
    child_runs = [
        c for c in data.get("child_runs", []) if c.get("name") != "RunnableLambda"
    ]

    title = f"{name} [dim]({run_type})[/dim]"

    renderables: list[Any] = []

    if include_metadata:
        if data.get("total_tokens"):
            renderables.append(
                f"[bold]Tokens:[/bold] {data['total_tokens']} (prompt: {data.get('prompt_tokens', 0)}, completion: {data.get('completion_tokens', 0)})"
            )
        if data.get("total_cost"):
            renderables.append(f"[bold]Cost:[/bold] ${data['total_cost']:.6f}")

    messages = _extract_messages(data)
    if messages:
        renderables.append("")
        for msg in messages:
            renderables.append(_format_message_panel(msg))

    if data.get("error"):
        renderables.append(f"\n[bold red]Error:[/bold red] {data['error']}")

    for child in child_runs:
        renderables.append(_build_run_panel(child, include_metadata=include_metadata))

    border_style = (
        "green" if status == "success" else "red" if status == "error" else "blue"
    )
    return Panel(
        Group(*renderables) if renderables else "",
        title=title,
        border_style=border_style,
        expand=False,
    )


def _print_run_panel(data: dict[str, Any], include_metadata: bool = False):
    """Print a run as a Rich panel."""
    console.print(_build_run_panel(data, include_metadata=include_metadata))


def _format_message_panel(msg: dict[str, Any]) -> Panel:
    """Format a message as a blue panel."""
    role = msg.get("role", "unknown")
    content = msg.get("content", "") or msg.get("kwargs", {}).get("content", "")

    lines = []
    if isinstance(content, str) and content.strip():
        lines.append(content)
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    text = item["text"]
                    lines.append(text)

    return Panel(
        "\n".join(lines) if lines else "",
        title=f"[bold]{role}[/bold]",
        border_style="blue",
        expand=False,
    )
