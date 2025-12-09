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

Set your project UUID and fetch a thread:

```bash
langsmith-fetch config set project-uuid <your-project-uuid>
langsmith-fetch thread test-email-agent-thread
```

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

## Configuration

Add your project UUID and API key to the config file:

```bash
# Set project UUID (required for thread fetching)
langsmith-fetch config set project-uuid <your-project-uuid>

# Set API key (optional, uses LANGSMITH_API_KEY env var by default)
langsmith-fetch config set api-key lsv2_...

# View your configuration
langsmith-fetch config show
```

Config file location: `~/.langsmith-cli/config.yaml`

## Usage

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
```

- **raw**: Compact JSON (single line)
- **json**: Pretty-printed JSON with syntax highlighting
- **pretty**: Human-readable formatted text with Rich panels

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

## Development

Run directly with Python module syntax:

```bash
python -m langsmith_cli thread test-email-agent-thread
```

## License

MIT
