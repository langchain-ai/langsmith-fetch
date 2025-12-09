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
      - Project UUID (required for thread fetching only)

    COMMON COMMANDS:
      langsmith-fetch latest                              # Fetch most recent trace
      langsmith-fetch trace <trace-id>                    # Fetch a single trace
      langsmith-fetch thread <thread-id>                  # Fetch single thread
      langsmith-fetch threads <output-dir> --limit 10     # Fetch recent threads (bulk)
      langsmith-fetch config set project-uuid <uuid>      # Configure project UUID
      langsmith-fetch config set api-key <key>            # Store API key in config

    OUTPUT FORMATS:
      --format pretty   Human-readable with Rich panels (default)
      --format json     Pretty-printed JSON with syntax highlighting
      --format raw      Compact single-line JSON for piping
      --file <path>     Save output to file instead of stdout (single traces/threads)

    FOR LLMs AND AUTOMATION:
      When fetching data programmatically, use these guidelines:

      SINGLE TRACE/THREAD (use stdout or --file):
        langsmith-fetch latest --format raw | jq
        langsmith-fetch trace <id> --file output.json
        langsmith-fetch thread <id> --file output.json

      MULTIPLE THREADS (use threads command with directory):
        langsmith-fetch threads ./output-folder --limit 10
        # Creates one JSON file per thread in output-folder/

      The threads command automatically:
        - Creates the output directory if it doesn't exist
        - Sanitizes thread IDs for safe filenames
        - Saves each thread as a separate .json file
        - Returns error if directory is not writable

    WORKFLOW EXAMPLES:
      # Quick inspection (default: pretty format to stdout)
      langsmith-fetch latest

      # Save for processing (raw JSON to file)
      langsmith-fetch latest --format raw --file latest.json

      # Bulk export (multiple threads to folder)
      langsmith-fetch threads ./my-threads --limit 25
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
            "Error: project-uuid required. Set with: langsmith-fetch config set project-uuid <uuid>",
            err=True,
        )
        sys.exit(1)

    # Get format (from option or config)
    if not format_type:
        format_type = config.get_default_format()

    try:
        # Fetch messages
        messages = fetchers.fetch_thread(
            thread_id, project_uuid, base_url=base_url, api_key=api_key
        )

        # Output
        formatters.print_formatted(messages, format_type, output_file)

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
        # Fetch messages
        messages = fetchers.fetch_trace(trace_id, base_url=base_url, api_key=api_key)

        # Output
        formatters.print_formatted(messages, format_type, output_file)

    except Exception as e:
        click.echo(f"Error fetching trace: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("output_dir", type=click.Path(), metavar="OUTPUT_DIR")
@click.option(
    "--project-uuid",
    metavar="UUID",
    help="LangSmith project UUID (overrides config). Find in UI or via trace session_id.",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=10,
    help="Maximum number of threads to fetch (default: 10)",
)
@click.option(
    "--filename-pattern",
    default="{thread_id}.json",
    help="Filename pattern for saved threads. Use {thread_id} for thread ID, {index} for sequential number (default: {thread_id}.json)",
)
def threads(output_dir, project_uuid, limit, filename_pattern):
    """Fetch recent threads for a project and save to files (BULK OPERATION).

    This command is designed for bulk operations where you need multiple threads
    saved to disk for processing. Each thread is saved as a separate JSON file.

    USE THIS COMMAND when:
      - You need multiple threads (not just one)
      - You want to save them to disk for batch processing
      - You're building a dataset or corpus

    USE 'thread' command (singular) when:
      - You need just one specific thread by ID
      - You want stdout output or a single file

    \b
    ARGUMENTS:
      OUTPUT_DIR  Directory where thread files will be saved (created if needed)

    \b
    FILE NAMING:
      - Default pattern: {thread_id}.json
      - Customize with --filename-pattern option
      - Available placeholders: {thread_id}, {index}
      - Example: --filename-pattern "thread_{index:03d}.json" → thread_001.json, thread_002.json
      - All filenames sanitized to ensure safe names across platforms
      - Directory created automatically if it doesn't exist
      - Existing files with same name will be overwritten

    \b
    RETURNS:
      Creates one JSON file per thread in OUTPUT_DIR.
      Each file contains all messages from all traces in that thread.

    \b
    EXAMPLES:
      # Fetch 10 most recent threads to ./my-threads directory (default naming)
      langsmith-fetch threads ./my-threads

      # Fetch 25 most recent threads with sequential numbering
      langsmith-fetch threads ./my-threads --limit 25 --filename-pattern "thread_{index:03d}.json"

      # Use custom pattern with thread ID
      langsmith-fetch threads ./my-threads --filename-pattern "{thread_id}_export.json"

      # Fetch threads with explicit project UUID
      langsmith-fetch threads ./my-threads --project-uuid 80f1ecb3-a16b-411e-97ae-1c89adbb5c49

    \b
    PREREQUISITES:
      - LANGSMITH_API_KEY environment variable must be set, or
        API key stored via: langsmith-fetch config set api-key <key>
      - Project UUID must be set via: langsmith-fetch config set project-uuid <uuid>
        or provided with --project-uuid option
    """

    # Get API key and base URL
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
            "Error: project-uuid required. Set with: langsmith-fetch config set project-uuid <uuid>",
            err=True,
        )
        sys.exit(1)

    # Create and validate output directory
    output_path = Path(output_dir).resolve()

    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        click.echo(f"Error: Cannot create output directory: {e}", err=True)
        sys.exit(1)

    # Verify directory is writable
    if not os.access(output_path, os.W_OK):
        click.echo(f"Error: Output directory is not writable: {output_path}", err=True)
        sys.exit(1)

    try:
        click.echo(
            f"Fetching up to {limit} recent threads from project {project_uuid}..."
        )

        # Fetch recent threads
        threads_data = fetchers.fetch_recent_threads(
            project_uuid, base_url, api_key, limit
        )

        if not threads_data:
            click.echo("No threads found in project.", err=True)
            sys.exit(1)

        click.echo(f"Found {len(threads_data)} thread(s). Saving to {output_path}/")

        # Validate filename pattern (check for placeholders with or without format specs)
        has_thread_id = re.search(r"\{thread_id[^}]*\}", filename_pattern)
        has_index = re.search(r"\{index[^}]*\}", filename_pattern) or re.search(
            r"\{idx[^}]*\}", filename_pattern
        )
        if not (has_thread_id or has_index):
            click.echo(
                "Error: Filename pattern must contain {thread_id} or {index}",
                err=True,
            )
            sys.exit(1)

        # Save each thread to a file
        for index, (thread_id, messages) in enumerate(threads_data, start=1):
            # Generate filename from pattern
            filename_str = filename_pattern.format(
                thread_id=thread_id, index=index, idx=index
            )
            # Sanitize the generated filename
            safe_filename = sanitize_filename(filename_str)
            # Ensure .json extension if not present
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

    except Exception as e:
        click.echo(f"Error fetching threads: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--project-uuid",
    metavar="UUID",
    help="LangSmith project UUID to filter traces (optional, searches all projects if not provided)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["raw", "json", "pretty"]),
    help="Output format: raw (compact JSON), json (pretty JSON), pretty (human-readable panels)",
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
    "--file",
    "output_file",
    metavar="PATH",
    help="Save output to file instead of printing to stdout",
)
def latest(project_uuid, format_type, last_n_minutes, since, output_file):
    """Fetch the most recent trace from LangSmith.

    Automatically finds and fetches the latest root trace without needing to manually
    copy trace IDs from the UI. Perfect for the workflow: "I just did a thing and I
    want the CLI to just grab the trace."

    \b
    RETURNS:
      List of messages from the most recent trace, ordered chronologically.

    \b
    EXAMPLES:
      # Fetch most recent trace across all projects
      langsmith-fetch latest

      # Fetch most recent trace from a specific project
      langsmith-fetch latest --project-uuid 80f1ecb3-a16b-411e-97ae-1c89adbb5c49

      # Fetch most recent trace from last 30 minutes
      langsmith-fetch latest --last-n-minutes 30

      # Fetch most recent trace since a specific time
      langsmith-fetch latest --since 2025-12-09T10:00:00Z

      # Fetch with JSON output format
      langsmith-fetch latest --format json

      # Save to file
      langsmith-fetch latest --file latest.json --format raw

    \b
    PREREQUISITES:
      - LANGSMITH_API_KEY environment variable must be set, or
      - API key stored via: langsmith-fetch config set api-key <key>

    \b
    OPTIONS:
      --project-uuid      Optional filter to search only within a specific project.
                          If not provided, searches across all projects.

      --last-n-minutes    Optional time window to limit search (mutually exclusive with --since)

      --since             Optional ISO timestamp to limit search (mutually exclusive with --last-n-minutes)

      --format            Output format (raw, json, or pretty)

    \b
    NOTES:
      - This command fetches the most recent TRACE only
      - Thread support via SDK is not yet available but will be added in a future release
      - The command searches for root traces only (not child runs)
    """

    # Validate mutually exclusive time filters
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

    # Get project UUID (from option or config, but it's optional)
    if not project_uuid:
        project_uuid = config.get_project_uuid()
    # Note: project_uuid can be None, which means search all projects

    # Get format (from option or config)
    if not format_type:
        format_type = config.get_default_format()

    try:
        # Fetch latest trace
        messages = fetchers.fetch_latest_trace(
            api_key=api_key,
            base_url=base_url,
            project_uuid=project_uuid,
            last_n_minutes=last_n_minutes,
            since=since,
        )

        # Output
        formatters.print_formatted(messages, format_type, output_file)

    except ValueError as e:
        # Handle "No traces found" case
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error fetching latest trace: {e}", err=True)
        sys.exit(1)


@main.group()
def config_cmd():
    """Manage configuration settings.

    Store persistent settings like project UUID, API key, and default output format.
    Configuration is stored in ~/.langsmith-cli/config.yaml

    \b
    AVAILABLE SETTINGS:
      project-uuid    LangSmith project UUID (required for thread fetching)
      api-key         LangSmith API key (alternative to LANGSMITH_API_KEY env var)
      default-format  Default output format (raw, json, or pretty)

    \b
    EXAMPLES:
      langsmith-fetch config set project-uuid 80f1ecb3-a16b-411e-97ae-1c89adbb5c49
      langsmith-fetch config set api-key lsv2_...
      langsmith-fetch config set default-format json
      langsmith-fetch config show
    """
    pass


@config_cmd.command("set")
@click.argument("key", metavar="KEY")
@click.argument("value", metavar="VALUE")
def config_set(key, value):
    """Set a configuration value.

    Store a configuration setting persistently. Common keys include:
      - project-uuid: Required for fetching threads
      - api-key: LangSmith API key (alternative to env var)
      - default-format: Output format (raw, json, or pretty)

    \b
    EXAMPLES:
      langsmith-fetch config set project-uuid 80f1ecb3-a16b-411e-97ae-1c89adbb5c49
      langsmith-fetch config set api-key lsv2_pt_...
      langsmith-fetch config set default-format json
    """
    try:
        config.set_config_value(key, value)
        click.echo(f"✓ Set {key} = {value}")
    except Exception as e:
        click.echo(f"Error setting config: {e}", err=True)
        sys.exit(1)


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
