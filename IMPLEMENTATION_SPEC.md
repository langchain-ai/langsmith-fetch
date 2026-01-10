# LangSmith-Fetch Extension: Tree Fetching & Public Traces

## Overview

This specification defines new functionality to be added to the `langsmith-fetch` CLI tool to support:
1. **Tree fetching**: Fetch the execution tree skeleton (all runs in a trace with metadata, no inputs/outputs)
2. **Single run fetching**: Fetch full data for a specific run by ID
3. **Public trace support**: Fetch traces from public share URLs without authentication

These features enable iterative, on-demand trace exploration rather than exhaustive upfront fetching.

---

## Current State Analysis

### Existing Codebase Structure
```
src/langsmith_cli/
├── __init__.py
├── __main__.py
├── cli.py           # Click CLI commands
├── config.py        # Auth/config management
├── fetchers.py      # Core fetching logic
└── formatters.py    # Output formatting
```

### Existing Functions to Leverage
- `config.py`: `get_api_key()`, `get_base_url()`, `get_project_uuid()` - reuse for auth
- `fetchers.py`: `_extract_run_metadata_from_sdk_run()` - reuse for metadata extraction
- `fetchers.py`: Request patterns with headers `{"X-API-Key": api_key, "Content-Type": "application/json"}`

### Key Insight: Current Limitation
The existing `fetch_trace()` function fetches only the ROOT run and extracts messages. It does NOT:
- Fetch child runs
- Return the execution tree structure
- Support public (unauthenticated) traces

---

## New Feature 1: Tree Fetching

### Purpose
Fetch ALL runs in a trace with metadata only (no inputs/outputs), enabling the caller to:
1. Understand the full execution structure
2. Identify runs of interest by name, tokens, duration, errors
3. Selectively fetch full data for specific runs later

### API Endpoint
```
POST {base_url}/runs/query
Headers:
  X-API-Key: {api_key}
  Content-Type: application/json

Body:
{
  "trace_id": "{root_trace_id}",
  "select": [
    "id",
    "name",
    "run_type",
    "parent_run_id",
    "child_run_ids",
    "dotted_order",
    "status",
    "error",
    "start_time",
    "end_time",
    "total_tokens",
    "prompt_tokens",
    "completion_tokens",
    "total_cost",
    "prompt_cost",
    "completion_cost",
    "first_token_time",
    "extra"
  ],
  "limit": 1000
}
```

### Response Structure (from LangSmith API)
```json
{
  "runs": [
    {
      "id": "uuid-string",
      "name": "handleEpicChat",
      "run_type": "chain",
      "parent_run_id": null,
      "child_run_ids": ["child-uuid-1", "child-uuid-2"],
      "dotted_order": "20250110T120000000000Z...",
      "status": "success",
      "error": null,
      "start_time": "2025-01-10T12:00:00.000Z",
      "end_time": "2025-01-10T12:03:52.120Z",
      "total_tokens": 705401,
      "prompt_tokens": 650000,
      "completion_tokens": 55401,
      "total_cost": 0.4614,
      "prompt_cost": 0.39,
      "completion_cost": 0.0714,
      "first_token_time": "2025-01-10T12:00:01.500Z",
      "extra": {
        "metadata": {...},
        "runtime": {...}
      }
    },
    // ... more runs (flat list, not nested)
  ],
  "cursors": {...}
}
```

### New Function: `fetch_trace_tree()`

**File**: `src/langsmith_cli/fetchers.py`

**Signature**:
```python
def fetch_trace_tree(
    trace_id: str,
    *,
    base_url: str,
    api_key: str,
    max_runs: int = 1000,
) -> dict[str, Any]:
    """
    Fetch all runs in a trace with metadata only (no inputs/outputs).

    Args:
        trace_id: The root trace UUID (same as root run ID)
        base_url: LangSmith API base URL
        api_key: LangSmith API key
        max_runs: Maximum runs to fetch (default 1000, should cover most traces)

    Returns:
        Dictionary with structure:
        {
            "trace_id": str,
            "total_runs": int,
            "root": {...},           # Root run metadata
            "runs_flat": [...],      # All runs as flat list
            "runs_by_id": {...},     # Runs indexed by ID for quick lookup
            "tree": {...},           # Hierarchical tree structure
            "summary": {
                "total_tokens": int,
                "total_cost": float,
                "total_duration_ms": int,
                "run_types": {"chain": 5, "llm": 3, ...},
                "models_used": ["claude-sonnet-4-...", "grok-..."],
                "has_errors": bool,
                "error_count": int
            }
        }

    Raises:
        requests.HTTPError: If API request fails
        ValueError: If trace_id is invalid or trace not found
    """
```

**Implementation Requirements**:
1. Make POST request to `/runs/query` with `trace_id` filter
2. Handle pagination if `cursors` indicates more results (unlikely for single trace, but handle it)
3. Build the hierarchical tree from flat list using `parent_run_id`
4. Extract model names from `extra.runtime` or `extra.metadata` where available
5. Calculate summary statistics

### New Function: `build_tree_from_runs()`

**File**: `src/langsmith_cli/tree.py` (NEW FILE)

**Signature**:
```python
def build_tree_from_runs(runs: list[dict]) -> dict[str, Any]:
    """
    Reconstruct hierarchical tree from flat list of runs.

    Args:
        runs: Flat list of run dictionaries, each containing 'id' and 'parent_run_id'

    Returns:
        Root node with nested 'children' arrays:
        {
            "id": "root-uuid",
            "name": "handleEpicChat",
            "run_type": "chain",
            "tokens": 705401,
            "cost": 0.4614,
            "duration_ms": 232120,
            "status": "success",
            "error": null,
            "model": null,
            "children": [
                {
                    "id": "child-uuid",
                    "name": "generateEpicResponse",
                    ...
                    "children": [...]
                }
            ]
        }

    Note:
        - Children are sorted by dotted_order (execution order)
        - Each node includes only essential fields for tree display
    """
```

**Implementation Requirements**:
1. Create lookup dict: `{run_id: run_data}`
2. Add empty `children` list to each run
3. Iterate runs, append each to its parent's `children` list
4. Find root (where `parent_run_id` is None)
5. Sort children by `dotted_order` at each level
6. Return root node

### New Function: `extract_run_summary()`

**File**: `src/langsmith_cli/tree.py`

**Signature**:
```python
def extract_run_summary(run: dict) -> dict[str, Any]:
    """
    Extract essential fields from a run for tree display.

    Args:
        run: Full run dictionary from API

    Returns:
        {
            "id": str,
            "name": str,
            "run_type": str,  # "chain", "llm", "tool", "retriever", etc.
            "status": str,    # "success", "error", "pending"
            "error": str | None,
            "tokens": int | None,
            "prompt_tokens": int | None,
            "completion_tokens": int | None,
            "cost": float | None,
            "duration_ms": int | None,
            "model": str | None,  # Extracted from extra.runtime or extra.metadata
            "has_children": bool,
            "child_count": int
        }
    """
```

### CLI Command: `tree`

**File**: `src/langsmith_cli/cli.py`

**Command Specification**:
```
langsmith-fetch tree <TRACE_ID> [OPTIONS]

Arguments:
  TRACE_ID    LangSmith trace UUID or root run ID

Options:
  --output-dir PATH     Save tree.json to directory (creates if not exists)
  --format [json|pretty|summary]
                        Output format (default: pretty)
                        - json: Full tree as JSON
                        - pretty: Rich formatted tree view
                        - summary: Compact summary only
  --file PATH           Save output to specific file (stdout mode only)
  --max-depth INT       Limit tree depth in output (default: unlimited)
  --show-ids            Include run IDs in pretty output
  --help                Show this message and exit

Examples:
  # View tree structure
  langsmith-fetch tree 3b0b15fe-1e3a-4aef-afa8-48df15879cfe

  # Save to directory
  langsmith-fetch tree 3b0b15fe-... --output-dir ./trace-data/

  # Get summary only
  langsmith-fetch tree 3b0b15fe-... --format summary
```

**Output Directory Structure** (when using `--output-dir`):
```
{output-dir}/
├── tree.json           # Full tree structure
├── summary.json        # Summary statistics
├── runs/               # Empty initially, populated by `run` command
│   └── .gitkeep
└── NAVIGATION.md       # Instructions for exploring the trace
```

**tree.json Schema**:
```json
{
  "trace_id": "uuid",
  "fetched_at": "2025-01-10T12:00:00Z",
  "total_runs": 47,
  "summary": {
    "total_tokens": 705401,
    "total_cost": 0.4614,
    "total_duration_ms": 232120,
    "run_types": {"chain": 30, "llm": 8, "tool": 9},
    "models_used": ["claude-sonnet-4-20250514", "grok-4-1-fast-non-reasoning"],
    "has_errors": false,
    "error_count": 0
  },
  "tree": {
    "id": "root-uuid",
    "name": "handleEpicChat",
    "run_type": "chain",
    "status": "success",
    "tokens": 705401,
    "cost": 0.4614,
    "duration_ms": 232120,
    "children": [...]
  },
  "runs_by_id": {
    "root-uuid": {...},
    "child-uuid": {...}
  }
}
```

**NAVIGATION.md Template**:
```markdown
# Trace Navigation Guide

## Trace: {trace_id}
Fetched: {timestamp}

## Summary
- Total runs: {total_runs}
- Total tokens: {total_tokens}
- Total cost: ${total_cost}
- Duration: {duration}s
- Models: {models_list}

## Tree Structure
{ascii_tree_representation}

## How to Explore

### View full data for a specific run:
```
langsmith-fetch run <run-id> --output-dir {output-dir}
```

### Key runs to investigate:
{list_of_notable_runs_by_tokens_or_errors}

## Files
- `tree.json` - Full tree structure with all run metadata
- `summary.json` - Quick statistics
- `runs/` - Directory for fetched run data (initially empty)
```

---

## New Feature 2: Single Run Fetching

### Purpose
Fetch complete data (inputs, outputs, metadata) for a single run by ID.

### API Endpoint
```
GET {base_url}/runs/{run_id}
Headers:
  X-API-Key: {api_key}
  Content-Type: application/json
```

### Response Structure
```json
{
  "id": "run-uuid",
  "name": "createStreamChat",
  "run_type": "llm",
  "inputs": {
    "messages": [...],
    "model": "claude-sonnet-4-...",
    "temperature": 0.7,
    ...
  },
  "outputs": {
    "generations": [...],
    "llm_output": {...}
  },
  "error": null,
  "start_time": "...",
  "end_time": "...",
  "extra": {...},
  "events": [...],
  "tags": [...],
  ...
}
```

### New Function: `fetch_run()`

**File**: `src/langsmith_cli/fetchers.py`

**Signature**:
```python
def fetch_run(
    run_id: str,
    *,
    base_url: str,
    api_key: str,
    include_events: bool = False,
) -> dict[str, Any]:
    """
    Fetch complete data for a single run.

    Args:
        run_id: The run UUID
        base_url: LangSmith API base URL
        api_key: LangSmith API key
        include_events: Whether to include streaming events (can be large)

    Returns:
        Complete run data including inputs and outputs:
        {
            "id": str,
            "name": str,
            "run_type": str,
            "status": str,
            "error": str | None,
            "inputs": dict,       # Full input data
            "outputs": dict,      # Full output data
            "metadata": {...},    # Extracted metadata (tokens, cost, timing)
            "events": [...] | None,
            "tags": [...]
        }

    Raises:
        requests.HTTPError: If API request fails (404 if run not found)
    """
```

### CLI Command: `run`

**Command Specification**:
```
langsmith-fetch run <RUN_ID> [OPTIONS]

Arguments:
  RUN_ID    LangSmith run UUID

Options:
  --output-dir PATH     Save to trace directory structure
                        (saves to {output-dir}/runs/{run-id}/)
  --format [json|pretty|raw]
                        Output format (default: pretty)
  --file PATH           Save to specific file
  --include-events      Include streaming events (can be large)
  --extract FIELD       Extract and display specific field only
                        (e.g., --extract inputs.messages)
  --help                Show this message and exit

Examples:
  # View run data
  langsmith-fetch run abc123-def456

  # Save to trace directory
  langsmith-fetch run abc123 --output-dir ./trace-data/

  # Extract specific field
  langsmith-fetch run abc123 --extract inputs.messages --format json
```

**Output Directory Structure** (when using `--output-dir`):
```
{output-dir}/runs/{run-id}/
├── run.json            # Full run data
├── inputs.json         # Just inputs (for large traces)
├── outputs.json        # Just outputs (for large traces)
└── metadata.json       # Extracted metadata
```

---

## New Feature 3: Public Trace Support

### Purpose
Fetch traces from public share URLs without requiring authentication.

### Public URL Formats
```
# Format 1: Public share URL
https://smith.langchain.com/public/{trace_id}/r

# Format 2: Public share with org
https://smith.langchain.com/public/{org_slug}/{trace_id}/r

# Format 3: Direct public link
https://smith.langchain.com/o/{org_id}/projects/p/{project_id}/r/{run_id}?share=true
```

### API Endpoint (Public)
```
GET https://api.smith.langchain.com/public/{org_id_or_slug}/runs/{trace_id}
# No authentication required
```

**Note**: The exact public API endpoint needs verification. Alternative approach:
```
GET https://api.smith.langchain.com/runs/{trace_id}/share
# May return public data without auth if trace is shared
```

### New Function: `parse_langsmith_url()`

**File**: `src/langsmith_cli/public.py` (NEW FILE)

**Signature**:
```python
def parse_langsmith_url(url: str) -> dict[str, Any]:
    """
    Parse a LangSmith URL and extract trace identification.

    Args:
        url: Any LangSmith trace URL (public or authenticated)

    Returns:
        {
            "trace_id": str,
            "is_public": bool,
            "org_slug": str | None,
            "project_id": str | None,
            "url_type": "public_share" | "project_trace" | "direct_run"
        }

    Raises:
        ValueError: If URL format is not recognized

    Examples:
        >>> parse_langsmith_url("https://smith.langchain.com/public/abc123/r")
        {"trace_id": "abc123", "is_public": True, "org_slug": None, ...}

        >>> parse_langsmith_url("https://smith.langchain.com/public/myorg/abc123/r")
        {"trace_id": "abc123", "is_public": True, "org_slug": "myorg", ...}
    """
```

### New Function: `fetch_public_trace_tree()`

**File**: `src/langsmith_cli/public.py`

**Signature**:
```python
def fetch_public_trace_tree(
    url_or_trace_id: str,
    *,
    base_url: str = "https://api.smith.langchain.com",
) -> dict[str, Any]:
    """
    Fetch trace tree from a public share URL (no auth required).

    Args:
        url_or_trace_id: Public URL or trace ID
        base_url: API base URL (default: production LangSmith)

    Returns:
        Same structure as fetch_trace_tree()

    Raises:
        ValueError: If trace is not publicly shared
        requests.HTTPError: If API request fails
    """
```

### CLI Integration

Modify `tree` and `run` commands to auto-detect public URLs:

```python
@cli.command()
@click.argument("trace_id_or_url")
def tree(trace_id_or_url: str, ...):
    # Auto-detect if input is a public URL
    if trace_id_or_url.startswith("http"):
        parsed = parse_langsmith_url(trace_id_or_url)
        if parsed["is_public"]:
            result = fetch_public_trace_tree(trace_id_or_url)
        else:
            # Authenticated URL, extract trace_id and use normal fetch
            result = fetch_trace_tree(parsed["trace_id"], ...)
    else:
        # Direct trace ID, use authenticated fetch
        result = fetch_trace_tree(trace_id_or_url, ...)
```

---

## Testing Requirements

### Unit Tests

**File**: `tests/test_tree.py` (NEW FILE)

```python
def test_build_tree_from_runs_simple():
    """Test tree building with simple parent-child relationship."""

def test_build_tree_from_runs_deep_nesting():
    """Test tree building with 5+ levels of nesting."""

def test_build_tree_from_runs_multiple_children():
    """Test tree building where parent has multiple children."""

def test_build_tree_from_runs_preserves_order():
    """Test that children are sorted by dotted_order."""

def test_extract_run_summary_llm_run():
    """Test metadata extraction for LLM run type."""

def test_extract_run_summary_chain_run():
    """Test metadata extraction for chain run type."""

def test_extract_run_summary_with_error():
    """Test metadata extraction when run has error."""
```

**File**: `tests/test_public.py` (NEW FILE)

```python
def test_parse_langsmith_url_public_simple():
    """Test parsing simple public URL."""

def test_parse_langsmith_url_public_with_org():
    """Test parsing public URL with org slug."""

def test_parse_langsmith_url_project_trace():
    """Test parsing authenticated project URL."""

def test_parse_langsmith_url_invalid():
    """Test that invalid URLs raise ValueError."""
```

**File**: `tests/test_fetchers.py` (EXTEND)

```python
def test_fetch_trace_tree_success(mock_api):
    """Test successful tree fetch with mocked API."""

def test_fetch_trace_tree_pagination(mock_api):
    """Test tree fetch handles pagination correctly."""

def test_fetch_run_success(mock_api):
    """Test successful single run fetch."""

def test_fetch_run_not_found(mock_api):
    """Test 404 handling for non-existent run."""
```

### Integration Tests

```python
@pytest.mark.integration
def test_tree_command_real_api():
    """Test tree command against real LangSmith API."""
    # Requires LANGSMITH_TEST_TRACE_ID env var

@pytest.mark.integration
def test_run_command_real_api():
    """Test run command against real LangSmith API."""
    # Requires LANGSMITH_TEST_RUN_ID env var
```

### Test Data Fixtures

Create `tests/fixtures/` with:
- `sample_runs_flat.json` - Example API response for /runs/query
- `sample_run_full.json` - Example API response for /runs/{id}
- `expected_tree.json` - Expected tree structure after building

---

## Error Handling

### Error Cases to Handle

| Scenario | Error Type | User Message |
|----------|-----------|--------------|
| Invalid trace ID format | ValueError | "Invalid trace ID format. Expected UUID." |
| Trace not found | HTTPError 404 | "Trace not found. Verify the trace ID exists." |
| Unauthorized (bad API key) | HTTPError 401 | "Authentication failed. Check your API key." |
| Rate limited | HTTPError 429 | "Rate limited. Retry after {seconds} seconds." |
| Public trace not shared | HTTPError 403 | "Trace is not publicly shared." |
| Network error | RequestException | "Network error: {details}" |
| Invalid URL format | ValueError | "Unrecognized LangSmith URL format." |

### Error Response Format

```python
class LangSmithFetchError(Exception):
    """Base exception for langsmith-fetch errors."""
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

class TraceNotFoundError(LangSmithFetchError):
    """Trace ID not found."""

class AuthenticationError(LangSmithFetchError):
    """API key invalid or missing."""

class PublicAccessDeniedError(LangSmithFetchError):
    """Trace is not publicly accessible."""
```

---

## Implementation Order

### Phase 1: Core Tree Fetching
1. Add `fetch_trace_tree()` to `fetchers.py`
2. Create `tree.py` with `build_tree_from_runs()` and `extract_run_summary()`
3. Add `tree` CLI command
4. Write unit tests for tree building

### Phase 2: Single Run Fetching
1. Add `fetch_run()` to `fetchers.py`
2. Add `run` CLI command
3. Write unit tests

### Phase 3: Public Trace Support
1. Create `public.py` with URL parsing and public fetching
2. Integrate public detection into `tree` and `run` commands
3. Write unit tests for URL parsing

### Phase 4: Output Formatting
1. Add `NAVIGATION.md` generation
2. Add pretty tree formatting with Rich
3. Add `--extract` functionality for field extraction

### Phase 5: Integration Testing
1. Test against real LangSmith API
2. Test with various trace sizes (small, medium, large)
3. Test public URL scenarios

---

## Dependencies

### Existing (no changes needed)
- `requests` - HTTP client
- `rich` - Terminal formatting
- `click` - CLI framework
- `langsmith` - SDK (optional, for some operations)

### New (if needed)
- None expected

---

## Acceptance Criteria

### Feature: Tree Fetching
- [ ] `langsmith-fetch tree <trace-id>` returns hierarchical tree structure
- [ ] Tree includes all runs with metadata (tokens, cost, duration, status)
- [ ] Tree is sorted by execution order
- [ ] `--output-dir` saves tree.json, summary.json, and NAVIGATION.md
- [ ] `--format pretty` shows Rich-formatted tree in terminal
- [ ] Handles traces with 100+ runs without timeout

### Feature: Single Run Fetching
- [ ] `langsmith-fetch run <run-id>` returns full run data
- [ ] `--output-dir` saves to `runs/{run-id}/` subdirectory
- [ ] `--extract` allows extracting specific fields
- [ ] Large inputs/outputs (2MB+) are handled gracefully

### Feature: Public Traces
- [ ] Public URLs are auto-detected and fetched without auth
- [ ] All public URL formats are supported
- [ ] Clear error message when trace is not publicly shared

### General
- [ ] All new code has unit tests with >80% coverage
- [ ] CLI help text is clear and includes examples
- [ ] Error messages are actionable
- [ ] No breaking changes to existing commands

---

## Open Questions (For Implementer to Verify)

1. **Public API endpoint**: Verify exact endpoint for public traces. May need to inspect network requests on smith.langchain.com.

2. **Pagination**: Does `/runs/query` with `trace_id` filter ever paginate for large traces? Test with trace having 200+ runs.

3. **Model extraction**: Where exactly is model name stored? Check `extra.runtime.model`, `extra.metadata.ls_model_name`, and `extra.invocation_params.model`.

4. **Rate limits**: What are the rate limits for `/runs/query`? May need to add retry logic.

---

## File Changes Summary

### New Files
- `src/langsmith_cli/tree.py` - Tree building utilities
- `src/langsmith_cli/public.py` - Public trace support
- `tests/test_tree.py` - Tree building tests
- `tests/test_public.py` - Public URL parsing tests
- `tests/fixtures/sample_runs_flat.json` - Test fixture
- `tests/fixtures/sample_run_full.json` - Test fixture
- `tests/fixtures/expected_tree.json` - Test fixture

### Modified Files
- `src/langsmith_cli/fetchers.py` - Add `fetch_trace_tree()`, `fetch_run()`
- `src/langsmith_cli/cli.py` - Add `tree`, `run` commands
- `tests/test_fetchers.py` - Add tests for new functions
