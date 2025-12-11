"""Main CLI interface using Click."""

import json
import os
import re
import sys
from pathlib import Path

import click

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
def trace(trace_id, format_type, output_file):
    """Fetch messages for a single trace by trace ID.

    A trace represents a single execution path containing multiple runs (LLM calls,
    tool executions). This command retrieves all messages from that trace.

    \b
    ARGUMENTS:
      TRACE_ID    LangSmith trace UUID (e.g., 3b0b15fe-1e3a-4aef-afa8-48df15879cfe)

    \b
    RETURNS:
      List of messages with role, content, tool calls, and metadata.

    \b
    EXAMPLES:
      # Fetch trace with default format (pretty)
      langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe

      # Fetch trace as JSON for parsing
      langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe --format json

      # Fetch trace as raw JSON for piping
      langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe --format raw

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
        # Fetch trace with metadata and feedback
        trace_data = fetchers.fetch_trace_with_metadata(
            trace_id, base_url=base_url, api_key=api_key
        )

        # Output with metadata and feedback
        formatters.print_formatted_trace(trace_data, format_type, output_file)

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
