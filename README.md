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
pip install langsmith-fetch
```

### Setup

Set your LangSmith API key and project name:

```bash
export LANGSMITH_API_KEY=lsv2_...
export LANGSMITH_PROJECT=your-project-name
```

That's it! The CLI will automatically fetch traces or threads in `LANGSMITH_PROJECT`.

## Usage coding agent

Start your favorite coding agent and ask questions like the following. Many agents will use the `langsmith-fetch --help` command to understand how to use the CLI and complete your request. 
 
> Use langsmith-fetch to analyze the last 3 threads from my LangSmith project for potential improvements

## Direct Usage

**Fetch recent traces**
```bash
# Fetch 2 most recent traces
langsmith-fetch threads --limit 2
```
<img width="1419" height="304" alt="Screenshot 2025-12-10 at 9 50 39 PM" src="https://github.com/user-attachments/assets/ee0cb14a-0608-44f7-a2e9-1043a42b8be5" />

**Fetch recent threads to a directory (RECOMMENDED):**

```bash
# Fetch 10 most recent threads to ./my-threads directory
langsmith-fetch threads ./my-threads --limit 10
```

**Fetch recent traces to a directory (RECOMMENDED):**

```bash
# Fetch 10 most recent traces to ./my-traces directory
langsmith-fetch traces ./my-traces --limit 10
```

**Fetch specific items by ID:**

```bash
# Fetch a specific trace by ID
langsmith-fetch trace 3b0b15fe-1e3a-4aef-afa8-48df15879cfe

# Fetch a specific thread by ID
langsmith-fetch thread test-email-agent-thread
```

> **Note:** When using `traces` or `threads` commands, always specify an output directory unless you explicitly want stdout output. Directory mode is the recommended default for typical workflows.

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

Single item commands (`trace` and `thread`) support saving output to a file:

```bash
# Save trace to JSON file
langsmith-fetch trace <trace-id> --file output.json --format json

# Save thread to text file
langsmith-fetch thread <thread-id> --file output.txt --format pretty
```

For bulk fetching (`traces` and `threads`), use directory mode instead:

```bash
# RECOMMENDED: Save multiple traces to directory (one file per trace)
langsmith-fetch traces ./my-traces --limit 10

# RECOMMENDED: Save multiple threads to directory (one file per thread)
langsmith-fetch threads ./my-threads --limit 10
```

### Output Structure (v0.3.0+)

Starting from version 0.3.0, all fetch commands return structured data that includes:

**Metadata:**
- Run status (success/error/pending)
- Timing information (start, end, duration)
- Token usage (prompt, completion, total)
- Costs (prompt, completion, total)
- Custom metadata from runs
- Feedback statistics summary

**Feedback:**
- Full feedback objects with scores, comments, and corrections
- Only fetched when feedback exists (smart fetching)
- Includes feedback keys, scores, values, and timestamps

**Example Output Structure:**

```json
{
  "trace_id": "3b0b15fe-1e3a-4aef-afa8-48df15879cfe",
  "messages": [
    {
      "type": "human",
      "content": "Can we meet next Tuesday?",
      "id": "964d69c7-10e2-4de2-89c9-4361c9ea5da7"
    },
    {
      "type": "ai",
      "content": [{"type": "tool_use", "name": "triage_email", "input": {...}}]
    }
  ],
  "metadata": {
    "status": "success",
    "start_time": "2025-12-11T10:00:00.123Z",
    "end_time": "2025-12-11T10:00:05.456Z",
    "duration_ms": 5333,
    "custom_metadata": {
      "user_id": "user-123",
      "thread_id": "test-email-agent-thread"
    },
    "token_usage": {
      "prompt_tokens": 1234,
      "completion_tokens": 567,
      "total_tokens": 1801
    },
    "costs": {
      "prompt_cost": 0.01234,
      "completion_cost": 0.00567,
      "total_cost": 0.01801
    },
    "feedback_stats": {
      "thumbs_up": 3,
      "thumbs_down": 1
    }
  },
  "feedback": [
    {
      "id": "fb-uuid-1",
      "key": "thumbs_up",
      "score": 1,
      "comment": "Great classification!",
      "created_at": "2025-12-11T10:05:00.000Z"
    }
  ]
}
```

**Pretty Format Output:**

When using `--format pretty`, the output includes formatted sections for metadata and feedback before displaying messages:

```
============================================================
RUN METADATA
============================================================
Status: success
Start Time: 2025-12-11T10:00:00.123Z
Duration: 5333ms

Token Usage:
  Prompt: 1234
  Completion: 567
  Total: 1801

Costs:
  Total: $0.01801
  Prompt: $0.01234
  Completion: $0.00567

Custom Metadata:
  user_id: user-123

Feedback Stats:
  thumbs_up: 3
  thumbs_down: 1

============================================================
FEEDBACK
============================================================

Feedback 1:
  Key: thumbs_up
  Score: 1
  Comment: Great classification!
  Created: 2025-12-11T10:05:00.000Z

============================================================
MESSAGES
============================================================
[messages displayed here]
```

### Migration Guide (v0.2.x → v0.3.0)

**Breaking Change:** The output format has changed from a flat list of messages to a structured object with messages, metadata, and feedback.

**Before (v0.2.x):**
```json
[
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]
```

**After (v0.3.0):**
```json
{
  "trace_id": "...",
  "messages": [
    {"type": "human", "content": "..."},
    {"type": "ai", "content": "..."}
  ],
  "metadata": {...},
  "feedback": [...]
}
```

**To Update Your Scripts:**

If you're processing the JSON output, update your code to access the `.messages` field:

```bash
# Before (v0.2.x):
cat trace.json | jq '.[0].content'

# After (v0.3.0):
cat trace.json | jq '.messages[0].content'
```

```python
# Before (v0.2.x):
import json
with open('trace.json') as f:
    messages = json.load(f)
    first_message = messages[0]

# After (v0.3.0):
import json
with open('trace.json') as f:
    trace_data = json.load(f)
    messages = trace_data['messages']
    metadata = trace_data['metadata']
    feedback = trace_data['feedback']
    first_message = messages[0]
```

**Why This Change?**

The new format provides:
- **Rich context**: Understand run performance, costs, and status at a glance
- **Feedback integration**: See user feedback directly alongside traces
- **Better debugging**: Metadata helps identify slow runs or errors quickly
- **Zero extra cost**: Metadata is extracted from existing API responses (no additional API calls)
- **Smart feedback fetching**: Only fetches feedback when it exists, minimizing API overhead

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
| `trace <id>` | Specific **trace** by ID | stdout or file |
| `thread <id>` | Specific **thread** by ID | stdout or file |
| `traces <dir>` | Recent **traces** (bulk) | Multiple JSON files in directory (RECOMMENDED) |
| `threads <dir>` | Recent **threads** (bulk) | Multiple JSON files in directory (RECOMMENDED) |

**When to use each:**
- **`traces <dir>`** - "Fetch recent traces to directory" (RECOMMENDED: use directory mode by default)
- **`threads <dir>`** - "Fetch recent threads to directory" (RECOMMENDED: use directory mode by default)
- **`trace <id>`** - "I have a specific trace ID from the UI"
- **`thread <id>`** - "I have a specific thread ID and want all its messages"

**Important:** For `traces` and `threads` commands, always specify an output directory unless you explicitly need stdout output.

### Where to find each ID

**Note:** With automatic project lookup, you only need the project *name* (from `LANGSMITH_PROJECT` env var), not the UUID. The sections below are only needed if you want to manually set the UUID or fetch specific traces/threads by ID.

You can find each ID in the LangSmith UI as shown in the screenshots below:

**Project ID** (optional with automatic lookup):
![Project ID location](images/project_id.png)

**Trace ID** (for fetching specific traces):
![Trace ID location](images/trace_id.png)

**Thread ID** (for fetching specific threads):
![Thread ID location](images/thread_id.png)

Alternatively, you can get the project UUID programmatically (this is what the CLI does automatically):

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

### Automatic Project Lookup (Recommended)

The easiest way to configure is using environment variables:

```bash
export LANGSMITH_API_KEY=lsv2_...
export LANGSMITH_PROJECT=your-project-name
```

The CLI will automatically look up your project UUID based on the project name. The lookup result is cached for the session, so you only pay the API call cost once.

### Manual Configuration (Alternative)

If you prefer to use a config file or need to set a specific project UUID:

```bash
# Set project UUID explicitly
langsmith-fetch config set project-uuid <your-project-uuid>

# Set API key (optional, uses LANGSMITH_API_KEY env var by default)
langsmith-fetch config set api-key lsv2_...

# View your configuration
langsmith-fetch config show
```

**Priority order** (highest to lowest):
1. Config file (`~/.langsmith-cli/config.yaml`)
2. `LANGSMITH_PROJECT_UUID` environment variable
3. `LANGSMITH_PROJECT` environment variable (automatic lookup)

Config file location: `~/.langsmith-cli/config.yaml`

## Usage

### Fetch Recent Threads

**RECOMMENDED: Use directory mode to save each thread to a separate JSON file:**

```bash
# Fetch 10 most recent threads to ./my-threads directory
langsmith-fetch threads ./my-threads --limit 10

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

**Stdout mode (only if you explicitly need it):**

```bash
# Fetch latest thread to stdout
langsmith-fetch threads --format json

# Fetch 5 latest threads to stdout
langsmith-fetch threads --limit 5 --format json
```

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

### Fetch Recent Traces

Perfect for the workflow: "I just did a thing and I want the CLI to just grab the trace(s)."

The `traces` command has two modes:

**DIRECTORY MODE (RECOMMENDED) - Save each trace to a separate JSON file:**

```bash
# Fetch 10 traces to ./my-traces directory
langsmith-fetch traces ./my-traces --limit 10

# Fetch 25 traces with sequential numbering
langsmith-fetch traces ./my-traces --limit 25 --filename-pattern "trace_{index:03d}.json"

# Fetch traces from last hour
langsmith-fetch traces ./my-traces --limit 20 --last-n-minutes 60

# Fetch traces since a specific time
langsmith-fetch traces ./my-traces --limit 10 --since 2025-12-09T10:00:00Z

# Control concurrent fetching (default: 5 workers)
langsmith-fetch traces ./my-traces --limit 20 --max-concurrent 10

# Disable progress bar
langsmith-fetch traces ./my-traces --limit 10 --no-progress
```

**Performance Options:**
- `--max-concurrent INTEGER`: Control concurrent trace fetches (default: 5, max recommended: 10)
- `--no-progress`: Disable progress bar display during fetch
- Timing information is always displayed by default

**File Naming (directory mode):**
- Default: Files named by trace ID (e.g., `3b0b15fe-1e3a-4aef-afa8-48df15879cfe.json`)
- Custom pattern: Use `--filename-pattern` with placeholders:
  - `{trace_id}` - Trace ID (default: `{trace_id}.json`)
  - `{index}` or `{idx}` - Sequential number starting from 1
  - Format specs supported: `{index:03d}` for zero-padded numbers

**STDOUT MODE (only if you explicitly need it):**
Fetch traces and print to stdout or save to a single file.

```bash
# Fetch most recent trace (default: 1 trace, pretty format)
langsmith-fetch traces

# Fetch most recent trace from a specific project
langsmith-fetch traces --project-uuid 80f1ecb3-a16b-411e-97ae-1c89adbb5c49

# Fetch most recent trace from last 30 minutes
langsmith-fetch traces --last-n-minutes 30

# Fetch 5 most recent traces to stdout
langsmith-fetch traces --limit 5 --format json

# Save to single file
langsmith-fetch traces --file latest.json --format raw
```

**Notes:**
- While project UUID is optional, providing it (via config or `--project-uuid`) filters results to a specific project, making searches faster and more targeted.
- Traces are fetched by chronological time (most recent first)
- **Always use directory mode unless you explicitly need stdout output**

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
- All CLI commands (traces, trace, thread, threads, config)
- All output formats (pretty, json, raw)
- Config management and storage
- API fetching and error handling
- Time filtering and SDK integration
- Edge cases and validation

## License

MIT
