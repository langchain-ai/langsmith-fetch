# LangSmith Fetch

CLI for fetching and displaying LangSmith data with LLM friendly formatting:

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

Fetch a trace by ID:

```bash
langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe
```

Fetch a thread by ID with project UUID:

```bash
langsmith-fetch thread test-email-agent-thread --project-uuid <your-project-uuid>
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

## Features

### Understanding LangSmith Data Organization

LangSmith organizes data into three levels:
- **Runs**: Individual LLM calls or tool executions
- **Traces**: A collection of runs representing a single execution path (one trace contains multiple runs)
- **Threads**: A collection of traces representing a conversation or session (one thread contains multiple traces)

Learn more in the [LangSmith threads documentation](https://docs.langchain.com/langsmith/threads).

### Where to find each ID

You can find each ID in the LangSmith UI as shown in the screenshots below:

**Project ID:**
![Project ID location](images/project_id.png)

**Trace ID:**
![Trace ID location](images/trace_id.png)

**Thread ID:**
![Thread ID location](images/thread_id.png)

Alternatively, you can get the project UUID programmatically from any LangSmith trace:

```python
from langsmith import Client

client = Client()
run = client.read_run('<any-trace-id>')
print(run.session_id)  # This is your project UUID
```

## Usage

### Fetch Thread by LangGraph thread_id

```bash
# Fetch with project UUID
langsmith-fetch thread test-email-agent-thread --project-uuid <uuid>

# Specify output format
langsmith-fetch thread test-email-agent-thread --project-uuid <uuid> --format json
langsmith-fetch thread test-email-agent-thread --project-uuid <uuid> --format pretty
langsmith-fetch thread test-email-agent-thread --project-uuid <uuid> --format raw
```

### Fetch Trace by UUID

```bash
# Fetch single trace
langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe

# With format option
langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe --format json
```

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

The test suite includes 34 tests covering:
- All CLI commands (trace, thread, config)
- All output formats (pretty, json, raw)
- Config management and storage
- API fetching and error handling
- Edge cases and validation

## License

MIT
