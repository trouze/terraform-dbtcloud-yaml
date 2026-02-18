"""Contract enforcement tests — catch regressions where pages reintroduce
duplicate implementations of canonical helpers.

These tests inspect source code to verify that pages delegate to the
shared contracts defined in docs/architecture/canonical-contracts.md.

They are intentionally "meta" tests — they verify architecture rules,
not runtime behavior. This catches drift before it becomes a bug.
"""

import ast
import re
from pathlib import Path

import pytest

# Paths relative to repo root
REPO_ROOT = Path(__file__).parent.parent.parent.parent
PAGES_DIR = REPO_ROOT / "importer" / "web" / "pages"
HELPERS_FILE = REPO_ROOT / "importer" / "web" / "utils" / "terraform_helpers.py"
PIPELINE_FILE = REPO_ROOT / "importer" / "web" / "utils" / "generate_pipeline.py"


def _read_source(filepath: Path) -> str:
    """Read a Python source file."""
    return filepath.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Contract 3a: No duplicate get_terraform_env implementations
# ---------------------------------------------------------------------------


class TestNoDuplicateEnvConstruction:
    """Pages must not implement their own TF env construction.

    The only allowed pattern is:
    - Importing from terraform_helpers (directly or via alias)
    - A thin wrapper that delegates to the shared function
    """

    @pytest.mark.parametrize(
        "page",
        ["adopt.py", "deploy.py", "destroy.py", "utilities.py"],
    )
    def test_no_inline_tf_var_assignment(self, page: str) -> None:
        """No page should directly set TF_VAR_dbt_token except via the helper."""
        source = _read_source(PAGES_DIR / page)

        # Count raw env["TF_VAR_dbt_token"] assignments
        raw_assignments = re.findall(
            r'env\["TF_VAR_dbt_token"\]\s*=', source
        )

        assert len(raw_assignments) == 0, (
            f"{page} has {len(raw_assignments)} direct TF_VAR_dbt_token "
            f"assignment(s). Delegate to terraform_helpers.get_terraform_env() instead."
        )

    def test_helpers_module_has_canonical_implementation(self) -> None:
        """terraform_helpers.py must contain the canonical get_terraform_env."""
        source = _read_source(HELPERS_FILE)
        assert "def get_terraform_env(" in source


# ---------------------------------------------------------------------------
# Contract 3b: No duplicate path resolution
# ---------------------------------------------------------------------------


class TestNoDuplicatePathResolution:
    """Pages must not compute project_root manually."""

    @pytest.mark.parametrize(
        "page",
        ["adopt.py", "utilities.py"],
    )
    def test_no_parent_chain_path_resolution(self, page: str) -> None:
        """No page should use Path(__file__).parent.parent... for project root."""
        source = _read_source(PAGES_DIR / page)

        parent_chains = re.findall(
            r"Path\(__file__\)\.parent\.parent\.parent\.parent", source
        )

        assert len(parent_chains) == 0, (
            f"{page} has {len(parent_chains)} manual project root resolution(s). "
            f"Use resolve_deployment_paths() instead."
        )


# ---------------------------------------------------------------------------
# Contract 2: Generate pipeline is the single entrypoint
# ---------------------------------------------------------------------------


class TestGeneratePipelineIsEntrypoint:
    """Verify pipeline module exists and has the required signature."""

    def test_pipeline_module_exists(self) -> None:
        assert PIPELINE_FILE.exists()

    def test_pipeline_has_run_function(self) -> None:
        source = _read_source(PIPELINE_FILE)
        assert "async def run_generate_pipeline(" in source

    def test_pipeline_result_dataclass_exists(self) -> None:
        source = _read_source(PIPELINE_FILE)
        assert "class PipelineResult" in source


# ---------------------------------------------------------------------------
# Contract 1: Reconcile source consistency
# ---------------------------------------------------------------------------


class TestReconcileSourceConsistency:
    """Verify that reconcile_state_resources is the primary state source."""

    def test_utilities_uses_reconcile_state(self) -> None:
        source = _read_source(PAGES_DIR / "utilities.py")
        assert "reconcile_state_resources" in source, (
            "utilities.py must use reconcile_state_resources"
        )

    def test_canonical_contracts_doc_exists(self) -> None:
        doc = REPO_ROOT / "docs" / "architecture" / "canonical-contracts.md"
        assert doc.exists(), "canonical-contracts.md documentation is required"

    def test_workflow_mapping_doc_exists(self) -> None:
        doc = REPO_ROOT / "docs" / "architecture" / "workflow-mapping.md"
        assert doc.exists(), "workflow-mapping.md documentation is required"


class TestSharedDetailDialogReuse:
    """Protection grid should reuse shared detail dialog path."""

    def test_utilities_reuses_show_match_detail_dialog(self) -> None:
        source = _read_source(PAGES_DIR / "utilities.py")
        assert "show_match_detail_dialog" in source, (
            "utilities.py should reuse show_match_detail_dialog from entity_table.py "
            "instead of implementing a duplicate detail popup"
        )
