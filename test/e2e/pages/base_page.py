"""Base Page Object for E2E tests.

This provides common functionality for all page objects including:
- Navigation
- Waiting for NiceGUI to render
- Common element locators
- Screenshot utilities

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.4
"""

from typing import Optional, List
from playwright.sync_api import Page, Locator, expect


class BasePage:
    """Base class for all Page Objects.
    
    Provides common functionality shared across all pages in the application.
    """
    
    # Common selectors
    CONTENT_SELECTOR = ".nicegui-content"
    LOADING_SPINNER = ".q-spinner"
    NOTIFICATION = ".q-notification"
    DIALOG = ".q-dialog"
    CARD = ".q-card"
    
    def __init__(self, page: Page, base_url: str = "http://127.0.0.1:8080"):
        """Initialize the page object.
        
        Args:
            page: Playwright page instance
            base_url: Base URL of the application
        """
        self.page = page
        self.base_url = base_url
        self._default_timeout = 10000  # 10 seconds
    
    # =========================================================================
    # Navigation
    # =========================================================================
    
    def navigate(self, path: str = "") -> None:
        """Navigate to a path within the application.
        
        Args:
            path: Path to navigate to (e.g., "/match", "/protection-management")
        """
        url = f"{self.base_url}{path}"
        self.page.goto(url)
        self.wait_for_page_load()
    
    def navigate_to_home(self) -> None:
        """Navigate to the home page."""
        self.navigate("/")
    
    def get_current_url(self) -> str:
        """Get the current page URL."""
        return self.page.url
    
    def get_current_path(self) -> str:
        """Get the current page path (without base URL)."""
        url = self.page.url
        return url.replace(self.base_url, "")
    
    # =========================================================================
    # Waiting
    # =========================================================================
    
    def wait_for_page_load(self) -> None:
        """Wait for the NiceGUI page to fully render."""
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_selector(self.CONTENT_SELECTOR, state="visible")
    
    def wait_for_element(
        self,
        selector: str,
        state: str = "visible",
        timeout: Optional[int] = None,
    ) -> Locator:
        """Wait for an element to be in a specific state.
        
        Args:
            selector: CSS selector
            state: Expected state ("visible", "hidden", "attached", "detached")
            timeout: Maximum wait time in milliseconds
            
        Returns:
            Locator for the element
        """
        timeout = timeout or self._default_timeout
        locator = self.page.locator(selector)
        locator.wait_for(state=state, timeout=timeout)
        return locator
    
    def wait_for_loading_complete(self) -> None:
        """Wait for any loading spinners to disappear."""
        spinner = self.page.locator(self.LOADING_SPINNER)
        if spinner.count() > 0:
            spinner.wait_for(state="hidden")
    
    def wait_for_notification(self, timeout: Optional[int] = None) -> Locator:
        """Wait for a notification to appear.
        
        Args:
            timeout: Maximum wait time in milliseconds
            
        Returns:
            Locator for the notification
        """
        return self.wait_for_element(self.NOTIFICATION, timeout=timeout)
    
    def wait_for_dialog(self, timeout: Optional[int] = None) -> Locator:
        """Wait for a dialog to appear.
        
        Args:
            timeout: Maximum wait time in milliseconds
            
        Returns:
            Locator for the dialog
        """
        return self.wait_for_element(self.DIALOG, timeout=timeout)
    
    # =========================================================================
    # Element Interactions
    # =========================================================================
    
    def click_button(self, text: str) -> None:
        """Click a button by its text content.
        
        Args:
            text: Button text to find and click
        """
        self.page.get_by_role("button", name=text).click()
    
    def click_link(self, text: str) -> None:
        """Click a link by its text content.
        
        Args:
            text: Link text to find and click
        """
        self.page.get_by_role("link", name=text).click()
    
    def fill_input(self, label: str, value: str) -> None:
        """Fill an input field by its label.
        
        Args:
            label: Label text of the input
            value: Value to enter
        """
        self.page.get_by_label(label).fill(value)
    
    def select_option(self, label: str, option: str) -> None:
        """Select an option from a dropdown by label.
        
        Args:
            label: Label text of the dropdown
            option: Option text to select
        """
        dropdown = self.page.get_by_label(label)
        dropdown.click()
        self.page.get_by_role("option", name=option).click()
    
    def check_checkbox(self, label: str) -> None:
        """Check a checkbox by its label.
        
        Args:
            label: Label text of the checkbox
        """
        checkbox = self.page.get_by_label(label)
        if not checkbox.is_checked():
            checkbox.click()
    
    def uncheck_checkbox(self, label: str) -> None:
        """Uncheck a checkbox by its label.
        
        Args:
            label: Label text of the checkbox
        """
        checkbox = self.page.get_by_label(label)
        if checkbox.is_checked():
            checkbox.click()
    
    # =========================================================================
    # Assertions
    # =========================================================================
    
    def assert_url_contains(self, text: str) -> None:
        """Assert the current URL contains text.
        
        Args:
            text: Text expected in URL
        """
        expect(self.page).to_have_url(f"*{text}*")
    
    def assert_text_visible(self, text: str) -> None:
        """Assert text is visible on the page.
        
        Args:
            text: Text expected to be visible
        """
        expect(self.page.get_by_text(text)).to_be_visible()
    
    def assert_element_visible(self, selector: str) -> None:
        """Assert an element is visible.
        
        Args:
            selector: CSS selector
        """
        expect(self.page.locator(selector)).to_be_visible()
    
    def assert_element_hidden(self, selector: str) -> None:
        """Assert an element is hidden.
        
        Args:
            selector: CSS selector
        """
        expect(self.page.locator(selector)).to_be_hidden()
    
    def assert_button_enabled(self, text: str) -> None:
        """Assert a button is enabled.
        
        Args:
            text: Button text
        """
        expect(self.page.get_by_role("button", name=text)).to_be_enabled()
    
    def assert_button_disabled(self, text: str) -> None:
        """Assert a button is disabled.
        
        Args:
            text: Button text
        """
        expect(self.page.get_by_role("button", name=text)).to_be_disabled()
    
    # =========================================================================
    # Screenshots and Debugging
    # =========================================================================
    
    def take_screenshot(self, name: str, path: str = ".ralph/screenshots") -> str:
        """Take a screenshot of the current page.
        
        Args:
            name: Screenshot filename (without extension)
            path: Directory to save screenshots
            
        Returns:
            Full path to the screenshot file
        """
        import os
        os.makedirs(path, exist_ok=True)
        screenshot_path = f"{path}/{name}.png"
        self.page.screenshot(path=screenshot_path)
        return screenshot_path
    
    def get_page_content(self) -> str:
        """Get the text content of the page.
        
        Returns:
            Page text content
        """
        return self.page.text_content("body") or ""
    
    def print_console_logs(self) -> None:
        """Print browser console logs for debugging."""
        # Note: Console logs need to be captured via page.on("console")
        # This is a placeholder for debugging
        pass
    
    # =========================================================================
    # Common NiceGUI Components
    # =========================================================================
    
    def get_cards(self) -> List[Locator]:
        """Get all card components on the page.
        
        Returns:
            List of card locators
        """
        return self.page.locator(self.CARD).all()
    
    def get_notification_text(self) -> Optional[str]:
        """Get the text of the current notification if visible.
        
        Returns:
            Notification text or None
        """
        notification = self.page.locator(self.NOTIFICATION)
        if notification.count() > 0:
            return notification.text_content()
        return None
    
    def close_dialog(self) -> None:
        """Close the current dialog if open."""
        dialog = self.page.locator(self.DIALOG)
        if dialog.count() > 0:
            # Try clicking close button or pressing Escape
            close_btn = dialog.locator("button:has-text('Close'), button:has-text('Cancel')")
            if close_btn.count() > 0:
                close_btn.first.click()
            else:
                self.page.keyboard.press("Escape")
