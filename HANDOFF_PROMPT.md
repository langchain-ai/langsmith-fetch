# Implementation Handoff: LangSmith-Fetch Tree Extension

## Your Mission

You are implementing new features for the `langsmith-fetch` CLI tool. The codebase is at `/Users/amiteshwar/repositories/langsmith-fetch/`.

**Read the full specification first**: `/Users/amiteshwar/repositories/langsmith-fetch/IMPLEMENTATION_SPEC.md`

## Context

`langsmith-fetch` is a CLI tool for fetching LangSmith trace data. Currently it only fetches "messages" from traces. We're extending it to support:

1. **Tree fetching**: Get the full execution tree skeleton (all nested runs with metadata, but NOT inputs/outputs)
2. **Single run fetching**: Get complete data for one specific run
3. **Public trace support**: Fetch from public share URLs without authentication

This enables iterative trace exploration: fetch the skeleton first, identify interesting runs, then selectively fetch full data for specific runs.

## Implementation Order

Follow this sequence:

### Step 1: Understand the Codebase
- Read `src/langsmith_cli/fetchers.py` to understand existing fetch patterns
- Read `src/langsmith_cli/cli.py` to understand the Click command structure
- Read `src/langsmith_cli/config.py` to understand auth handling
- Run existing tests: `cd /Users/amiteshwar/repositories/langsmith-fetch && uv run pytest`

### Step 2: Implement Tree Building Utilities
Create `src/langsmith_cli/tree.py` with:
- `build_tree_from_runs(runs: list[dict]) -> dict` - Reconstruct hierarchy from flat list
- `extract_run_summary(run: dict) -> dict` - Extract essential fields for tree display
- `generate_navigation_md(tree_data: dict) -> str` - Generate NAVIGATION.md content

### Step 3: Implement Tree Fetching
Add to `src/langsmith_cli/fetchers.py`:
- `fetch_trace_tree(trace_id, *, base_url, api_key, max_runs=1000) -> dict`

This should:
1. POST to `/runs/query` with `{"trace_id": trace_id, "select": [...], "limit": max_runs}`
2. Handle pagination if needed (check for `cursors` in response)
3. Call `build_tree_from_runs()` to construct hierarchy
4. Return structured result with tree, summary, and runs_by_id

### Step 4: Add Tree CLI Command
Add to `src/langsmith_cli/cli.py`:
```python
@cli.command()
@click.argument("trace_id")
@click.option("--output-dir", type=click.Path(), help="Save to directory")
@click.option("--format", type=click.Choice(["json", "pretty", "summary"]), default="pretty")
def tree(trace_id: str, output_dir: str | None, format: str):
    """Fetch trace execution tree (skeleton only, no inputs/outputs)."""
```

### Step 5: Implement Single Run Fetching
Add to `src/langsmith_cli/fetchers.py`:
- `fetch_run(run_id, *, base_url, api_key) -> dict`

Add CLI command:
```python
@cli.command()
@click.argument("run_id")
@click.option("--output-dir", type=click.Path())
@click.option("--extract", help="Extract specific field (e.g., inputs.messages)")
def run(run_id: str, output_dir: str | None, extract: str | None):
    """Fetch complete data for a single run."""
```

### Step 6: Implement Public Trace Support
Create `src/langsmith_cli/public.py` with:
- `parse_langsmith_url(url: str) -> dict` - Parse URL, detect if public
- `fetch_public_trace_tree(url_or_id, *, base_url) -> dict` - Fetch without auth

Integrate into `tree` and `run` commands to auto-detect public URLs.

### Step 7: Write Tests
Create tests in:
- `tests/test_tree.py` - Tree building logic
- `tests/test_public.py` - URL parsing

Extend `tests/test_fetchers.py` for new functions.

### Step 8: Integration Testing
Test against real LangSmith API if you have access (check if LANGSMITH_API_KEY is set).

## Key Technical Details

### API Endpoint for Tree Fetching
```
POST https://api.smith.langchain.com/runs/query
Headers: {"X-API-Key": "...", "Content-Type": "application/json"}
Body: {
  "trace_id": "...",
  "select": ["id", "name", "run_type", "parent_run_id", "child_run_ids",
             "dotted_order", "status", "error", "start_time", "end_time",
             "total_tokens", "prompt_tokens", "completion_tokens",
             "total_cost", "extra"],
  "limit": 1000
}
```

### Tree Building Algorithm
```python
def build_tree_from_runs(runs):
    by_id = {r["id"]: {**r, "children": []} for r in runs}
    root = None
    for run in runs:
        parent_id = run.get("parent_run_id")
        if parent_id is None:
            root = by_id[run["id"]]
        elif parent_id in by_id:
            by_id[parent_id]["children"].append(by_id[run["id"]])
    # Sort children by dotted_order at each level
    def sort_children(node):
        node["children"].sort(key=lambda x: x.get("dotted_order", ""))
        for child in node["children"]:
            sort_children(child)
    if root:
        sort_children(root)
    return root
```

### Model Name Extraction
Check these locations in order:
1. `extra.metadata.ls_model_name`
2. `extra.runtime.model`
3. `extra.invocation_params.model`
4. `extra.invocation_params.model_name`

### Output Directory Structure
```
{output-dir}/
├── tree.json           # Full tree with runs_by_id
├── summary.json        # Just statistics
├── NAVIGATION.md       # Human-readable guide
└── runs/               # For individual run data
    └── {run-id}/
        ├── run.json
        ├── inputs.json
        └── outputs.json
```

## Testing Commands

```bash
cd /Users/amiteshwar/repositories/langsmith-fetch

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_tree.py -v

# Run with coverage
uv run pytest --cov=langsmith_cli

# Test CLI manually (requires API key)
export LANGSMITH_API_KEY="lsv2_..."
uv run langsmith-fetch tree <some-trace-id>
uv run langsmith-fetch run <some-run-id>
```

## Definition of Done

- [ ] `langsmith-fetch tree <id>` works and shows hierarchical structure
- [ ] `langsmith-fetch tree <id> --output-dir ./out` creates tree.json, summary.json, NAVIGATION.md
- [ ] `langsmith-fetch run <id>` fetches full run data
- [ ] `langsmith-fetch run <id> --output-dir ./out` saves to runs/{id}/
- [ ] Public URLs auto-detected: `langsmith-fetch tree https://smith.langchain.com/public/...`
- [ ] All tests pass: `uv run pytest`
- [ ] No type errors: `uv run pyright` or `uv run mypy src/`

## Questions You May Need to Resolve

1. **Public API endpoint**: The exact endpoint for public traces may need verification. Try inspecting network requests on smith.langchain.com when viewing a public trace.

2. **Pagination behavior**: Test if traces with many runs (100+) paginate. The response may include a `cursors` object.

3. **Model name location**: Different run types store model names in different places. Test with actual LLM runs.

## Files to Create/Modify

### Create
- `src/langsmith_cli/tree.py`
- `src/langsmith_cli/public.py`
- `tests/test_tree.py`
- `tests/test_public.py`
- `tests/fixtures/sample_runs_flat.json`

### Modify
- `src/langsmith_cli/fetchers.py` - Add `fetch_trace_tree()`, `fetch_run()`
- `src/langsmith_cli/cli.py` - Add `tree`, `run` commands
- `tests/test_fetchers.py` - Add tests for new functions

## Start Here

1. Read `IMPLEMENTATION_SPEC.md` thoroughly
2. Read existing code in `src/langsmith_cli/`
3. Run existing tests to ensure baseline works
4. Begin with Step 2 (tree.py utilities) as it has no dependencies
5. Work through steps sequentially, testing each before moving on

Good luck!
