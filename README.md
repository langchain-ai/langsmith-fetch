# LangSmith Fetch

CLI for fetching and displaying LangSmith data with LLM friendly formatting:

- Fetch recent threads from a project and save to files
- Fetch LangGraph thread messages by thread_id
- Fetch individual trace messages by trace ID
- Multiple output formats: raw JSON, pretty JSON, or human-readable
- Config file support for storing project UUID and preferences

![LangSmith Fetch Banner](images/banner.jpg)

## 🚀 Quickstart

### Installation

```bash
# Via pip (coming soon to PyPI)
pip install langsmith-fetch

# For now, install from source
pip install git+https://github.com/langchain-ai/langsmith-fetch.git
```

### Basic Usage

Set your API key:

```bash
export LANGSMITH_API_KEY=lsv2_...
```

Fetch the most recent trace:

```bash
langsmith-fetch latest
```

Fetch a specific trace by ID:

```bash
langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe
```

Set your project UUID and fetch recent threads:

```bash
langsmith-fetch config set project-uuid <your-project-uuid>
langsmith-fetch threads ./my-threads --limit 10
```

Or fetch a specific thread by ID:

```bash
langsmith-fetch thread test-email-agent-thread
```

### Output Formats

LangSmith Fetch supports three output formats for different use cases:

- **`pretty`**: Human-readable Rich panels with color and formatting (default)
  - Best for: Terminal viewing, debugging, manual inspection
  - Example: `langsmith-fetch trace <id>` or `langsmith-fetch trace <id> --format pretty`

- **`json`**: Pretty-printed JSON with syntax highlighting
  - Best for: Reading structured data, copying to other tools
  - Example: `langsmith-fetch trace <id> --format json`

- **`raw`**: Compact single-line JSON for piping
  - Best for: Shell pipelines, automated processing, scripts
  - Example: `langsmith-fetch trace <id> --format raw | jq '.[] | select(.role=="user")'`

### Save to File

All commands support saving output to a file instead of printing to stdout:

```bash
# Save trace to JSON file
langsmith-fetch trace <trace-id> --file output.json --format json

# Save thread to text file
langsmith-fetch thread <thread-id> --file output.txt --format pretty

# Save latest trace to file
langsmith-fetch latest --file latest.json --format raw
```

## Features

### Understanding LangSmith Data Organization

LangSmith organizes data into three levels:
- **Runs**: Individual LLM calls or tool executions
- **Traces**: A collection of runs representing a single execution path (one trace contains multiple runs)
- **Threads**: A collection of traces representing a conversation or session (one thread contains multiple traces)

Learn more in the [LangSmith threads documentation](https://docs.langchain.com/langsmith/threads).

### Command Overview

| Command | What it fetches | Output |
|---------|----------------|--------|
| `latest` | Single most recent **trace** (by time) | stdout or file |
| `trace <id>` | Specific **trace** by ID | stdout or file |
| `thread <id>` | Specific **thread** by ID | stdout or file |
| `threads <dir>` | Multiple recent **threads** (bulk) | Multiple JSON files in directory |

**When to use each:**
- **`latest`** - "I just ran something and want to see the trace"
- **`trace <id>`** - "I have a specific trace ID from the UI"
- **`thread <id>`** - "I have a specific thread ID and want all its messages"
- **`threads <dir>`** - "I want to download multiple threads for batch processing"

### Where to find each ID

You can find each ID in the LangSmith UI as shown in the screenshots below:

**Project ID:**
![Project ID location](images/project_id.png)

**Trace ID:**
![Trace ID location](images/trace_id.png)

**Thread ID:**
![Thread ID location](images/thread_id.png)

Alternatively, you can get the project UUID programmatically:

```python
from langsmith import Client

client = Client()

# Option 1: Get UUID from any trace in the project
run = client.read_run('<any-trace-id>')
print(run.session_id)  # This is your project UUID

# Option 2: Search for project by name
projects = list(client.list_projects())
for p in projects:
    if 'your-project-name' in p.name.lower():
        print(f'Project: {p.name}')
        print(f'UUID: {p.id}')
```

## Configuration

Add your project UUID and API key to the config file:

```bash
# Set project UUID (required for threads, optional but recommended for latest)
langsmith-fetch config set project-uuid <your-project-uuid>

# Set API key (optional, uses LANGSMITH_API_KEY env var by default)
langsmith-fetch config set api-key lsv2_...

# View your configuration
langsmith-fetch config show
```

Config file location: `~/.langsmith-cli/config.yaml`

## Usage

### Fetch Recent Threads

Fetch the most recent threads from a project and save each to a separate JSON file:

```bash
# Fetch 10 most recent threads (default) to ./my-threads directory
langsmith-fetch threads ./my-threads

# Fetch 25 most recent threads
langsmith-fetch threads ./my-threads --limit 25

# Override project UUID
langsmith-fetch threads ./my-threads --project-uuid <uuid>

# Customize filename pattern
langsmith-fetch threads ./my-threads --filename-pattern "thread_{index:03d}.json"
# Creates: thread_001.json, thread_002.json, etc.
```

**File Naming:**
- Default: Files named by thread ID (e.g., `abc123def.json`)
- Custom pattern: Use `--filename-pattern` with placeholders:
  - `{thread_id}` - Thread ID (default: `{thread_id}.json`)
  - `{index}` or `{idx}` - Sequential number starting from 1
  - Format specs supported: `{index:03d}` for zero-padded numbers

### Fetch Thread by LangGraph thread_id

```bash
# With config file (project UUID already set)
langsmith-fetch thread test-email-agent-thread

# Override project UUID
langsmith-fetch thread test-email-agent-thread --project-uuid <uuid>

# Specify output format
langsmith-fetch thread test-email-agent-thread --format json
langsmith-fetch thread test-email-agent-thread --format pretty
langsmith-fetch thread test-email-agent-thread --format raw

# Save to file
langsmith-fetch thread test-email-agent-thread --file output.json --format json
```

### Fetch Trace by UUID

```bash
# Fetch single trace
langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe

# With format option
langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe --format json

# Save to file
langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe --file trace.json --format json
```

### Auto-Fetch Latest Trace

Perfect for the workflow: "I just did a thing and I want the CLI to just grab the trace."

```bash
# Fetch most recent trace across all projects
langsmith-fetch latest

# Fetch most recent trace from a specific project (recommended for faster results)
langsmith-fetch latest --project-uuid 80f1ecb3-a16b-411e-97ae-1c89adbb5c49

# Fetch most recent trace from last 30 minutes
langsmith-fetch latest --last-n-minutes 30

# Fetch most recent trace since a specific time
langsmith-fetch latest --since 2025-12-09T10:00:00Z

# Fetch with JSON output format
langsmith-fetch latest --format json

# Save to file
langsmith-fetch latest --file latest.json --format raw
```

**Notes:**
- The `latest` command currently fetches the most recent trace only. Support for fetching the latest thread will be added in a future release when SDK support becomes available.
- While project UUID is optional, providing it (via config or `--project-uuid`) filters results to a specific project, making searches faster and more targeted.

## Examples

### Basic Thread Fetch

```bash
$ langsmith-fetch thread test-email-agent-thread

╭─────────────────────────── Message 1: USER ───────────────────────────╮
│ Subject: Quick question about next week                               │
│ From: jane@example.com                                                │
│ To: lance@langchain.dev                                               │
│                                                                        │
│ Hi Lance,                                                             │
│ Can we meet next Tuesday at 2pm to discuss the project roadmap?      │
╰────────────────────────────────────────────────────────────────────────╯

╭────────────────────────── Message 2: ASSISTANT ───────────────────────╮
│ Tool: triage_email                                                    │
│ ...                                                                   │
╰────────────────────────────────────────────────────────────────────────╯
```

### JSON Output

```bash
$ langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe --format json

[
  {
    "role": "user",
    "content": "..."
  },
  ...
]
```

## Tests

Run the test suite:

```bash
# Install with test dependencies
pip install -e ".[test]"

# Or with uv
uv sync --extra test

# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=langsmith_cli
```

The test suite includes 50 tests covering:
- All CLI commands (latest, trace, thread, config)
- All output formats (pretty, json, raw)
- Config management and storage
- API fetching and error handling
- Time filtering and SDK integration
- Edge cases and validation

## License

MIT
