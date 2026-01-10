"""Tree building utilities for trace hierarchies."""

from datetime import datetime
from typing import Any


def build_tree_from_runs(runs: list[dict]) -> dict[str, Any] | None:
    """
    Reconstruct hierarchical tree from flat list of runs.

    Args:
        runs: Flat list of run dictionaries, each containing 'id' and 'parent_run_id'

    Returns:
        Root node with nested 'children' arrays, or None if no runs provided.
        Each node has:
        {
            "id": str,
            "name": str,
            "run_type": str,
            "status": str,
            "error": str | None,
            "tokens": int | None,
            "prompt_tokens": int | None,
            "completion_tokens": int | None,
            "cost": float | None,
            "duration_ms": int | None,
            "model": str | None,
            "children": list[dict]
        }

    Note:
        - Children are sorted by dotted_order (execution order)
        - Each node includes only essential fields for tree display
    """
    if not runs:
        return None

    # Create lookup dict with extracted summary and empty children
    by_id: dict[str, dict] = {}
    for run in runs:
        summary = extract_run_summary(run)
        summary["children"] = []
        by_id[run["id"]] = summary

    # Build tree by linking children to parents
    root = None
    for run in runs:
        run_id = run["id"]
        parent_id = run.get("parent_run_id")

        if parent_id is None:
            root = by_id[run_id]
        elif parent_id in by_id:
            by_id[parent_id]["children"].append(by_id[run_id])

    # Sort children by dotted_order at each level
    def sort_children(node: dict) -> None:
        node["children"].sort(key=lambda x: x.get("dotted_order", "") or "")
        for child in node["children"]:
            sort_children(child)

    if root:
        sort_children(root)

    return root


def extract_run_summary(run: dict) -> dict[str, Any]:
    """
    Extract essential fields from a run for tree display.

    Args:
        run: Full run dictionary from API

    Returns:
        {
            "id": str,
            "name": str,
            "run_type": str,
            "status": str,
            "error": str | None,
            "tokens": int | None,
            "prompt_tokens": int | None,
            "completion_tokens": int | None,
            "cost": float | None,
            "prompt_cost": float | None,
            "completion_cost": float | None,
            "duration_ms": int | None,
            "model": str | None,
            "dotted_order": str | None,
            "start_time": str | None,
            "end_time": str | None,
            "first_token_time": str | None,
            "has_children": bool,
            "child_count": int
        }
    """
    # Calculate duration from timestamps
    duration_ms = None
    start_time = run.get("start_time")
    end_time = run.get("end_time")
    if start_time and end_time:
        try:
            # Handle both datetime objects and strings
            if isinstance(start_time, str):
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            else:
                start_dt = start_time
            if isinstance(end_time, str):
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            else:
                end_dt = end_time
            duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
        except (ValueError, AttributeError, TypeError):
            pass

    # Extract model name from various locations
    model = extract_model_name(run)

    # Get child info
    child_run_ids = run.get("child_run_ids") or []

    return {
        "id": run.get("id"),
        "name": run.get("name"),
        "run_type": run.get("run_type"),
        "status": run.get("status"),
        "error": run.get("error"),
        "tokens": run.get("total_tokens"),
        "prompt_tokens": run.get("prompt_tokens"),
        "completion_tokens": run.get("completion_tokens"),
        "cost": run.get("total_cost"),
        "prompt_cost": run.get("prompt_cost"),
        "completion_cost": run.get("completion_cost"),
        "duration_ms": duration_ms,
        "model": model,
        "dotted_order": run.get("dotted_order"),
        "start_time": start_time if isinstance(start_time, str) else (
            start_time.isoformat() if start_time else None
        ),
        "end_time": end_time if isinstance(end_time, str) else (
            end_time.isoformat() if end_time else None
        ),
        "first_token_time": run.get("first_token_time"),
        "has_children": len(child_run_ids) > 0,
        "child_count": len(child_run_ids),
    }


def extract_model_name(run: dict) -> str | None:
    """
    Extract model name from run data.

    Checks multiple locations in order of preference:
    1. extra.metadata.ls_model_name
    2. extra.runtime.model
    3. extra.invocation_params.model
    4. extra.invocation_params.model_name

    Args:
        run: Run dictionary from API

    Returns:
        Model name string or None if not found
    """
    extra = run.get("extra") or {}

    # Check metadata first
    metadata = extra.get("metadata") or {}
    if model := metadata.get("ls_model_name"):
        return model

    # Check runtime
    runtime = extra.get("runtime") or {}
    if model := runtime.get("model"):
        return model

    # Check invocation_params
    invocation_params = extra.get("invocation_params") or {}
    if model := invocation_params.get("model"):
        return model
    if model := invocation_params.get("model_name"):
        return model

    return None


def calculate_tree_summary(runs: list[dict]) -> dict[str, Any]:
    """
    Calculate summary statistics for a trace.

    Args:
        runs: List of run dictionaries

    Returns:
        {
            "total_runs": int,
            "total_tokens": int,
            "prompt_tokens": int,
            "completion_tokens": int,
            "total_cost": float,
            "total_duration_ms": int | None,
            "run_types": dict[str, int],
            "models_used": list[str],
            "has_errors": bool,
            "error_count": int,
            "error_runs": list[dict]  # [{id, name, error}]
        }
    """
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    total_cost = 0.0
    run_types: dict[str, int] = {}
    models_used: set[str] = set()
    error_count = 0
    error_runs: list[dict] = []
    root_duration_ms = None

    for run in runs:
        # Token counts
        if run.get("total_tokens"):
            total_tokens += run["total_tokens"]
        if run.get("prompt_tokens"):
            prompt_tokens += run["prompt_tokens"]
        if run.get("completion_tokens"):
            completion_tokens += run["completion_tokens"]

        # Costs
        if run.get("total_cost"):
            total_cost += run["total_cost"]

        # Run types
        run_type = run.get("run_type", "unknown")
        run_types[run_type] = run_types.get(run_type, 0) + 1

        # Models
        model = extract_model_name(run)
        if model:
            models_used.add(model)

        # Errors
        if run.get("error") or run.get("status") == "error":
            error_count += 1
            error_runs.append({
                "id": run.get("id"),
                "name": run.get("name"),
                "error": run.get("error"),
            })

        # Root run duration (for total duration)
        if run.get("parent_run_id") is None:
            start_time = run.get("start_time")
            end_time = run.get("end_time")
            if start_time and end_time:
                try:
                    if isinstance(start_time, str):
                        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    else:
                        start_dt = start_time
                    if isinstance(end_time, str):
                        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    else:
                        end_dt = end_time
                    root_duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
                except (ValueError, AttributeError, TypeError):
                    pass

    return {
        "total_runs": len(runs),
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_cost": total_cost,
        "total_duration_ms": root_duration_ms,
        "run_types": run_types,
        "models_used": sorted(models_used),
        "has_errors": error_count > 0,
        "error_count": error_count,
        "error_runs": error_runs,
    }


def generate_navigation_md(
    trace_id: str,
    tree: dict | None,
    summary: dict,
    output_dir: str,
    fetched_at: str,
) -> str:
    """
    Generate NAVIGATION.md content for exploring a trace.

    Args:
        trace_id: The trace UUID
        tree: The tree structure (root node)
        summary: Summary statistics
        output_dir: Output directory path
        fetched_at: Timestamp when trace was fetched

    Returns:
        Markdown string content for NAVIGATION.md
    """
    lines = [
        "# Trace Navigation Guide",
        "",
        f"## Trace: {trace_id}",
        f"Fetched: {fetched_at}",
        "",
        "## Summary",
        f"- Total runs: {summary['total_runs']}",
        f"- Total tokens: {summary['total_tokens']:,}",
        f"- Total cost: ${summary['total_cost']:.5f}",
    ]

    if summary["total_duration_ms"]:
        duration_s = summary["total_duration_ms"] / 1000
        lines.append(f"- Duration: {duration_s:.2f}s")

    if summary["models_used"]:
        models_str = ", ".join(summary["models_used"])
        lines.append(f"- Models: {models_str}")

    if summary["has_errors"]:
        lines.append(f"- Errors: {summary['error_count']}")

    lines.extend([
        "",
        "## Run Types",
    ])
    for run_type, count in sorted(summary["run_types"].items()):
        lines.append(f"- {run_type}: {count}")

    lines.extend([
        "",
        "## Tree Structure",
        "```",
    ])

    # Generate ASCII tree
    if tree:
        lines.extend(_generate_ascii_tree(tree))
    else:
        lines.append("(no tree data)")

    lines.extend([
        "```",
        "",
        "## How to Explore",
        "",
        "### View full data for a specific run:",
        "```",
        f"langsmith-fetch run <run-id> --output-dir {output_dir}",
        "```",
        "",
    ])

    # Key runs section
    if summary["error_runs"]:
        lines.extend([
            "### Runs with errors:",
        ])
        for err_run in summary["error_runs"][:5]:  # Limit to 5
            lines.append(f"- `{err_run['id']}` ({err_run['name']})")
        lines.append("")

    # Add notable runs by token usage
    if tree:
        high_token_runs = _find_high_token_runs(tree, limit=5)
        if high_token_runs:
            lines.extend([
                "### High token usage runs:",
            ])
            for run in high_token_runs:
                tokens = run.get("tokens") or 0
                lines.append(f"- `{run['id']}` ({run['name']}): {tokens:,} tokens")
            lines.append("")

    lines.extend([
        "## Files",
        "- `tree.json` - Full tree structure with all run metadata",
        "- `summary.json` - Quick statistics",
        "- `runs/` - Directory for fetched run data (initially empty)",
    ])

    return "\n".join(lines)


def _generate_ascii_tree(node: dict, prefix: str = "", is_last: bool = True) -> list[str]:
    """Generate ASCII tree representation of a node and its children."""
    lines = []

    # Node representation
    connector = "└── " if is_last else "├── "
    name = node.get("name", "unknown")
    run_type = node.get("run_type", "")
    status = node.get("status", "")

    # Build info string
    info_parts = [f"[{run_type}]"]
    if node.get("tokens"):
        info_parts.append(f"{node['tokens']:,} tokens")
    if node.get("model"):
        info_parts.append(node["model"])
    if status == "error":
        info_parts.append("ERROR")

    info_str = " ".join(info_parts)
    lines.append(f"{prefix}{connector}{name} {info_str}")

    # Process children
    children = node.get("children", [])
    child_prefix = prefix + ("    " if is_last else "│   ")

    for i, child in enumerate(children):
        is_last_child = i == len(children) - 1
        lines.extend(_generate_ascii_tree(child, child_prefix, is_last_child))

    return lines


def _find_high_token_runs(node: dict, limit: int = 5) -> list[dict]:
    """Find runs with highest token usage in tree."""
    runs = []

    def collect_runs(n: dict) -> None:
        if n.get("tokens"):
            runs.append({
                "id": n["id"],
                "name": n["name"],
                "tokens": n["tokens"],
            })
        for child in n.get("children", []):
            collect_runs(child)

    collect_runs(node)

    # Sort by tokens descending and return top N
    runs.sort(key=lambda x: x["tokens"], reverse=True)
    return runs[:limit]


def format_tree_pretty(
    tree: dict | None,
    summary: dict,
    show_ids: bool = False,
    max_depth: int | None = None,
) -> str:
    """
    Format tree for pretty terminal output.

    Args:
        tree: Tree structure (root node)
        summary: Summary statistics
        show_ids: Whether to show run IDs
        max_depth: Maximum tree depth to show

    Returns:
        Formatted string for terminal output
    """
    lines = []

    # Summary section
    lines.append("=" * 60)
    lines.append("TRACE SUMMARY")
    lines.append("=" * 60)
    lines.append(f"Total runs: {summary['total_runs']}")
    lines.append(f"Total tokens: {summary['total_tokens']:,}")
    lines.append(f"Total cost: ${summary['total_cost']:.5f}")

    if summary["total_duration_ms"]:
        duration_s = summary["total_duration_ms"] / 1000
        lines.append(f"Duration: {duration_s:.2f}s")

    if summary["models_used"]:
        lines.append(f"Models: {', '.join(summary['models_used'])}")

    if summary["has_errors"]:
        lines.append(f"Errors: {summary['error_count']}")

    # Run types
    lines.append("\nRun types:")
    for run_type, count in sorted(summary["run_types"].items()):
        lines.append(f"  {run_type}: {count}")

    # Tree section
    lines.append("")
    lines.append("=" * 60)
    lines.append("EXECUTION TREE")
    lines.append("=" * 60)

    if tree:
        tree_lines = _format_tree_node(tree, show_ids=show_ids, max_depth=max_depth)
        lines.extend(tree_lines)
    else:
        lines.append("(no tree data)")

    return "\n".join(lines)


def _format_tree_node(
    node: dict,
    prefix: str = "",
    is_last: bool = True,
    show_ids: bool = False,
    max_depth: int | None = None,
    current_depth: int = 0,
) -> list[str]:
    """Format a single tree node and its children."""
    lines = []

    # Check depth limit
    if max_depth is not None and current_depth > max_depth:
        return lines

    connector = "└── " if is_last else "├── "
    name = node.get("name", "unknown")
    run_type = node.get("run_type", "")

    # Build display line
    parts = [f"{prefix}{connector}{name}"]
    parts.append(f"[{run_type}]")

    if node.get("tokens"):
        parts.append(f"{node['tokens']:,} tok")
    if node.get("duration_ms"):
        parts.append(f"{node['duration_ms']}ms")
    if node.get("model"):
        parts.append(f"({node['model']})")
    if node.get("status") == "error":
        parts.append("[ERROR]")

    if show_ids:
        parts.append(f"id:{node['id']}")

    lines.append(" ".join(parts))

    # Process children
    children = node.get("children", [])
    child_prefix = prefix + ("    " if is_last else "│   ")

    # Check if we should truncate children
    if max_depth is not None and current_depth >= max_depth and children:
        lines.append(f"{child_prefix}... ({len(children)} children)")
    else:
        for i, child in enumerate(children):
            is_last_child = i == len(children) - 1
            lines.extend(_format_tree_node(
                child,
                child_prefix,
                is_last_child,
                show_ids=show_ids,
                max_depth=max_depth,
                current_depth=current_depth + 1,
            ))

    return lines
