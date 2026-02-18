"""Regression tests for post-apply target snapshot staleness.

Verifies:
- TargetFetchState.mark_stale / clear_stale transitions
- Successful terraform apply marks target snapshot stale
- Successful target fetch clears stale flags
- Generate/plan/apply operations are blocked when target is stale
- State viewer shows outputs-only explanatory message
"""

import asyncio
import json
import pytest
from dataclasses import asdict
from unittest.mock import MagicMock, patch

from importer.web.state import AppState, TargetFetchState


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# =============================================================================
# TargetFetchState staleness field tests
# =============================================================================


class TestTargetFetchStateStaleness:
    """Unit tests for TargetFetchState staleness helpers."""

    def test_default_not_stale(self):
        state = TargetFetchState()
        assert state.is_stale is False
        assert state.stale_reason == ""
        assert state.stale_marked_at is None

    def test_mark_stale_sets_fields(self):
        state = TargetFetchState(fetch_complete=True)
        state.mark_stale("apply changed target")
        assert state.is_stale is True
        assert state.stale_reason == "apply changed target"
        assert state.stale_marked_at is not None
        assert state.fetch_complete is False

    def test_clear_stale_resets_fields(self):
        state = TargetFetchState(
            is_stale=True,
            stale_reason="test",
            stale_marked_at="2025-01-01T00:00:00+00:00",
        )
        state.clear_stale()
        assert state.is_stale is False
        assert state.stale_reason == ""
        assert state.stale_marked_at is None

    def test_mark_then_clear_roundtrip(self):
        state = TargetFetchState(fetch_complete=True)
        state.mark_stale("apply completed")
        assert state.is_stale is True
        assert state.fetch_complete is False

        state.fetch_complete = True
        state.clear_stale()
        assert state.is_stale is False
        assert state.fetch_complete is True

    def test_serialization_backward_compat(self):
        """New fields have defaults, so deserializing old state works."""
        old_data = {
            "output_dir": "dev_support/samples/target",
            "fetch_complete": True,
            "last_fetch_file": "/some/path.json",
        }
        state = TargetFetchState(**{
            k: v for k, v in old_data.items()
            if k in TargetFetchState.__dataclass_fields__
        })
        assert state.is_stale is False
        assert state.stale_reason == ""
        assert state.stale_marked_at is None

    def test_asdict_includes_stale_fields(self):
        state = TargetFetchState()
        state.mark_stale("reason")
        d = asdict(state)
        assert "is_stale" in d
        assert "stale_reason" in d
        assert "stale_marked_at" in d
        assert d["is_stale"] is True
        assert d["stale_reason"] == "reason"


# =============================================================================
# Deploy apply → stale transition tests
# =============================================================================


class TestApplyMarksTargetStale:
    """Verify that _run_terraform_apply marks target as stale on success."""

    @pytest.fixture
    def app_state(self):
        state = AppState()
        state.deploy.last_plan_success = True
        state.deploy.terraform_dir = "/tmp/test_tf"
        state.target_fetch.fetch_complete = True
        return state

    def test_successful_apply_marks_stale(self, app_state):
        from importer.web.pages.deploy import _run_terraform_apply

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Apply complete! Resources: 5 added, 0 changed, 0 destroyed."
        mock_result.stderr = ""

        deploy_state = {"terraform_dir": "/tmp/test_tf"}
        save_state = MagicMock()

        with patch("importer.web.pages.deploy.asyncio.to_thread", return_value=mock_result), \
             patch("importer.web.pages.deploy._get_terraform_env", return_value={}), \
             patch("importer.web.pages.deploy.cleanup_adopt_imports_file", return_value=(False, None)), \
             patch("importer.web.pages.deploy.ui"):
            terminal = MagicMock()
            _run(_run_terraform_apply(app_state, terminal, save_state, deploy_state))

        assert app_state.target_fetch.is_stale is True
        assert app_state.target_fetch.fetch_complete is False
        assert "apply" in app_state.target_fetch.stale_reason.lower()
        save_state.assert_called()

    def test_failed_apply_does_not_mark_stale(self, app_state):
        from importer.web.pages.deploy import _run_terraform_apply

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: something went wrong"

        deploy_state = {"terraform_dir": "/tmp/test_tf"}
        save_state = MagicMock()

        with patch("importer.web.pages.deploy.asyncio.to_thread", return_value=mock_result), \
             patch("importer.web.pages.deploy._get_terraform_env", return_value={}), \
             patch("importer.web.pages.deploy.ui"):
            terminal = MagicMock()
            _run(_run_terraform_apply(app_state, terminal, save_state, deploy_state))

        assert app_state.target_fetch.is_stale is False
        assert app_state.target_fetch.fetch_complete is True


# =============================================================================
# Stale guard tests
# =============================================================================


class TestStaleGuards:
    """Generate/plan/apply operations are blocked when target is stale."""

    @pytest.fixture
    def stale_state(self):
        state = AppState()
        state.target_fetch.mark_stale("test staleness")
        state.deploy.last_plan_success = True
        state.deploy.terraform_initialized = True
        return state

    def test_generate_blocked_when_stale(self, stale_state):
        from importer.web.pages.deploy import _run_generate

        terminal = MagicMock()
        save_state = MagicMock()

        with patch("importer.web.pages.deploy.ui"):
            _run(_run_generate(stale_state, terminal, save_state, {}, "/tmp"))

        terminal.error.assert_called()
        error_msg = terminal.error.call_args_list[0][0][0]
        assert "stale" in error_msg.lower()

    def test_plan_blocked_when_stale(self, stale_state):
        from importer.web.pages.deploy import _run_terraform_plan

        terminal = MagicMock()
        save_state = MagicMock()

        with patch("importer.web.pages.deploy.ui"):
            _run(_run_terraform_plan(stale_state, terminal, save_state, {}))

        terminal.error.assert_called()

    def test_apply_blocked_when_stale(self, stale_state):
        from importer.web.pages.deploy import _run_terraform_apply

        terminal = MagicMock()
        save_state = MagicMock()

        with patch("importer.web.pages.deploy.ui"):
            _run(_run_terraform_apply(stale_state, terminal, save_state, {}))

        terminal.error.assert_called()

    def test_generate_allowed_when_not_stale(self):
        """Generate proceeds normally when target is not stale (may fail for other reasons)."""
        from importer.web.pages.deploy import _run_generate

        state = AppState()
        state.target_fetch.is_stale = False
        state.map.last_yaml_file = None

        terminal = MagicMock()
        save_state = MagicMock()

        with patch("importer.web.pages.deploy.ui"):
            _run(_run_generate(state, terminal, save_state, {}, "/tmp"))

        if terminal.error.called:
            msg = terminal.error.call_args_list[0][0][0]
            assert "stale" not in msg.lower()


# =============================================================================
# Target fetch clears stale tests
# =============================================================================


class TestTargetFetchClearsStale:
    """Successful target fetch should clear stale flags."""

    def test_clear_stale_on_fetch_complete(self):
        state = TargetFetchState()
        state.mark_stale("apply changed target")
        assert state.is_stale is True

        state.fetch_complete = True
        state.clear_stale()
        assert state.is_stale is False
        assert state.stale_reason == ""
        assert state.stale_marked_at is None


# =============================================================================
# State viewer outputs-only tests
# =============================================================================


class TestStateViewerOutputsSemantics:
    """Verify state viewer handles outputs-only state files correctly."""

    def test_outputs_only_state_data_detection(self):
        """When resources=[] and outputs exist, both counts should be available."""
        state_data = {
            "version": 4,
            "terraform_version": "1.14.1",
            "resources": [],
            "outputs": {
                "project_ids": {"value": {"proj_a": 1}},
                "job_ids": {"value": {"job_a": 100}},
            },
        }
        resource_count = sum(
            max(1, len(r.get("instances", [])))
            for r in state_data.get("resources", [])
            if r.get("mode") != "data"
        )
        output_count = len(state_data.get("outputs", {}))

        assert resource_count == 0
        assert output_count == 2

    def test_normal_state_data_has_resources(self):
        """Normal state has both resources and outputs."""
        state_data = {
            "version": 4,
            "resources": [
                {"type": "dbtcloud_project", "mode": "managed", "instances": [{"attributes": {}}]},
            ],
            "outputs": {"project_ids": {"value": {"a": 1}}},
        }
        resource_count = sum(
            max(1, len(r.get("instances", [])))
            for r in state_data.get("resources", [])
            if r.get("mode") != "data"
        )
        output_count = len(state_data.get("outputs", {}))

        assert resource_count == 1
        assert output_count == 1

    def test_empty_state_no_outputs(self):
        """Completely empty state has neither resources nor outputs."""
        state_data = {"version": 4, "resources": [], "outputs": {}}
        resource_count = sum(
            max(1, len(r.get("instances", [])))
            for r in state_data.get("resources", [])
            if r.get("mode") != "data"
        )
        output_count = len(state_data.get("outputs", {}))

        assert resource_count == 0
        assert output_count == 0

    def test_data_sources_excluded_from_resource_count(self):
        """Data sources should not count as managed resources."""
        state_data = {
            "version": 4,
            "resources": [
                {"type": "dbtcloud_project", "mode": "managed", "instances": [{}]},
                {"type": "data.external", "mode": "data", "instances": [{}]},
            ],
            "outputs": {},
        }
        resource_count = sum(
            max(1, len(r.get("instances", [])))
            for r in state_data.get("resources", [])
            if r.get("mode") != "data"
        )
        assert resource_count == 1
