"""Playwright configuration for E2E tests.

This module defines configuration settings for Playwright browser automation.
These settings can be imported by conftest.py or used directly in tests.

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.4
"""

from pathlib import Path


# =============================================================================
# Browser Configuration
# =============================================================================

# Browser to use for tests
# Options: "chromium", "firefox", "webkit"
BROWSER = "chromium"

# Run in headless mode (no visible browser window)
# Set to False for debugging
HEADLESS = True

# Slow down operations by this many milliseconds
# Useful for debugging (set to 0 for normal speed)
SLOW_MO = 0

# =============================================================================
# Server Configuration
# =============================================================================

# Port for the test server
TEST_SERVER_PORT = 8081

# Base URL for tests
BASE_URL = f"http://127.0.0.1:{TEST_SERVER_PORT}"

# =============================================================================
# Timeout Configuration
# =============================================================================

# Default timeout for operations (milliseconds)
DEFAULT_TIMEOUT = 30000  # 30 seconds

# Navigation timeout
NAVIGATION_TIMEOUT = 30000  # 30 seconds

# Expect (assertion) timeout
EXPECT_TIMEOUT = 10000  # 10 seconds

# =============================================================================
# Viewport Configuration
# =============================================================================

# Default viewport size
VIEWPORT = {
    "width": 1280,
    "height": 720,
}

# =============================================================================
# Screenshot Configuration
# =============================================================================

# Directory for screenshots
SCREENSHOT_DIR = Path(__file__).parent.parent.parent / ".ralph" / "screenshots"

# Take screenshot on test failure
SCREENSHOT_ON_FAILURE = True

# Screenshot format
SCREENSHOT_FORMAT = "png"  # or "jpeg"

# =============================================================================
# Video Recording Configuration
# =============================================================================

# Record video of test execution
RECORD_VIDEO = False

# Video directory
VIDEO_DIR = Path(__file__).parent / "videos"

# Video size
VIDEO_SIZE = {
    "width": 1280,
    "height": 720,
}

# =============================================================================
# Trace Configuration
# =============================================================================

# Record trace for debugging
RECORD_TRACE = False

# Trace options: "on", "off", "on-first-retry", "retain-on-failure"
TRACE_MODE = "retain-on-failure"

# =============================================================================
# Test Configuration
# =============================================================================

# Number of retries for flaky tests
RETRIES = 0

# Number of parallel workers
WORKERS = 1  # Sequential for E2E tests

# =============================================================================
# Network Configuration
# =============================================================================

# Ignore HTTPS certificate errors
IGNORE_HTTPS_ERRORS = True

# Bypass Content Security Policy
BYPASS_CSP = False

# =============================================================================
# Logging Configuration
# =============================================================================

# Console logging level
LOG_LEVEL = "info"  # debug, info, warning, error

# =============================================================================
# Pytest-Playwright Configuration
# =============================================================================

# Configuration dict for pytest-playwright
PYTEST_PLAYWRIGHT_CONFIG = {
    "browser": BROWSER,
    "headless": HEADLESS,
    "slow_mo": SLOW_MO,
    "viewport": VIEWPORT,
}


def get_browser_context_args():
    """Get browser context arguments for Playwright.
    
    Returns:
        Dict of browser context arguments
    """
    return {
        "viewport": VIEWPORT,
        "ignore_https_errors": IGNORE_HTTPS_ERRORS,
        "bypass_csp": BYPASS_CSP,
    }


def get_browser_launch_args():
    """Get browser launch arguments for Playwright.
    
    Returns:
        Dict of browser launch arguments
    """
    return {
        "headless": HEADLESS,
        "slow_mo": SLOW_MO,
    }


# =============================================================================
# Test Markers
# =============================================================================

# Custom pytest markers used in E2E tests
MARKERS = {
    "e2e": "End-to-end browser tests",
    "slow": "Slow tests that may take longer to execute",
    "terraform": "Tests that require Terraform execution",
    "cross_page": "Tests that verify behavior across multiple pages",
}
