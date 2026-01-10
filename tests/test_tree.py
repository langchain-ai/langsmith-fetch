"""Tests for tree module."""

import json
from pathlib import Path

import pytest

from langsmith_cli.tree import (
    build_tree_from_runs,
    calculate_tree_summary,
    extract_model_name,
    extract_run_summary,
    format_tree_pretty,
    generate_navigation_md,
)


@pytest.fixture
def sample_runs():
    """Load sample runs from fixture file."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_runs_flat.json"
    with open(fixture_path) as f:
        data = json.load(f)
    return data["runs"]


@pytest.fixture
def single_run():
    """A single run for testing extract functions."""
    return {
        "id": "test-run-123",
        "name": "testRun",
        "run_type": "llm",
        "parent_run_id": None,
        "child_run_ids": ["child-1", "child-2"],
        "dotted_order": "20250110T120000000000Z",
        "status": "success",
        "error": None,
        "start_time": "2025-01-10T12:00:00.000Z",
        "end_time": "2025-01-10T12:01:00.000Z",
        "total_tokens": 1000,
        "prompt_tokens": 800,
        "completion_tokens": 200,
        "total_cost": 0.01,
        "prompt_cost": 0.008,
        "completion_cost": 0.002,
        "first_token_time": "2025-01-10T12:00:01.000Z",
        "extra": {
            "metadata": {"ls_model_name": "claude-sonnet-4"},
            "runtime": {"model": "claude-sonnet-4-backup"},
            "invocation_params": {"model": "claude-fallback"},
        },
    }


class TestBuildTreeFromRuns:
    """Tests for build_tree_from_runs function."""

    def test_build_tree_from_runs_simple(self, sample_runs):
        """Test tree building with simple parent-child relationship."""
        tree = build_tree_from_runs(sample_runs)

        assert tree is not None
        assert tree["id"] == "root-uuid-1234"
        assert tree["name"] == "handleEpicChat"
        assert "children" in tree

    def test_build_tree_from_runs_hierarchy(self, sample_runs):
        """Test that tree hierarchy is correctly built."""
        tree = build_tree_from_runs(sample_runs)

        # Root should have 2 children
        assert len(tree["children"]) == 2

        # Find the child that has grandchildren
        chain_child = next(c for c in tree["children"] if c["name"] == "generateEpicResponse")
        assert len(chain_child["children"]) == 1
        assert chain_child["children"][0]["name"] == "createStreamChat"

    def test_build_tree_from_runs_preserves_order(self, sample_runs):
        """Test that children are sorted by dotted_order."""
        tree = build_tree_from_runs(sample_runs)

        # Children should be in dotted_order order
        children = tree["children"]
        for i in range(len(children) - 1):
            assert children[i]["dotted_order"] < children[i + 1]["dotted_order"]

    def test_build_tree_from_runs_empty_list(self):
        """Test tree building with empty list."""
        tree = build_tree_from_runs([])
        assert tree is None

    def test_build_tree_from_runs_single_run(self):
        """Test tree building with single run."""
        runs = [{
            "id": "single-run",
            "name": "singleRun",
            "run_type": "chain",
            "parent_run_id": None,
            "child_run_ids": [],
            "status": "success",
        }]
        tree = build_tree_from_runs(runs)

        assert tree is not None
        assert tree["id"] == "single-run"
        assert tree["children"] == []

    def test_build_tree_from_runs_deep_nesting(self):
        """Test tree building with 5+ levels of nesting."""
        runs = []
        parent_id = None
        for i in range(6):
            run_id = f"level-{i}"
            runs.append({
                "id": run_id,
                "name": f"level{i}",
                "run_type": "chain",
                "parent_run_id": parent_id,
                "child_run_ids": [f"level-{i+1}"] if i < 5 else [],
                "dotted_order": ".".join(["1"] * (i + 1)),
                "status": "success",
            })
            parent_id = run_id

        tree = build_tree_from_runs(runs)

        # Traverse to verify depth
        current = tree
        depth = 0
        while current:
            depth += 1
            if current["children"]:
                current = current["children"][0]
            else:
                break

        assert depth == 6

    def test_build_tree_from_runs_multiple_children(self):
        """Test tree building where parent has multiple children."""
        runs = [
            {
                "id": "parent",
                "name": "parent",
                "run_type": "chain",
                "parent_run_id": None,
                "child_run_ids": ["c1", "c2", "c3", "c4"],
                "dotted_order": "1",
                "status": "success",
            },
            {"id": "c1", "name": "child1", "run_type": "llm", "parent_run_id": "parent", "child_run_ids": [], "dotted_order": "1.1", "status": "success"},
            {"id": "c2", "name": "child2", "run_type": "llm", "parent_run_id": "parent", "child_run_ids": [], "dotted_order": "1.2", "status": "success"},
            {"id": "c3", "name": "child3", "run_type": "tool", "parent_run_id": "parent", "child_run_ids": [], "dotted_order": "1.3", "status": "success"},
            {"id": "c4", "name": "child4", "run_type": "retriever", "parent_run_id": "parent", "child_run_ids": [], "dotted_order": "1.4", "status": "success"},
        ]

        tree = build_tree_from_runs(runs)
        assert len(tree["children"]) == 4


class TestExtractRunSummary:
    """Tests for extract_run_summary function."""

    def test_extract_run_summary_llm_run(self, single_run):
        """Test metadata extraction for LLM run type."""
        summary = extract_run_summary(single_run)

        assert summary["id"] == "test-run-123"
        assert summary["name"] == "testRun"
        assert summary["run_type"] == "llm"
        assert summary["status"] == "success"
        assert summary["tokens"] == 1000
        assert summary["prompt_tokens"] == 800
        assert summary["completion_tokens"] == 200
        assert summary["cost"] == 0.01
        assert summary["model"] == "claude-sonnet-4"  # From ls_model_name
        assert summary["has_children"] is True
        assert summary["child_count"] == 2

    def test_extract_run_summary_chain_run(self):
        """Test metadata extraction for chain run type."""
        run = {
            "id": "chain-run",
            "name": "myChain",
            "run_type": "chain",
            "parent_run_id": None,
            "child_run_ids": [],
            "status": "success",
            "error": None,
            "start_time": "2025-01-10T12:00:00.000Z",
            "end_time": "2025-01-10T12:00:30.000Z",
            "total_tokens": 500,
            "total_cost": 0.005,
            "extra": {},
        }
        summary = extract_run_summary(run)

        assert summary["run_type"] == "chain"
        assert summary["duration_ms"] == 30000  # 30 seconds
        assert summary["model"] is None  # No model for chain
        assert summary["has_children"] is False

    def test_extract_run_summary_with_error(self):
        """Test metadata extraction when run has error."""
        run = {
            "id": "error-run",
            "name": "failedRun",
            "run_type": "llm",
            "parent_run_id": None,
            "child_run_ids": [],
            "status": "error",
            "error": "Model rate limit exceeded",
            "start_time": "2025-01-10T12:00:00.000Z",
            "end_time": "2025-01-10T12:00:05.000Z",
            "extra": {},
        }
        summary = extract_run_summary(run)

        assert summary["status"] == "error"
        assert summary["error"] == "Model rate limit exceeded"

    def test_extract_run_summary_duration_calculation(self):
        """Test duration is correctly calculated from timestamps."""
        run = {
            "id": "test",
            "name": "test",
            "run_type": "llm",
            "parent_run_id": None,
            "child_run_ids": [],
            "status": "success",
            "start_time": "2025-01-10T12:00:00.000Z",
            "end_time": "2025-01-10T12:05:30.500Z",  # 5 min 30.5 sec later
            "extra": {},
        }
        summary = extract_run_summary(run)

        # 5*60 + 30.5 = 330.5 seconds = 330500 ms
        assert summary["duration_ms"] == 330500


class TestExtractModelName:
    """Tests for extract_model_name function."""

    def test_extract_from_ls_model_name(self):
        """Test model extraction from extra.metadata.ls_model_name."""
        run = {
            "extra": {
                "metadata": {"ls_model_name": "claude-sonnet-4"},
                "runtime": {"model": "should-not-use"},
            }
        }
        assert extract_model_name(run) == "claude-sonnet-4"

    def test_extract_from_runtime_model(self):
        """Test model extraction from extra.runtime.model."""
        run = {
            "extra": {
                "metadata": {},
                "runtime": {"model": "gpt-4o"},
            }
        }
        assert extract_model_name(run) == "gpt-4o"

    def test_extract_from_invocation_params_model(self):
        """Test model extraction from extra.invocation_params.model."""
        run = {
            "extra": {
                "invocation_params": {"model": "claude-3-opus"}
            }
        }
        assert extract_model_name(run) == "claude-3-opus"

    def test_extract_from_invocation_params_model_name(self):
        """Test model extraction from extra.invocation_params.model_name."""
        run = {
            "extra": {
                "invocation_params": {"model_name": "llama-3"}
            }
        }
        assert extract_model_name(run) == "llama-3"

    def test_extract_no_model_found(self):
        """Test when no model is found."""
        run = {"extra": {}}
        assert extract_model_name(run) is None

    def test_extract_empty_extra(self):
        """Test when extra is None or missing."""
        assert extract_model_name({}) is None
        assert extract_model_name({"extra": None}) is None


class TestCalculateTreeSummary:
    """Tests for calculate_tree_summary function."""

    def test_calculate_summary(self, sample_runs):
        """Test summary calculation."""
        summary = calculate_tree_summary(sample_runs)

        assert summary["total_runs"] == 4
        assert summary["total_tokens"] > 0
        assert summary["total_cost"] > 0
        assert summary["has_errors"] is False
        assert summary["error_count"] == 0
        assert "chain" in summary["run_types"]
        assert "llm" in summary["run_types"]
        assert "tool" in summary["run_types"]
        assert len(summary["models_used"]) > 0

    def test_calculate_summary_with_errors(self):
        """Test summary calculation with errors."""
        runs = [
            {
                "id": "r1",
                "name": "run1",
                "run_type": "llm",
                "parent_run_id": None,
                "status": "error",
                "error": "Error 1",
                "total_tokens": 100,
                "total_cost": 0.01,
                "extra": {},
            },
            {
                "id": "r2",
                "name": "run2",
                "run_type": "llm",
                "parent_run_id": None,
                "status": "error",
                "error": "Error 2",
                "total_tokens": 200,
                "total_cost": 0.02,
                "extra": {},
            },
        ]
        summary = calculate_tree_summary(runs)

        assert summary["has_errors"] is True
        assert summary["error_count"] == 2
        assert len(summary["error_runs"]) == 2


class TestFormatTreePretty:
    """Tests for format_tree_pretty function."""

    def test_format_tree_pretty_basic(self, sample_runs):
        """Test basic pretty formatting."""
        tree = build_tree_from_runs(sample_runs)
        summary = calculate_tree_summary(sample_runs)

        formatted = format_tree_pretty(tree, summary)

        assert "TRACE SUMMARY" in formatted
        assert "EXECUTION TREE" in formatted
        assert "handleEpicChat" in formatted
        assert "generateEpicResponse" in formatted

    def test_format_tree_pretty_with_ids(self, sample_runs):
        """Test pretty formatting with IDs shown."""
        tree = build_tree_from_runs(sample_runs)
        summary = calculate_tree_summary(sample_runs)

        formatted = format_tree_pretty(tree, summary, show_ids=True)

        assert "id:root-uuid-1234" in formatted

    def test_format_tree_pretty_max_depth(self, sample_runs):
        """Test pretty formatting with max depth."""
        tree = build_tree_from_runs(sample_runs)
        summary = calculate_tree_summary(sample_runs)

        formatted = format_tree_pretty(tree, summary, max_depth=1)

        # Should show root and immediate children, but truncate grandchildren
        assert "handleEpicChat" in formatted
        # May show truncation indicator for deeper levels


class TestGenerateNavigationMd:
    """Tests for generate_navigation_md function."""

    def test_generate_navigation_md(self, sample_runs):
        """Test NAVIGATION.md generation."""
        tree = build_tree_from_runs(sample_runs)
        summary = calculate_tree_summary(sample_runs)

        md = generate_navigation_md(
            trace_id="test-trace-123",
            tree=tree,
            summary=summary,
            output_dir="./trace-data",
            fetched_at="2025-01-10T12:00:00Z",
        )

        assert "# Trace Navigation Guide" in md
        assert "test-trace-123" in md
        assert "Total runs:" in md
        assert "langsmith-fetch run" in md
        assert "tree.json" in md
        assert "summary.json" in md

    def test_generate_navigation_md_with_errors(self):
        """Test NAVIGATION.md generation with errors."""
        runs = [
            {
                "id": "err-run",
                "name": "errorRun",
                "run_type": "llm",
                "parent_run_id": None,
                "child_run_ids": [],
                "status": "error",
                "error": "Test error",
                "extra": {},
            }
        ]
        tree = build_tree_from_runs(runs)
        summary = calculate_tree_summary(runs)

        md = generate_navigation_md(
            trace_id="error-trace",
            tree=tree,
            summary=summary,
            output_dir="./out",
            fetched_at="2025-01-10T12:00:00Z",
        )

        assert "Errors:" in md
        assert "Runs with errors:" in md
        assert "err-run" in md


class TestTreeEdgeCases:
    """Edge case tests for tree building functions."""

    def test_build_tree_orphaned_nodes(self):
        """Test tree building with orphaned nodes (parent doesn't exist)."""
        runs = [
            {
                "id": "root",
                "name": "rootRun",
                "run_type": "chain",
                "parent_run_id": None,
                "child_run_ids": [],
                "dotted_order": "1",
                "status": "success",
            },
            {
                "id": "orphan",
                "name": "orphanRun",
                "run_type": "llm",
                "parent_run_id": "nonexistent-parent",  # Parent doesn't exist
                "child_run_ids": [],
                "dotted_order": "2",
                "status": "success",
            },
        ]
        tree = build_tree_from_runs(runs)

        # Should still build tree with root node
        assert tree is not None
        assert tree["id"] == "root"
        # Orphan node has no parent that exists, so it won't be in root's children
        assert len(tree["children"]) == 0

    def test_build_tree_missing_dotted_order(self):
        """Test tree building with missing dotted_order."""
        runs = [
            {
                "id": "root",
                "name": "rootRun",
                "run_type": "chain",
                "parent_run_id": None,
                "child_run_ids": ["child1", "child2"],
                "status": "success",
                # No dotted_order
            },
            {
                "id": "child1",
                "name": "child1Run",
                "run_type": "llm",
                "parent_run_id": "root",
                "child_run_ids": [],
                "status": "success",
                # No dotted_order
            },
            {
                "id": "child2",
                "name": "child2Run",
                "run_type": "llm",
                "parent_run_id": "root",
                "child_run_ids": [],
                "status": "success",
                # No dotted_order
            },
        ]
        tree = build_tree_from_runs(runs)

        assert tree is not None
        assert len(tree["children"]) == 2

    def test_build_tree_multiple_roots(self):
        """Test tree building with multiple root nodes (no parent)."""
        runs = [
            {
                "id": "root1",
                "name": "root1Run",
                "run_type": "chain",
                "parent_run_id": None,
                "child_run_ids": [],
                "dotted_order": "1",
                "status": "success",
            },
            {
                "id": "root2",
                "name": "root2Run",
                "run_type": "chain",
                "parent_run_id": None,
                "child_run_ids": [],
                "dotted_order": "2",
                "status": "success",
            },
        ]
        tree = build_tree_from_runs(runs)

        # Should return one of the root nodes
        assert tree is not None
        assert tree["id"] in ("root1", "root2")

    def test_extract_run_summary_missing_fields(self):
        """Test extract_run_summary with minimal run data."""
        run = {
            "id": "minimal-run",
            "name": "minimalRun",
            "run_type": "chain",
            # Missing most optional fields
        }
        summary = extract_run_summary(run)

        assert summary["id"] == "minimal-run"
        assert summary["name"] == "minimalRun"
        assert summary["tokens"] is None
        assert summary["cost"] is None
        assert summary["model"] is None
        assert summary["has_children"] is False

    def test_extract_run_summary_null_fields(self):
        """Test extract_run_summary handles None values gracefully."""
        run = {
            "id": "null-run",
            "name": "nullRun",
            "run_type": "llm",
            "parent_run_id": None,
            "child_run_ids": None,  # Can be None
            "status": None,
            "error": None,
            "start_time": None,
            "end_time": None,
            "total_tokens": None,
            "total_cost": None,
            "extra": None,
        }
        summary = extract_run_summary(run)

        assert summary["id"] == "null-run"
        assert summary["has_children"] is False
        assert summary["child_count"] == 0

    def test_calculate_summary_no_tokens(self):
        """Test summary calculation with runs that have no token data."""
        runs = [
            {
                "id": "r1",
                "name": "run1",
                "run_type": "chain",
                "parent_run_id": None,
                "status": "success",
                # No token data
                "extra": {},
            },
        ]
        summary = calculate_tree_summary(runs)

        assert summary["total_runs"] == 1
        assert summary["total_tokens"] == 0
        assert summary["total_cost"] == 0

    def test_calculate_summary_mixed_statuses(self):
        """Test summary calculation with mixed success/error statuses."""
        runs = [
            {"id": "r1", "name": "run1", "run_type": "chain", "status": "success", "extra": {}},
            {"id": "r2", "name": "run2", "run_type": "llm", "status": "error", "error": "Err1", "extra": {}},
            {"id": "r3", "name": "run3", "run_type": "llm", "status": "success", "extra": {}},
            {"id": "r4", "name": "run4", "run_type": "tool", "status": "error", "error": "Err2", "extra": {}},
        ]
        summary = calculate_tree_summary(runs)

        assert summary["total_runs"] == 4
        assert summary["has_errors"] is True
        assert summary["error_count"] == 2
        assert len(summary["error_runs"]) == 2

    def test_format_tree_pretty_empty_tree(self):
        """Test pretty formatting with None tree."""
        summary = {
            "total_runs": 0,
            "total_tokens": 0,
            "total_cost": 0,
            "total_duration_ms": None,
            "has_errors": False,
            "error_count": 0,
            "run_types": {},
            "models_used": [],
            "error_runs": [],
        }
        formatted = format_tree_pretty(None, summary)

        assert "TRACE SUMMARY" in formatted
        assert "No tree structure" in formatted or "Total runs: 0" in formatted
