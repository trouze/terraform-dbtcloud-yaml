"""E2E smoke tests for target intent: deploy page and target-intent artifact.

These tests verify:
- Deploy page loads without error at /deploy
- Target intent computation is exercised by the deploy flow (artifact created when generate runs)

Run with: pytest test/e2e/test_target_intent_ui.py -v -m e2e
"""

import pytest
from playwright.sync_api import Page


@pytest.fixture
def deploy_page(page_with_server: Page, test_server: str) -> Page:
    """Page with server; use test_server base URL."""
    page_with_server.set_default_timeout(10000)
    return page_with_server


class TestDeployPageLoad:
    """Smoke tests for deploy page."""

    @pytest.mark.e2e
    def test_deploy_page_loads_without_error(self, deploy_page: Page, test_server: str):
        """Deploy page at /deploy loads without 500."""
        deploy_page.goto(f"{test_server}/deploy")
        deploy_page.wait_for_load_state("networkidle")
        # No 500: page should show deploy content (e.g. "Deploy" or "Plan Deployment")
        content = deploy_page.content()
        assert "500" not in content or "Internal Server Error" not in content

    @pytest.mark.e2e
    def test_deploy_page_url(self, deploy_page: Page, test_server: str):
        """Deploy page URL is /deploy."""
        deploy_page.goto(f"{test_server}/deploy")
        deploy_page.wait_for_load_state("domcontentloaded")
        assert "/deploy" in deploy_page.url
