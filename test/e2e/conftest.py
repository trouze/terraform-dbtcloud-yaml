"""Pytest configuration and fixtures for E2E tests.

This module provides:
- Server management fixtures (start/stop the NiceGUI app)
- Browser fixtures via pytest-playwright
- Test data fixtures (YAML configs, protection intent files)
- API mocking fixtures

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.4
"""

import json
import os
import pytest
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator, Dict, Any
from urllib.request import urlopen
from urllib.error import URLError

# Import Playwright types
try:
    from playwright.sync_api import Page, Browser, BrowserContext
except ImportError:
    Page = Any
    Browser = Any
    BrowserContext = Any


# =============================================================================
# Configuration
# =============================================================================

# Default port for the test server (can be overridden via NICEGUI_PORT env var)
TEST_SERVER_PORT = int(os.environ.get("NICEGUI_PORT", 8080))

# Base URL for tests
TEST_BASE_URL = f"http://127.0.0.1:{TEST_SERVER_PORT}"

# Path to the app entry point
APP_ENTRY_POINT = Path(__file__).parent.parent.parent / "importer" / "web" / "app.py"

# Fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# =============================================================================
# Server Management Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def test_server() -> Generator[str, None, None]:
    """Start the NiceGUI application server for testing.
    
    This fixture starts the server once per test session and stops it
    when all tests are complete.
    
    Yields:
        Base URL of the test server
    """
    # Check if server is already running (for development)
    if _is_server_running(TEST_BASE_URL):
        print(f"Using existing server at {TEST_BASE_URL}")
        yield TEST_BASE_URL
        return
    
    # Start the server
    env = os.environ.copy()
    env["NICEGUI_PORT"] = str(TEST_SERVER_PORT)
    env["NICEGUI_RELOAD"] = "false"
    # Add project root to PYTHONPATH so 'importer' module can be found
    project_root = str(Path(__file__).parent.parent.parent)
    env["PYTHONPATH"] = project_root + ":" + env.get("PYTHONPATH", "")
    
    process = subprocess.Popen(
        [sys.executable, str(APP_ENTRY_POINT)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for server to be ready
    max_wait = 30  # seconds
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        if _is_server_running(TEST_BASE_URL):
            print(f"Test server started at {TEST_BASE_URL}")
            break
        time.sleep(0.5)
    else:
        process.terminate()
        stdout, stderr = process.communicate()
        raise RuntimeError(
            f"Server failed to start within {max_wait}s.\n"
            f"stdout: {stdout.decode()}\n"
            f"stderr: {stderr.decode()}"
        )
    
    yield TEST_BASE_URL
    
    # Cleanup
    process.terminate()
    process.wait(timeout=5)
    print("Test server stopped")


def _is_server_running(url: str) -> bool:
    """Check if a server is running at the given URL."""
    try:
        response = urlopen(url, timeout=1)
        return response.status == 200
    except (URLError, TimeoutError):
        return False


# =============================================================================
# Browser Fixtures (Playwright)
# =============================================================================

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: Dict[str, Any]) -> Dict[str, Any]:
    """Configure browser context settings."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture
def page_with_server(test_server: str, page: Page) -> Generator[Page, None, None]:
    """Provide a page with the test server URL.
    
    This fixture ensures the test server is running before providing
    the page to the test.
    """
    page.set_default_timeout(10000)  # 10 second default timeout
    yield page


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def test_workspace(tmp_path: Path) -> Path:
    """Create an isolated test workspace with necessary files.
    
    Returns:
        Path to the test workspace directory
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    # Create directory structure
    (workspace / "terraform").mkdir()
    (workspace / "config").mkdir()
    
    return workspace


@pytest.fixture
def sample_yaml_config(test_workspace: Path) -> Path:
    """Create a sample YAML configuration file.
    
    Returns:
        Path to the created YAML file
    """
    yaml_content = """
version: 2
projects:
  - key: test_project
    name: Test Project
    protected: false
    repository: test_repo
    environments:
      - key: dev
        name: Development
        protected: false
      - key: prod
        name: Production
        protected: false
    jobs:
      - key: daily_job
        name: Daily Job
        protected: false

globals:
  repositories:
    - key: test_repo
      remote_url: https://github.com/test/repo
      protected: false
"""
    yaml_file = test_workspace / "config" / "dbt-cloud-config.yml"
    yaml_file.write_text(yaml_content)
    return yaml_file


@pytest.fixture
def sample_terraform_state(test_workspace: Path) -> Path:
    """Create a sample Terraform state file.
    
    Returns:
        Path to the created state file
    """
    state = {
        "version": 4,
        "terraform_version": "1.5.0",
        "serial": 1,
        "lineage": "test-lineage",
        "outputs": {},
        "resources": [
            {
                "module": "module.dbt_cloud.module.projects_v2[0]",
                "type": "dbtcloud_project",
                "name": "projects",
                "instances": [
                    {"index_key": "test_project", "attributes": {"id": "123"}},
                ],
            },
            {
                "module": "module.dbt_cloud.module.projects_v2[0]",
                "type": "dbtcloud_repository",
                "name": "repositories",
                "instances": [
                    {"index_key": "test_project", "attributes": {"id": "456"}},
                ],
            },
            {
                "module": "module.dbt_cloud.module.projects_v2[0]",
                "type": "dbtcloud_project_repository",
                "name": "project_repositories",
                "instances": [
                    {"index_key": "test_project", "attributes": {"id": "789"}},
                ],
            },
        ],
    }
    
    state_file = test_workspace / "terraform" / "terraform.tfstate"
    state_file.write_text(json.dumps(state, indent=2))
    return state_file


@pytest.fixture
def empty_protection_intent(test_workspace: Path) -> Path:
    """Create an empty protection intent file.
    
    Returns:
        Path to the created intent file
    """
    intent = {
        "version": 1,
        "updated_at": "2026-02-04T00:00:00Z",
        "intent": {},
        "history": [],
    }
    
    intent_file = test_workspace / "config" / "protection-intent.json"
    intent_file.write_text(json.dumps(intent, indent=2))
    return intent_file


@pytest.fixture
def protection_intent_with_pending(test_workspace: Path) -> Path:
    """Create a protection intent file with pending intents.
    
    Returns:
        Path to the created intent file
    """
    intent = {
        "version": 1,
        "updated_at": "2026-02-04T00:00:00Z",
        "intent": {
            "PRJ:test_project": {
                "protected": True,
                "set_at": "2026-02-04T00:00:00Z",
                "set_by": "test",
                "reason": "Test protection",
                "resource_type": "PRJ",
                "applied_to_yaml": False,
                "applied_to_tf_state": False,
            },
        },
        "history": [
            {
                "resource_key": "PRJ:test_project",
                "action": "protect",
                "timestamp": "2026-02-04T00:00:00Z",
                "source": "test",
            },
        ],
    }
    
    intent_file = test_workspace / "config" / "protection-intent.json"
    intent_file.write_text(json.dumps(intent, indent=2))
    return intent_file


# =============================================================================
# API Mocking Fixtures
# =============================================================================

@pytest.fixture
def mock_api_responses() -> Dict[str, Any]:
    """Provide mock API responses for dbt Cloud API.
    
    Returns:
        Dictionary mapping endpoint patterns to response data
    """
    return {
        "accounts": {
            "data": [
                {"id": 1, "name": "Test Account"},
            ],
        },
        "projects": {
            "data": [
                {"id": 123, "name": "Test Project", "account_id": 1},
            ],
        },
        "environments": {
            "data": [
                {"id": 456, "name": "Development", "project_id": 123},
                {"id": 457, "name": "Production", "project_id": 123},
            ],
        },
        "jobs": {
            "data": [
                {"id": 789, "name": "Daily Job", "project_id": 123, "environment_id": 456},
            ],
        },
        "repositories": {
            "data": [
                {"id": 12, "remote_url": "https://github.com/test/repo", "project_id": 123},
            ],
        },
    }


@pytest.fixture
def page_with_mocked_api(page: Page, mock_api_responses: Dict[str, Any]) -> Page:
    """Configure page to intercept and mock API calls.
    
    Args:
        page: Playwright page instance
        mock_api_responses: Mock response data
        
    Returns:
        Configured page with route interception
    """
    def handle_route(route):
        url = route.request.url
        
        # Check if this is a dbt Cloud API call
        if "cloud.getdbt.com" in url or "api.getdbt.com" in url:
            # Extract endpoint from URL
            for endpoint, response_data in mock_api_responses.items():
                if endpoint in url:
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(response_data),
                    )
                    return
            
            # Default mock response
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"data": []}),
            )
            return
        
        # Let other requests through
        route.continue_()
    
    page.route("**/*", handle_route)
    return page


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def wait_for_nicegui():
    """Factory fixture to wait for NiceGUI elements to render."""
    def _wait(page: Page, selector: str, timeout: int = 5000) -> None:
        """Wait for a NiceGUI element to be visible.
        
        Args:
            page: Playwright page instance
            selector: CSS selector
            timeout: Maximum wait time in milliseconds
        """
        page.wait_for_selector(selector, state="visible", timeout=timeout)
    
    return _wait


@pytest.fixture
def screenshot_on_failure(page: Page, request, tmp_path: Path):
    """Take a screenshot on test failure.
    
    This fixture is automatically used by tests to capture screenshots
    when a test fails.
    """
    yield
    
    # Check if test failed
    if request.node.rep_call.failed:
        screenshot_path = tmp_path / f"failure_{request.node.name}.png"
        page.screenshot(path=str(screenshot_path))
        print(f"Screenshot saved to: {screenshot_path}")


# =============================================================================
# Pytest Hooks
# =============================================================================

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to make test result available to fixtures."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
