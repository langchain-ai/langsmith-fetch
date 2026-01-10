"""Main CLI interface using Click."""

import json
import os
import re
import sys
from pathlib import Path

import click
import requests

from . import config, fetchers, formatters


def sanitize_filename(filename: str) -> str:
    """Sanitize a string to be used as a safe filename.

    Removes or replaces characters that are not safe for filenames across platforms.

    Args:
        filename: The original filename string

    Returns:
        A sanitized filename safe for all platforms
    """
    # Remove or replace unsafe characters
    # Keep alphanumeric, hyphens, underscores, and dots
    safe_name = re.sub(r"[^\w\-.]", "_", filename)
    # Remove leading/trailing dots and spaces
    safe_name = safe_name.strip(". ")
    # Limit length to 255 characters (filesystem limit)
    if len(safe_name) > 255:
        safe_name = safe_name[:255]
    return safe_name


@click.group()
def main():
    """LangSmith Fetch - Fetch and display LangSmith threads and traces.

    This CLI tool retrieves conversation messages, traces, and threads from LangSmith.

    REQUIREMENTS:
      - LANGSMITH_API_KEY environment variable or stored in config
      - Project UUID (required for threads, optional for traces)

    COMMON COMMANDS:
      langsmith-fetch trace <trace-id>                    # Fetch a specific trace by ID
      langsmith-fetch thread <thread-id>                  # Fetch a specific thread by ID
      langsmith-fetch traces ./dir --limit 10             # Fetch 10 traces to directory (RECOMMENDED)
      langsmith-fetch threads ./dir --limit 10            # Fetch 10 threads to directory (RECOMMENDED)

    CONFIGURATION:
      langsmith-fetch config show                         # View current configuration
      langsmith-fetch config set project-uuid <uuid>      # Configure project UUID
      langsmith-fetch config set api-key <key>            # Store API key in config

    NOTE: When using 'traces' or 'threads' commands, ALWAYS specify an output directory
    unless you explicitly want to print to stdout. Use directory mode for typical usage.

    OUTPUT FORMATS:
      --format pretty   Human-readable with Rich panels (default)
      --format json     Pretty-printed JSON with syntax highlighting
      --format raw      Compact single-line JSON for piping

    FOR LLMs AND AUTOMATION:
      When fetching data programmatically, use these guidelines:

      FETCH BY ID (when you have a specific trace/thread ID):
        langsmith-fetch trace <trace-id> --format raw
        langsmith-fetch thread <thread-id> --format raw

      BULK FETCH MULTIPLE (saves to directory - RECOMMENDED DEFAULT):
        langsmith-fetch traces ./output-folder --limit 10
        langsmith-fetch threads ./output-folder --limit 10
        # Creates one JSON file per trace/thread in output-folder/
        # USE THIS BY DEFAULT unless user explicitly asks for stdout

      FETCH TO STDOUT (only if user explicitly requests it):
        langsmith-fetch traces --project-uuid <uuid> --format raw
        langsmith-fetch threads --project-uuid <uuid> --format raw
        NOTE: For threads, --project-uuid is REQUIRED

    WORKFLOW EXAMPLES:
      # Bulk export to directory (RECOMMENDED - use this by default)
      langsmith-fetch traces ./my-traces --limit 10
      langsmith-fetch threads ./my-threads --limit 25

      # Fetch to stdout (only if user explicitly wants stdout output)
      langsmith-fetch traces --limit 5 --format json
      langsmith-fetch threads --limit 5 --format json

      # Quick inspection of single item
      langsmith-fetch trace <trace-id>
      langsmith-fetch thread <thread-id>
    """
    pass


@main.command()
@click.argument("thread_id", metavar="THREAD_ID")
@click.option(
    "--project-uuid",
    metavar="UUID",
    help="LangSmith project UUID (overrides config). Find in UI or via trace session_id.",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["raw", "json", "pretty"]),
    help="Output format: raw (compact JSON), json (pretty JSON), pretty (human-readable panels)",
)
@click.option(
    "--file",
    "output_file",
    metavar="PATH",
    help="Save output to file instead of printing to stdout",
)
def thread(thread_id, project_uuid, format_type, output_file):
    """Fetch messages for a LangGraph thread by thread_id.

    A thread represents a conversation or session containing multiple traces. Each
    trace in the thread represents one turn or execution. This command retrieves
    all messages from all traces in the thread.

    \b
    ARGUMENTS:
      THREAD_ID   LangGraph thread identifier (e.g., 'test-email-agent-thread')

    \b
    RETURNS:
      List of all messages from all traces in the thread, ordered chronologically.

    \b
    EXAMPLES:
      # Fetch thread with project UUID from config
      langsmith-fetch thread test-email-agent-thread

      # Fetch thread with explicit project UUID
      langsmith-fetch thread my-thread --project-uuid 80f1ecb3-a16b-411e-97ae-1c89adbb5c49

      # Fetch thread as JSON for parsing
      langsmith-fetch thread test-email-agent-thread --format json

    \b
    PREREQUISITES:
      - LANGSMITH_API_KEY environment variable must be set, or
        API key stored via: langsmith-fetch config set api-key <key>
      - Project UUID must be set via: langsmith-fetch config set project-uuid <uuid>
        or provided with --project-uuid option

    \b
    FINDING PROJECT UUID:
      The project UUID can be found in the LangSmith UI or programmatically:
        from langsmith import Client
        run = Client().read_run('<any-trace-id>')
        print(run.session_id)  # This is your project UUID
    """

    # Get API key
    base_url = config.get_base_url()
    api_key = config.get_api_key()
    if not api_key:
        click.echo(
            "Error: LANGSMITH_API_KEY not found in environment or config", err=True
        )
        sys.exit(1)

    # Get project UUID (from option or config)
    if not project_uuid:
        project_uuid = config.get_project_uuid()

    if not project_uuid:
        click.echo(
            "Error: project-uuid required. Pass --project-uuid <uuid> flag",
            err=True,
        )
        sys.exit(1)

    # Get format (from option or config)
    if not format_type:
        format_type = config.get_default_format()

    try:
        # Fetch thread with metadata and feedback
        thread_data = fetchers.fetch_thread_with_metadata(
            thread_id, project_uuid, base_url=base_url, api_key=api_key
        )

        # Output with metadata and feedback
        formatters.print_formatted_trace(thread_data, format_type, output_file)

    except Exception as e:
        click.echo(f"Error fetching thread: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("trace_id", metavar="TRACE_ID")
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["raw", "json", "pretty"]),
    help="Output format: raw (compact JSON), json (pretty JSON), pretty (human-readable panels)",
)
@click.option(
    "--file",
    "output_file",
    metavar="PATH",
    help="Save output to file instead of printing to stdout",
)
@click.option(
    "--include-metadata",
    is_flag=True,
    default=False,
    help="Include run metadata (status, timing, tokens, costs) in output",
)
@click.option(
    "--include-feedback",
    is_flag=True,
    default=False,
    help="Include feedback data in output (requires extra API call)",
)
def trace(trace_id, format_type, output_file, include_metadata, include_feedback):
    """Fetch messages for a single trace by trace ID.

    A trace represents a single execution path containing multiple runs (LLM calls,
    tool executions). This command retrieves all messages from that trace.

    \b
    ARGUMENTS:
      TRACE_ID    LangSmith trace UUID (e.g., 3b0b15fe-1e3a-4aef-afa8-48df15879cfe)

    \b
    RETURNS:
      List of messages with role, content, tool calls (default).
      With --include-metadata: Dictionary with messages, metadata, and feedback.

    \b
    EXAMPLES:
      # Fetch trace messages only (default)
      langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe

      # Fetch trace with metadata (status, timing, tokens, costs)
      langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe --include-metadata

      # Fetch trace with both metadata and feedback
      langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe --include-metadata --include-feedback

      # Fetch trace as JSON for parsing
      langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe --format json

    \b
    PREREQUISITES:
      - LANGSMITH_API_KEY environment variable must be set, or
      - API key stored via: langsmith-fetch config set api-key <key>
    """

    # Get API key
    base_url = config.get_base_url()
    api_key = config.get_api_key()
    if not api_key:
        click.echo(
            "Error: LANGSMITH_API_KEY not found in environment or config", err=True
        )
        sys.exit(1)

    # Get format (from option or config)
    if not format_type:
        format_type = config.get_default_format()

    try:
        # Fetch trace with or without metadata/feedback
        if include_metadata or include_feedback:
            # Fetch with metadata and/or feedback
            trace_data = fetchers.fetch_trace_with_metadata(
                trace_id,
                base_url=base_url,
                api_key=api_key,
                include_feedback=include_feedback,
            )
            # Output with metadata and feedback
            formatters.print_formatted_trace(trace_data, format_type, output_file)
        else:
            # Fetch messages only (no metadata/feedback)
            messages = fetchers.fetch_trace(trace_id, base_url=base_url, api_key=api_key)
            # Output just messages
            formatters.print_formatted(messages, format_type, output_file)

    except Exception as e:
        click.echo(f"Error fetching trace: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("output_dir", type=click.Path(), required=False, metavar="[OUTPUT_DIR]")
@click.option(
    "--project-uuid",
    metavar="UUID",
    help="LangSmith project UUID (overrides config). Find in UI or via trace session_id.",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=1,
    help="Maximum number of threads to fetch (default: 1)",
)
@click.option(
    "--last-n-minutes",
    type=int,
    metavar="N",
    help="Only search threads from the last N minutes",
)
@click.option(
    "--since",
    metavar="TIMESTAMP",
    help="Only search threads since ISO timestamp (e.g., 2025-12-09T10:00:00Z)",
)
@click.option(
    "--filename-pattern",
    default="{thread_id}.json",
    help="Filename pattern for saved threads (directory mode only). Use {thread_id} for thread ID, {index} for sequential number (default: {thread_id}.json)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["raw", "json", "pretty"]),
    help="Output format: raw (compact JSON), json (pretty JSON), pretty (human-readable panels)",
)
@click.option(
    "--no-progress",
    is_flag=True,
    default=False,
    help="Disable progress bar display during fetch",
)
@click.option(
    "--max-concurrent",
    type=int,
    default=5,
    help="Maximum concurrent thread fetches (default: 5, max recommended: 10)",
)
def threads(
    output_dir,
    project_uuid,
    limit,
    last_n_minutes,
    since,
    filename_pattern,
    format_type,
    no_progress,
    max_concurrent,
):
    """Fetch recent threads from LangSmith BY CHRONOLOGICAL TIME.

    This command has TWO MODES:

    \b
    DIRECTORY MODE (with OUTPUT_DIR) - RECOMMENDED DEFAULT:
      - Saves each thread as a separate JSON file in OUTPUT_DIR
      - Use --limit to control how many threads (default: 1)
      - Use --filename-pattern to customize filenames
      - Examples:
          langsmith-fetch threads ./my-threads --limit 10
          langsmith-fetch threads ./my-threads --limit 25 --filename-pattern "thread_{index:03d}.json"
      - USE THIS MODE BY DEFAULT unless user explicitly requests stdout output

    \b
    STDOUT MODE (no OUTPUT_DIR) - Only if user explicitly requests it:
      - Fetch threads and print to stdout
      - Use --limit to fetch multiple threads
      - Use --format to control output format (raw, json, pretty)
      - Examples:
          langsmith-fetch threads                          # Fetch latest thread, pretty format
          langsmith-fetch threads --format json            # Fetch latest, JSON format
          langsmith-fetch threads --limit 5                # Fetch 5 latest threads

    \b
    TEMPORAL FILTERING (both modes):
      - --last-n-minutes N: Only fetch threads from last N minutes
      - --since TIMESTAMP: Only fetch threads since specific time
      - Examples:
          langsmith-fetch threads --last-n-minutes 30
          langsmith-fetch threads --since 2025-12-09T10:00:00Z
          langsmith-fetch threads ./dir --limit 10 --last-n-minutes 60

    \b
    IMPORTANT:
      - Fetches threads by chronological timestamp (most recent first)
      - Project UUID is REQUIRED (via --project-uuid or config)

    \b
    PREREQUISITES:
      - LANGSMITH_API_KEY environment variable or stored in config
      - Project UUID (required, via config or --project-uuid flag)
    """
    from rich.console import Console

    console = Console()

    # Validate mutually exclusive options
    if last_n_minutes is not None and since is not None:
        click.echo(
            "Error: --last-n-minutes and --since are mutually exclusive", err=True
        )
        sys.exit(1)

    # Get API key and base URL
    base_url = config.get_base_url()
    api_key = config.get_api_key()
    if not api_key:
        click.echo(
            "Error: LANGSMITH_API_KEY not found in environment or config", err=True
        )
        sys.exit(1)

    # Get project UUID (from option or config) - REQUIRED
    if not project_uuid:
        project_uuid = config.get_project_uuid()

    if not project_uuid:
        click.echo(
            "Error: project-uuid required. Set via config or pass --project-uuid flag",
            err=True,
        )
        sys.exit(1)

    # DIRECTORY MODE: output_dir provided
    if output_dir:
        # Check if user mistakenly passed a thread ID (UUID) instead of directory
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        if re.match(uuid_pattern, output_dir, re.IGNORECASE):
            click.echo(
                f"Error: '{output_dir}' looks like a UUID, not a directory path.",
                err=True,
            )
            click.echo(
                "To fetch a specific thread by ID, use: langsmith-fetch thread <thread-id>",
                err=True,
            )
            click.echo(
                "To fetch multiple threads to a directory, use: langsmith-fetch threads <directory-path>",
                err=True,
            )
            sys.exit(1)

        # Validate incompatible options
        if format_type:
            click.echo(
                "Warning: --format ignored in directory mode (files are always JSON)",
                err=True,
            )

        # Validate filename pattern
        has_thread_id = re.search(r"\{thread_id[^}]*\}", filename_pattern)
        has_index = re.search(r"\{index[^}]*\}", filename_pattern) or re.search(
            r"\{idx[^}]*\}", filename_pattern
        )
        if not (has_thread_id or has_index):
            click.echo(
                "Error: Filename pattern must contain {thread_id} or {index}", err=True
            )
            sys.exit(1)

        # Create output directory
        output_path = Path(output_dir).resolve()
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            click.echo(f"Error: Cannot create output directory: {e}", err=True)
            sys.exit(1)

        # Verify writable
        if not os.access(output_path, os.W_OK):
            click.echo(
                f"Error: Output directory is not writable: {output_path}", err=True
            )
            sys.exit(1)

        # Fetch threads
        click.echo(f"Fetching up to {limit} recent thread(s)...")
        try:
            threads_data = fetchers.fetch_recent_threads(
                project_uuid,
                base_url,
                api_key,
                limit,
                last_n_minutes=last_n_minutes,
                since=since,
                max_workers=max_concurrent,
                show_progress=not no_progress,
            )
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"Error fetching threads: {e}", err=True)
            sys.exit(1)

        if not threads_data:
            click.echo("No threads found.", err=True)
            sys.exit(1)

        click.echo(f"Found {len(threads_data)} thread(s). Saving to {output_path}/")

        # Save each thread to file
        for index, (thread_id, messages) in enumerate(threads_data, start=1):
            filename_str = filename_pattern.format(
                thread_id=thread_id, index=index, idx=index
            )
            safe_filename = sanitize_filename(filename_str)
            if not safe_filename.endswith(".json"):
                safe_filename = f"{safe_filename}.json"

            filename = output_path / safe_filename
            with open(filename, "w") as f:
                json.dump(messages, f, indent=2, default=str)
            click.echo(
                f"  ✓ Saved {thread_id} to {safe_filename} ({len(messages)} messages)"
            )

        click.echo(
            f"\n✓ Successfully saved {len(threads_data)} thread(s) to {output_path}/"
        )

    # STDOUT MODE: no output_dir
    else:
        # Get format
        if not format_type:
            format_type = config.get_default_format()

        try:
            threads_data = fetchers.fetch_recent_threads(
                project_uuid,
                base_url,
                api_key,
                limit,
                last_n_minutes=last_n_minutes,
                since=since,
                max_workers=max_concurrent,
                show_progress=not no_progress,
            )

            if not threads_data:
                click.echo("No threads found.", err=True)
                sys.exit(1)

            # For single thread, just output the messages
            if limit == 1 and len(threads_data) == 1:
                thread_id, messages = threads_data[0]
                formatters.print_formatted(messages, format_type, output_file=None)
            else:
                # For multiple threads, output all as a list
                all_threads = []
                for thread_id, messages in threads_data:
                    all_threads.append({"thread_id": thread_id, "messages": messages})
                formatters.print_formatted(all_threads, format_type, output_file=None)

        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"Error fetching threads: {e}", err=True)
            sys.exit(1)


@main.command()
@click.argument("output_dir", type=click.Path(), required=False, metavar="[OUTPUT_DIR]")
@click.option(
    "--project-uuid",
    metavar="UUID",
    help="LangSmith project UUID (overrides config). Find in UI or via trace session_id.",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=1,
    help="Maximum number of traces to fetch (default: 1)",
)
@click.option(
    "--last-n-minutes",
    type=int,
    metavar="N",
    help="Only search traces from the last N minutes",
)
@click.option(
    "--since",
    metavar="TIMESTAMP",
    help="Only search traces since ISO timestamp (e.g., 2025-12-09T10:00:00Z)",
)
@click.option(
    "--filename-pattern",
    default="{trace_id}.json",
    help="Filename pattern for saved traces (directory mode only). Use {trace_id} for ID, {index} for sequential number (default: {trace_id}.json)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["raw", "json", "pretty"]),
    help="Output format: raw (compact JSON), json (pretty JSON), pretty (human-readable panels)",
)
@click.option(
    "--file",
    "output_file",
    metavar="PATH",
    help="Save output to file instead of stdout (stdout mode only)",
)
@click.option(
    "--no-progress",
    is_flag=True,
    default=False,
    help="Disable progress bar display during fetch",
)
@click.option(
    "--max-concurrent",
    type=int,
    default=5,
    help="Maximum concurrent trace fetches (default: 5, max recommended: 10)",
)
@click.option(
    "--include-metadata",
    is_flag=True,
    default=False,
    help="Include run metadata (status, timing, tokens, costs) in output",
)
@click.option(
    "--include-feedback",
    is_flag=True,
    default=False,
    help="Include feedback data in output (requires extra API call)",
)
def traces(
    output_dir,
    project_uuid,
    limit,
    last_n_minutes,
    since,
    filename_pattern,
    format_type,
    output_file,
    no_progress,
    max_concurrent,
    include_metadata,
    include_feedback,
):
    """Fetch recent traces from LangSmith BY CHRONOLOGICAL TIME.

    This command has TWO MODES:

    \b
    DIRECTORY MODE (with OUTPUT_DIR) - RECOMMENDED DEFAULT:
      - Saves each trace as a separate JSON file in OUTPUT_DIR
      - Use --limit to control how many traces (default: 1)
      - Use --filename-pattern to customize filenames
      - Examples:
          langsmith-fetch traces ./my-traces --limit 10
          langsmith-fetch traces ./my-traces --limit 25 --filename-pattern "trace_{index:03d}.json"
      - USE THIS MODE BY DEFAULT unless user explicitly requests stdout output

    \b
    STDOUT MODE (no OUTPUT_DIR) - Only if user explicitly requests it:
      - Fetch traces and print to stdout or save to single file
      - Use --limit to fetch multiple traces
      - Use --format to control output format (raw, json, pretty)
      - Use --file to save to a single file instead of stdout
      - Examples:
          langsmith-fetch traces                          # Fetch latest trace, pretty format
          langsmith-fetch traces --format json            # Fetch latest, JSON format
          langsmith-fetch traces --limit 5                # Fetch 5 latest traces
          langsmith-fetch traces --file out.json          # Save latest to file

    \b
    TEMPORAL FILTERING (both modes):
      - --last-n-minutes N: Only fetch traces from last N minutes
      - --since TIMESTAMP: Only fetch traces since specific time
      - Examples:
          langsmith-fetch traces --last-n-minutes 30
          langsmith-fetch traces --since 2025-12-09T10:00:00Z
          langsmith-fetch traces ./dir --limit 10 --last-n-minutes 60

    \b
    IMPORTANT:
      - Fetches traces by chronological timestamp (most recent first)
      - Always use --project-uuid to target specific project (or set via config)
      - Without --project-uuid, searches ALL projects (may return unexpected results)

    \b
    PREREQUISITES:
      - LANGSMITH_API_KEY environment variable or stored in config
      - Optional: Project UUID for filtering (recommended)
    """
    from rich.console import Console

    console = Console()

    # Validate mutually exclusive options
    if last_n_minutes is not None and since is not None:
        click.echo(
            "Error: --last-n-minutes and --since are mutually exclusive", err=True
        )
        sys.exit(1)

    # Get API key and base URL
    base_url = config.get_base_url()
    api_key = config.get_api_key()
    if not api_key:
        click.echo(
            "Error: LANGSMITH_API_KEY not found in environment or config", err=True
        )
        sys.exit(1)

    # Get project UUID from config if not provided
    if not project_uuid:
        project_uuid = config.get_project_uuid()

    # DIRECTORY MODE: output_dir provided
    if output_dir:
        # Check if user mistakenly passed a trace ID instead of directory
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        if re.match(uuid_pattern, output_dir, re.IGNORECASE):
            click.echo(
                f"Error: '{output_dir}' looks like a trace ID, not a directory path.",
                err=True,
            )
            click.echo(
                "To fetch a specific trace by ID, use: langsmith-fetch trace <trace-id>",
                err=True,
            )
            click.echo(
                "To fetch multiple traces to a directory, use: langsmith-fetch traces <directory-path>",
                err=True,
            )
            sys.exit(1)

        # Validate incompatible options
        if format_type:
            click.echo(
                "Warning: --format ignored in directory mode (files are always JSON)",
                err=True,
            )
        if output_file:
            click.echo("Warning: --file ignored in directory mode", err=True)

        # Validate filename pattern
        has_trace_id = re.search(r"\{trace_id[^}]*\}", filename_pattern)
        has_index = re.search(r"\{index[^}]*\}", filename_pattern) or re.search(
            r"\{idx[^}]*\}", filename_pattern
        )
        if not (has_trace_id or has_index):
            click.echo(
                "Error: Filename pattern must contain {trace_id} or {index}", err=True
            )
            sys.exit(1)

        # Create output directory
        output_path = Path(output_dir).resolve()
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            click.echo(f"Error: Cannot create output directory: {e}", err=True)
            sys.exit(1)

        # Verify writable
        if not os.access(output_path, os.W_OK):
            click.echo(
                f"Error: Output directory is not writable: {output_path}", err=True
            )
            sys.exit(1)

        # Fetch traces
        click.echo(f"Fetching up to {limit} recent trace(s)...")
        try:
            traces_data, timing_info = fetchers.fetch_recent_traces(
                api_key=api_key,
                base_url=base_url,
                limit=limit,
                project_uuid=project_uuid,
                last_n_minutes=last_n_minutes,
                since=since,
                max_workers=max_concurrent,
                show_progress=not no_progress,
                return_timing=True,
                include_metadata=include_metadata,
                include_feedback=include_feedback,
            )
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"Error fetching traces: {e}", err=True)
            sys.exit(1)

        # Display timing information
        total_time = timing_info.get("total_duration", 0)
        fetch_time = timing_info.get("fetch_duration", 0)
        avg_time = timing_info.get("avg_per_trace", 0)

        click.echo(
            f"Found {len(traces_data)} trace(s) in {total_time:.2f}s. Saving to {output_path}/"
        )
        if len(traces_data) > 1 and avg_time > 0:
            click.echo(
                f"  (Fetch time: {fetch_time:.2f}s, avg: {avg_time:.2f}s per trace)"
            )

        # Save each trace to file with metadata and feedback
        for index, (trace_id, trace_data) in enumerate(traces_data, start=1):
            filename_str = filename_pattern.format(
                trace_id=trace_id, index=index, idx=index
            )
            safe_filename = sanitize_filename(filename_str)
            if not safe_filename.endswith(".json"):
                safe_filename = f"{safe_filename}.json"

            filename = output_path / safe_filename
            with open(filename, "w") as f:
                json.dump(trace_data, f, indent=2, default=str)

            # Show summary of saved data
            # Handle both list (include_metadata=False) and dict (include_metadata=True) cases
            if isinstance(trace_data, dict):
                messages_count = len(trace_data.get("messages", []))
                feedback_count = len(trace_data.get("feedback", []))
                status = trace_data.get("metadata", {}).get("status", "unknown")
                summary = f"{messages_count} messages, status: {status}"
                if feedback_count > 0:
                    summary += f", {feedback_count} feedback"
            else:
                # trace_data is a list of messages
                messages_count = len(trace_data)
                summary = f"{messages_count} messages"

            click.echo(f"  ✓ Saved {trace_id} to {safe_filename} ({summary})")

        click.echo(
            f"\n✓ Successfully saved {len(traces_data)} trace(s) to {output_path}/"
        )

    # STDOUT MODE: no output_dir
    else:
        # Get format
        if not format_type:
            format_type = config.get_default_format()

        try:
            # Fetch traces
            traces_data = fetchers.fetch_recent_traces(
                api_key=api_key,
                base_url=base_url,
                limit=limit,
                project_uuid=project_uuid,
                last_n_minutes=last_n_minutes,
                since=since,
                max_workers=max_concurrent,
                show_progress=not no_progress,
                return_timing=False,
                include_metadata=include_metadata,
                include_feedback=include_feedback,
            )

            # For limit=1, output single trace directly
            if limit == 1 and len(traces_data) == 1:
                trace_id, trace_data = traces_data[0]
                if output_file:
                    formatters.print_formatted_trace(trace_data, format_type, output_file)
                    click.echo(f"Saved trace to {output_file}")
                else:
                    formatters.print_formatted_trace(trace_data, format_type, None)

            # For limit>1, output as array
            else:
                # traces_data is already a list of (trace_id, trace_data) tuples
                output_data = [trace_data for _, trace_data in traces_data]

                # Output to file or stdout
                if output_file:
                    with open(output_file, "w") as f:
                        if format_type == "raw":
                            json.dump(output_data, f, default=str)
                        else:
                            json.dump(output_data, f, indent=2, default=str)
                    click.echo(f"Saved {len(traces_data)} trace(s) to {output_file}")
                else:
                    if format_type == "raw":
                        click.echo(json.dumps(output_data, default=str))
                    elif format_type == "json":
                        from rich.syntax import Syntax

                        json_str = json.dumps(output_data, indent=2, default=str)
                        syntax = Syntax(
                            json_str, "json", theme="monokai", line_numbers=False
                        )
                        console.print(syntax)
                    else:  # pretty
                        for trace_id, trace_data in traces_data:
                            click.echo(f"\n{'=' * 60}")
                            click.echo(f"Trace: {trace_id}")
                            click.echo("=" * 60)
                            formatters.print_formatted_trace(trace_data, "pretty", None)

        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"Error fetching traces: {e}", err=True)
            sys.exit(1)


@main.command("tree")
@click.argument("trace_id_or_url", metavar="TRACE_ID")
@click.option(
    "--output-dir",
    type=click.Path(),
    metavar="PATH",
    help="Save tree.json, summary.json, and NAVIGATION.md to directory",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["json", "pretty", "summary"]),
    default="pretty",
    help="Output format (default: pretty)",
)
@click.option(
    "--file",
    "output_file",
    metavar="PATH",
    help="Save output to specific file (stdout mode only)",
)
@click.option(
    "--max-depth",
    type=int,
    metavar="N",
    help="Limit tree depth in output (default: unlimited)",
)
@click.option(
    "--show-ids",
    is_flag=True,
    default=False,
    help="Include run IDs in pretty output",
)
def tree_cmd(trace_id_or_url, output_dir, format_type, output_file, max_depth, show_ids):
    """Fetch trace execution tree (skeleton only, no inputs/outputs).

    Fetches all runs in a trace with metadata (tokens, cost, duration, status)
    but NOT the inputs/outputs. This allows exploring trace structure before
    selectively fetching full data for specific runs.

    \b
    ARGUMENTS:
      TRACE_ID    LangSmith trace UUID or public share URL

    \b
    OUTPUT MODES:
      --format pretty   Rich formatted tree view (default)
      --format json     Full tree as JSON
      --format summary  Compact summary statistics only

    \b
    EXAMPLES:
      # View tree structure
      langsmith-fetch tree 3b0b15fe-1e3a-4aef-afa8-48df15879cfe

      # Save to directory with navigation guide
      langsmith-fetch tree 3b0b15fe-... --output-dir ./trace-data/

      # Get summary only
      langsmith-fetch tree 3b0b15fe-... --format summary

      # Public trace URL
      langsmith-fetch tree https://smith.langchain.com/public/abc123/r

    \b
    OUTPUT DIRECTORY STRUCTURE (when using --output-dir):
      {output-dir}/
      ├── tree.json           # Full tree structure
      ├── summary.json        # Summary statistics
      ├── runs/               # For individual run data (initially empty)
      │   └── .gitkeep
      └── NAVIGATION.md       # Instructions for exploring the trace
    """
    from .tree import format_tree_pretty, generate_navigation_md

    # Get API key
    base_url = config.get_base_url()
    api_key = config.get_api_key()

    # Check if this is a public URL
    is_public_url = trace_id_or_url.startswith("http")

    if is_public_url:
        # Handle public URL
        try:
            from .public import fetch_public_trace_tree, parse_langsmith_url

            parsed = parse_langsmith_url(trace_id_or_url)
            if parsed["is_public"]:
                # Fetch without auth
                result = fetch_public_trace_tree(trace_id_or_url, base_url=base_url)
            else:
                # Extract trace_id and use normal fetch
                if not api_key:
                    click.echo(
                        "Error: LANGSMITH_API_KEY required for non-public traces",
                        err=True,
                    )
                    sys.exit(1)
                result = fetchers.fetch_trace_tree(
                    parsed["trace_id"], base_url=base_url, api_key=api_key
                )
        except ImportError:
            click.echo(
                "Error: Public URL support requires the public module", err=True
            )
            sys.exit(1)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    else:
        # Direct trace ID - requires auth
        if not api_key:
            click.echo(
                "Error: LANGSMITH_API_KEY not found in environment or config",
                err=True,
            )
            sys.exit(1)

        try:
            result = fetchers.fetch_trace_tree(
                trace_id_or_url, base_url=base_url, api_key=api_key
            )
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except (KeyboardInterrupt, SystemExit):
            raise
        except (requests.RequestException, IOError) as e:
            click.echo(f"Error fetching tree: {e}", err=True)
            sys.exit(1)

    # OUTPUT MODE: Directory
    if output_dir:
        output_path = Path(output_dir).resolve()
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            (output_path / "runs").mkdir(exist_ok=True)
            # Create .gitkeep in runs directory
            (output_path / "runs" / ".gitkeep").touch()
        except (OSError, PermissionError) as e:
            click.echo(f"Error: Cannot create output directory: {e}", err=True)
            sys.exit(1)

        # Save tree.json
        tree_file = output_path / "tree.json"
        with open(tree_file, "w") as f:
            json.dump(result, f, indent=2, default=str)
        click.echo(f"  ✓ Saved tree.json ({result['total_runs']} runs)")

        # Save summary.json
        summary_file = output_path / "summary.json"
        with open(summary_file, "w") as f:
            json.dump(result["summary"], f, indent=2, default=str)
        click.echo("  ✓ Saved summary.json")

        # Generate and save NAVIGATION.md
        navigation_md = generate_navigation_md(
            trace_id=result["trace_id"],
            tree=result["tree"],
            summary=result["summary"],
            output_dir=str(output_path),
            fetched_at=result["fetched_at"],
        )
        nav_file = output_path / "NAVIGATION.md"
        with open(nav_file, "w") as f:
            f.write(navigation_md)
        click.echo("  ✓ Saved NAVIGATION.md")

        click.echo(f"\n✓ Trace data saved to {output_path}/")
        click.echo(f"  Use: langsmith-fetch run <run-id> --output-dir {output_path}")

    # OUTPUT MODE: File or stdout
    else:
        if format_type == "json":
            output_data = json.dumps(result, indent=2, default=str)
            if output_file:
                with open(output_file, "w") as f:
                    f.write(output_data)
                click.echo(f"Saved to {output_file}")
            else:
                from rich.syntax import Syntax
                from rich.console import Console
                console = Console()
                syntax = Syntax(output_data, "json", theme="monokai", line_numbers=False)
                console.print(syntax)

        elif format_type == "summary":
            summary = result["summary"]
            output_data = json.dumps(summary, indent=2, default=str)
            if output_file:
                with open(output_file, "w") as f:
                    f.write(output_data)
                click.echo(f"Saved to {output_file}")
            else:
                click.echo(f"Trace: {result['trace_id']}")
                click.echo(f"Total runs: {summary['total_runs']}")
                click.echo(f"Total tokens: {summary['total_tokens']:,}")
                click.echo(f"Total cost: ${summary['total_cost']:.5f}")
                if summary['total_duration_ms']:
                    click.echo(f"Duration: {summary['total_duration_ms'] / 1000:.2f}s")
                if summary['models_used']:
                    click.echo(f"Models: {', '.join(summary['models_used'])}")
                if summary['has_errors']:
                    click.echo(f"Errors: {summary['error_count']}")

        else:  # pretty
            formatted = format_tree_pretty(
                result["tree"],
                result["summary"],
                show_ids=show_ids,
                max_depth=max_depth,
            )
            if output_file:
                with open(output_file, "w") as f:
                    f.write(formatted)
                click.echo(f"Saved to {output_file}")
            else:
                click.echo(formatted)


@main.command("run")
@click.argument("run_id", metavar="RUN_ID")
@click.option(
    "--output-dir",
    type=click.Path(),
    metavar="PATH",
    help="Save to trace directory structure ({output-dir}/runs/{run-id}/)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["json", "pretty", "raw"]),
    default="pretty",
    help="Output format (default: pretty)",
)
@click.option(
    "--file",
    "output_file",
    metavar="PATH",
    help="Save to specific file",
)
@click.option(
    "--include-events",
    is_flag=True,
    default=False,
    help="Include streaming events (can be large)",
)
@click.option(
    "--extract",
    metavar="FIELD",
    help="Extract and display specific field only (e.g., inputs.messages)",
)
def run_cmd(run_id, output_dir, format_type, output_file, include_events, extract):
    """Fetch complete data for a single run.

    Retrieves full run data including inputs, outputs, and metadata for a specific
    run by its UUID.

    \b
    ARGUMENTS:
      RUN_ID    LangSmith run UUID

    \b
    EXAMPLES:
      # View run data
      langsmith-fetch run abc123-def456

      # Save to trace directory
      langsmith-fetch run abc123 --output-dir ./trace-data/

      # Extract specific field
      langsmith-fetch run abc123 --extract inputs.messages --format json

      # Include streaming events
      langsmith-fetch run abc123 --include-events

    \b
    OUTPUT DIRECTORY STRUCTURE (when using --output-dir):
      {output-dir}/runs/{run-id}/
      ├── run.json            # Full run data
      ├── inputs.json         # Just inputs
      ├── outputs.json        # Just outputs
      └── metadata.json       # Extracted metadata
    """
    # Get API key
    base_url = config.get_base_url()
    api_key = config.get_api_key()
    if not api_key:
        click.echo(
            "Error: LANGSMITH_API_KEY not found in environment or config", err=True
        )
        sys.exit(1)

    try:
        result = fetchers.fetch_run(
            run_id,
            base_url=base_url,
            api_key=api_key,
            include_events=include_events,
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except (KeyboardInterrupt, SystemExit):
        raise
    except (requests.RequestException, IOError, json.JSONDecodeError) as e:
        click.echo(f"Error fetching run: {e}", err=True)
        sys.exit(1)

    # Handle --extract option
    if extract:
        # Navigate the dot-separated path
        data = result
        for part in extract.split("."):
            if isinstance(data, dict) and part in data:
                data = data[part]
            elif isinstance(data, list) and part.isdigit():
                idx = int(part)
                if 0 <= idx < len(data):
                    data = data[idx]
                else:
                    click.echo(f"Error: Index {idx} out of range", err=True)
                    sys.exit(1)
            else:
                click.echo(f"Error: Field '{extract}' not found", err=True)
                sys.exit(1)
        result = data

    # OUTPUT MODE: Directory
    if output_dir:
        output_path = Path(output_dir).resolve()
        # Sanitize run_id to prevent path traversal
        safe_run_id = sanitize_filename(run_id)
        run_dir = output_path / "runs" / safe_run_id

        try:
            run_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            click.echo(f"Error: Cannot create directory: {e}", err=True)
            sys.exit(1)

        # Save run.json (full data)
        with open(run_dir / "run.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        click.echo("  ✓ Saved run.json")

        # Save inputs.json
        if isinstance(result, dict) and "inputs" in result:
            with open(run_dir / "inputs.json", "w") as f:
                json.dump(result["inputs"], f, indent=2, default=str)
            click.echo("  ✓ Saved inputs.json")

        # Save outputs.json
        if isinstance(result, dict) and "outputs" in result:
            with open(run_dir / "outputs.json", "w") as f:
                json.dump(result["outputs"], f, indent=2, default=str)
            click.echo("  ✓ Saved outputs.json")

        # Save metadata.json
        if isinstance(result, dict) and "metadata" in result:
            with open(run_dir / "metadata.json", "w") as f:
                json.dump(result["metadata"], f, indent=2, default=str)
            click.echo("  ✓ Saved metadata.json")

        click.echo(f"\n✓ Run data saved to {run_dir}/")

    # OUTPUT MODE: File or stdout
    elif output_file:
        if format_type == "raw":
            with open(output_file, "w") as f:
                json.dump(result, f, default=str)
        else:
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2, default=str)
        click.echo(f"Saved to {output_file}")

    # OUTPUT MODE: stdout
    else:
        if format_type == "raw":
            click.echo(json.dumps(result, default=str))
        elif format_type == "json":
            from rich.syntax import Syntax
            from rich.console import Console
            console = Console()
            json_str = json.dumps(result, indent=2, default=str)
            syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
            console.print(syntax)
        else:  # pretty
            if isinstance(result, dict):
                click.echo("=" * 60)
                click.echo(f"RUN: {result.get('name', 'unknown')}")
                click.echo("=" * 60)
                click.echo(f"ID: {result.get('id')}")
                click.echo(f"Type: {result.get('run_type')}")
                click.echo(f"Status: {result.get('status')}")

                if result.get("error"):
                    click.echo(f"Error: {result['error']}")

                # Metadata
                metadata = result.get("metadata", {})
                if metadata:
                    click.echo("\nMetadata:")
                    if metadata.get("duration_ms"):
                        click.echo(f"  Duration: {metadata['duration_ms']}ms")
                    token_usage = metadata.get("token_usage", {})
                    if token_usage.get("total_tokens"):
                        click.echo(f"  Tokens: {token_usage['total_tokens']}")
                    costs = metadata.get("costs", {})
                    if costs.get("total_cost"):
                        click.echo(f"  Cost: ${costs['total_cost']:.5f}")

                # Inputs preview
                inputs = result.get("inputs", {})
                if inputs:
                    click.echo("\nInputs:")
                    preview = json.dumps(inputs, indent=2, default=str)
                    if len(preview) > 500:
                        preview = preview[:500] + "...(truncated)"
                    click.echo(preview)

                # Outputs preview
                outputs = result.get("outputs", {})
                if outputs:
                    click.echo("\nOutputs:")
                    preview = json.dumps(outputs, indent=2, default=str)
                    if len(preview) > 500:
                        preview = preview[:500] + "...(truncated)"
                    click.echo(preview)
            else:
                # Extracted data (from --extract)
                click.echo(json.dumps(result, indent=2, default=str))


@main.group()
def config_cmd():
    """Manage configuration settings.

    View current configuration settings.
    Configuration is stored in ~/.langsmith-cli/config.yaml and can be edited directly.

    \b
    AVAILABLE SETTINGS:
      project-uuid    LangSmith project UUID (required for thread fetching)
      project-name    LangSmith project name (paired with project-uuid)
      api-key         LangSmith API key (alternative to LANGSMITH_API_KEY env var)
      base-url        LangSmith base URL (alternative to LANGSMITH_ENDPOINT env var, defaults to https://api.smith.langchain.com)
      default-format  Default output format (raw, json, or pretty)

    \b
    EXAMPLES:
      # Check current configuration
      langsmith-fetch config show

      # Edit config file directly
      nano ~/.langsmith-cli/config.yaml
    """
    pass


@config_cmd.command("show")
def config_show():
    """Show current configuration.

    Display all stored configuration values including project UUID, API key
    (partially masked for security), and default format settings.

    \b
    EXAMPLE:
      langsmith-fetch config show

    \b
    OUTPUT:
      Shows the config file location and all stored key-value pairs.
      API keys are partially masked for security (first 10 chars shown).
    """
    try:
        cfg = config.load_config()
        if not cfg:
            click.echo("No configuration found")
            click.echo(f"Config file location: {config.CONFIG_FILE}")
            return

        click.echo("Current configuration:")
        click.echo(f"Location: {config.CONFIG_FILE}\n")
        for key, value in cfg.items():
            # Hide API key for security
            if key in ("api_key", "api-key"):
                value = value[:10] + "..." if value else "(not set)"
            click.echo(f"  {key}: {value}")
    except Exception as e:
        click.echo(f"Error loading config: {e}", err=True)
        sys.exit(1)


# Register config subcommands under main CLI
main.add_command(config_cmd, name="config")


if __name__ == "__main__":
    main()
