"""Main CLI interface using Click."""

import click
import sys
from . import config, fetchers, formatters


@click.group()
def main():
    """LangSmith Fetch - Fetch and display LangSmith threads and traces.

    This CLI tool retrieves conversation messages, traces, and threads from LangSmith.

    REQUIREMENTS:
      - LANGSMITH_API_KEY environment variable or stored in config
      - Project UUID (required for thread fetching only)

    COMMON COMMANDS:
      langsmith-fetch trace <trace-id>                    # Fetch a single trace
      langsmith-fetch thread <thread-id>                  # Fetch all traces in a thread
      langsmith-fetch config set project-uuid <uuid>      # Configure project UUID
      langsmith-fetch config set api-key <key>            # Store API key in config

    OUTPUT FORMATS:
      --format pretty   Human-readable with Rich panels (default)
      --format json     Pretty-printed JSON with syntax highlighting
      --format raw      Compact single-line JSON for piping
    """
    pass


@main.command()
@click.argument('thread_id', metavar='THREAD_ID')
@click.option('--project-uuid', metavar='UUID',
              help='LangSmith project UUID (overrides config). Find in UI or via trace session_id.')
@click.option('--format', 'format_type', type=click.Choice(['raw', 'json', 'pretty']),
              help='Output format: raw (compact JSON), json (pretty JSON), pretty (human-readable panels)')
def thread(thread_id, project_uuid, format_type):
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
    api_key = config.get_api_key()
    if not api_key:
        click.echo("Error: LANGSMITH_API_KEY not found in environment or config", err=True)
        sys.exit(1)

    # Get project UUID (from option or config)
    if not project_uuid:
        project_uuid = config.get_project_uuid()

    if not project_uuid:
        click.echo("Error: project-uuid required. Set with: langsmith-fetch config set project-uuid <uuid>", err=True)
        sys.exit(1)

    # Get format (from option or config)
    if not format_type:
        format_type = config.get_default_format()

    try:
        # Fetch messages
        messages = fetchers.fetch_thread(thread_id, project_uuid, api_key)

        # Output
        formatters.print_formatted(messages, format_type)

    except Exception as e:
        click.echo(f"Error fetching thread: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument('trace_id', metavar='TRACE_ID')
@click.option('--format', 'format_type', type=click.Choice(['raw', 'json', 'pretty']),
              help='Output format: raw (compact JSON), json (pretty JSON), pretty (human-readable panels)')
def trace(trace_id, format_type):
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
    api_key = config.get_api_key()
    if not api_key:
        click.echo("Error: LANGSMITH_API_KEY not found in environment or config", err=True)
        sys.exit(1)

    # Get format (from option or config)
    if not format_type:
        format_type = config.get_default_format()

    try:
        # Fetch messages
        messages = fetchers.fetch_trace(trace_id, api_key)

        # Output
        formatters.print_formatted(messages, format_type)

    except Exception as e:
        click.echo(f"Error fetching trace: {e}", err=True)
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


@config_cmd.command('set')
@click.argument('key', metavar='KEY')
@click.argument('value', metavar='VALUE')
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


@config_cmd.command('show')
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
            if key == 'api_key':
                value = value[:10] + "..." if value else "(not set)"
            click.echo(f"  {key}: {value}")
    except Exception as e:
        click.echo(f"Error loading config: {e}", err=True)
        sys.exit(1)


# Register config subcommands under main CLI
main.add_command(config_cmd, name='config')


if __name__ == '__main__':
    main()
