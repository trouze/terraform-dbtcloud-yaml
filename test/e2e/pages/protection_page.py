"""Page Object for Protection Management page.

This page allows users to:
- View current protection status of resources
- Select resources to protect/unprotect
- Generate protection changes (YAML + moved blocks)
- See pending changes and status badges

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.4
"""

from typing import List, Optional, Dict
from playwright.sync_api import Page, Locator, expect

from .base_page import BasePage


class ProtectionManagementPage(BasePage):
    """Page Object for the Protection Management page (/protection-management)."""
    
    # Page-specific selectors
    PATH = "/protection-management"
    
    # Resource table selectors
    RESOURCE_TABLE = "table.q-table, .ag-grid, .resource-table"
    RESOURCE_ROW = "tr, .ag-row, .resource-row"
    
    # Protection controls
    PROTECT_BUTTON = "button:has-text('Protect')"
    UNPROTECT_BUTTON = "button:has-text('Unprotect')"
    GENERATE_BUTTON = "button:has-text('Generate')"
    BULK_PROTECT_BUTTON = "button:has-text('Protect All')"
    BULK_UNPROTECT_BUTTON = "button:has-text('Unprotect All')"
    
    # Status badges
    PENDING_GENERATE_BADGE = ".badge-orange, [class*='pending-generate']"
    PENDING_APPLY_BADGE = ".badge-blue, [class*='pending-apply']"
    PROTECTED_BADGE = ".badge-green, [class*='protected']"
    UNPROTECTED_BADGE = ".badge-gray, [class*='unprotected']"
    
    # Dialog selectors
    CASCADE_DIALOG = ".cascade-dialog, .q-dialog:has-text('cascade')"
    GENERATE_DIALOG = ".generate-dialog, .q-dialog:has-text('Generate')"
    STREAMING_OUTPUT = ".streaming-output, pre, code"
    
    def __init__(self, page: Page, base_url: str = "http://127.0.0.1:8080"):
        super().__init__(page, base_url)
    
    # =========================================================================
    # Navigation
    # =========================================================================
    
    def go_to_protection_management(self) -> None:
        """Navigate to the protection management page."""
        self.navigate(self.PATH)
    
    def is_on_protection_page(self) -> bool:
        """Check if currently on the protection management page."""
        return self.PATH in self.get_current_path()
    
    # =========================================================================
    # Resource List
    # =========================================================================
    
    def get_resource_count(self) -> int:
        """Get the number of resources displayed.
        
        Returns:
            Number of resource rows
        """
        self.wait_for_loading_complete()
        rows = self.page.locator(self.RESOURCE_ROW)
        return rows.count()
    
    def get_resource_keys(self) -> List[str]:
        """Get all resource keys displayed on the page.
        
        Returns:
            List of resource keys
        """
        self.wait_for_loading_complete()
        # Look for elements with data-resource-key attribute or similar
        keys = []
        rows = self.page.locator(self.RESOURCE_ROW).all()
        for row in rows:
            key_attr = row.get_attribute("data-resource-key")
            if key_attr:
                keys.append(key_attr)
            else:
                # Try to extract from row content
                text = row.text_content() or ""
                # Keys typically start with PRJ: or REPO:
                if "PRJ:" in text:
                    start = text.find("PRJ:")
                    end = text.find(" ", start) if " " in text[start:] else len(text)
                    keys.append(text[start:end].strip())
                elif "REPO:" in text:
                    start = text.find("REPO:")
                    end = text.find(" ", start) if " " in text[start:] else len(text)
                    keys.append(text[start:end].strip())
        return keys
    
    def find_resource_row(self, key: str) -> Optional[Locator]:
        """Find the row for a specific resource.
        
        Args:
            key: Resource key (e.g., "PRJ:my_project")
            
        Returns:
            Locator for the row, or None if not found
        """
        # Try by data attribute first
        row = self.page.locator(f'{self.RESOURCE_ROW}[data-resource-key="{key}"]')
        if row.count() > 0:
            return row.first
        
        # Try by text content
        row = self.page.locator(f'{self.RESOURCE_ROW}:has-text("{key}")')
        if row.count() > 0:
            return row.first
        
        return None
    
    # =========================================================================
    # Protection Status
    # =========================================================================
    
    def get_resource_protection_status(self, key: str) -> Optional[str]:
        """Get the protection status of a resource.
        
        Args:
            key: Resource key
            
        Returns:
            Status string: "protected", "unprotected", "pending-generate", "pending-apply"
        """
        row = self.find_resource_row(key)
        if not row:
            return None
        
        if row.locator(self.PROTECTED_BADGE).count() > 0:
            return "protected"
        elif row.locator(self.PENDING_GENERATE_BADGE).count() > 0:
            return "pending-generate"
        elif row.locator(self.PENDING_APPLY_BADGE).count() > 0:
            return "pending-apply"
        else:
            return "unprotected"
    
    def get_protected_resources(self) -> List[str]:
        """Get keys of all protected resources.
        
        Returns:
            List of protected resource keys
        """
        protected = []
        for key in self.get_resource_keys():
            if self.get_resource_protection_status(key) == "protected":
                protected.append(key)
        return protected
    
    def get_pending_generate_resources(self) -> List[str]:
        """Get keys of resources pending generate.
        
        Returns:
            List of resource keys with pending generate status
        """
        pending = []
        for key in self.get_resource_keys():
            if self.get_resource_protection_status(key) == "pending-generate":
                pending.append(key)
        return pending
    
    # =========================================================================
    # Protection Actions
    # =========================================================================
    
    def protect_resource(self, key: str) -> None:
        """Mark a resource for protection.
        
        Args:
            key: Resource key to protect
        """
        row = self.find_resource_row(key)
        if row:
            protect_btn = row.locator(self.PROTECT_BUTTON)
            if protect_btn.count() > 0:
                protect_btn.click()
                self.wait_for_loading_complete()
    
    def unprotect_resource(self, key: str) -> None:
        """Mark a resource for unprotection.
        
        Args:
            key: Resource key to unprotect
        """
        row = self.find_resource_row(key)
        if row:
            unprotect_btn = row.locator(self.UNPROTECT_BUTTON)
            if unprotect_btn.count() > 0:
                unprotect_btn.click()
                self.wait_for_loading_complete()
    
    def bulk_protect_all(self) -> None:
        """Click the bulk protect all button."""
        self.page.locator(self.BULK_PROTECT_BUTTON).click()
        self.wait_for_loading_complete()
    
    def bulk_unprotect_all(self) -> None:
        """Click the bulk unprotect all button."""
        self.page.locator(self.BULK_UNPROTECT_BUTTON).click()
        self.wait_for_loading_complete()
    
    # =========================================================================
    # Generate Workflow
    # =========================================================================
    
    def click_generate(self) -> None:
        """Click the Generate button to start the generate workflow."""
        self.page.locator(self.GENERATE_BUTTON).click()
    
    def is_generate_enabled(self) -> bool:
        """Check if the Generate button is enabled.
        
        Returns:
            True if Generate button is clickable
        """
        btn = self.page.locator(self.GENERATE_BUTTON)
        if btn.count() == 0:
            return False
        return btn.is_enabled()
    
    def wait_for_generate_dialog(self) -> Locator:
        """Wait for the generate dialog to appear.
        
        Returns:
            Locator for the generate dialog
        """
        return self.wait_for_dialog()
    
    def wait_for_generate_complete(self, timeout: int = 30000) -> None:
        """Wait for the generate process to complete.
        
        Args:
            timeout: Maximum wait time in milliseconds
        """
        # Wait for streaming output to appear
        self.wait_for_element(self.STREAMING_OUTPUT, timeout=timeout)
        
        # Wait for completion message or close button to be enabled
        # The dialog typically shows "Complete" or enables "Close" when done
        self.page.wait_for_function(
            """() => {
                const dialog = document.querySelector('.q-dialog');
                if (!dialog) return false;
                const text = dialog.textContent || '';
                return text.includes('Complete') || text.includes('Success') ||
                       dialog.querySelector('button:not([disabled]):has-text("Close")');
            }""",
            timeout=timeout,
        )
    
    def get_generate_output(self) -> str:
        """Get the streaming output text from generate dialog.
        
        Returns:
            Output text content
        """
        output = self.page.locator(self.STREAMING_OUTPUT)
        if output.count() > 0:
            return output.text_content() or ""
        return ""
    
    def close_generate_dialog(self) -> None:
        """Close the generate dialog."""
        self.close_dialog()
    
    # =========================================================================
    # Cascade Dialog
    # =========================================================================
    
    def is_cascade_dialog_visible(self) -> bool:
        """Check if cascade confirmation dialog is visible.
        
        Returns:
            True if cascade dialog is showing
        """
        dialog = self.page.locator(self.CASCADE_DIALOG)
        return dialog.count() > 0 and dialog.is_visible()
    
    def get_cascade_resources(self) -> List[str]:
        """Get resources listed in cascade dialog.
        
        Returns:
            List of resource keys in cascade
        """
        dialog = self.page.locator(self.CASCADE_DIALOG)
        if dialog.count() == 0:
            return []
        
        # Extract resource keys from dialog content
        text = dialog.text_content() or ""
        resources = []
        for line in text.split("\n"):
            if "PRJ:" in line or "REPO:" in line or "ENV:" in line:
                resources.append(line.strip())
        return resources
    
    def confirm_cascade(self) -> None:
        """Confirm the cascade protection action."""
        dialog = self.page.locator(self.CASCADE_DIALOG)
        if dialog.count() > 0:
            confirm_btn = dialog.locator("button:has-text('Confirm'), button:has-text('Yes')")
            if confirm_btn.count() > 0:
                confirm_btn.click()
                self.wait_for_loading_complete()
    
    def cancel_cascade(self) -> None:
        """Cancel the cascade protection action."""
        dialog = self.page.locator(self.CASCADE_DIALOG)
        if dialog.count() > 0:
            cancel_btn = dialog.locator("button:has-text('Cancel'), button:has-text('No')")
            if cancel_btn.count() > 0:
                cancel_btn.click()
    
    # =========================================================================
    # Assertions
    # =========================================================================
    
    def assert_resource_protected(self, key: str) -> None:
        """Assert a resource is marked as protected.
        
        Args:
            key: Resource key
        """
        status = self.get_resource_protection_status(key)
        assert status == "protected", f"Expected {key} to be protected, but status is {status}"
    
    def assert_resource_unprotected(self, key: str) -> None:
        """Assert a resource is marked as unprotected.
        
        Args:
            key: Resource key
        """
        status = self.get_resource_protection_status(key)
        assert status == "unprotected", f"Expected {key} to be unprotected, but status is {status}"
    
    def assert_resource_pending_generate(self, key: str) -> None:
        """Assert a resource has pending generate status.
        
        Args:
            key: Resource key
        """
        status = self.get_resource_protection_status(key)
        assert status == "pending-generate", f"Expected {key} to be pending-generate, but status is {status}"
    
    def assert_generate_button_enabled(self) -> None:
        """Assert the Generate button is enabled."""
        assert self.is_generate_enabled(), "Generate button should be enabled"
    
    def assert_generate_button_disabled(self) -> None:
        """Assert the Generate button is disabled."""
        assert not self.is_generate_enabled(), "Generate button should be disabled"
    
    def assert_page_loads_without_error(self) -> None:
        """Assert the page loads successfully without 500 error."""
        self.wait_for_page_load()
        page_content = self.get_page_content()
        # Check for actual HTTP 500 error indicators, not just "500" substring
        # (Tailwind CSS uses classes like "translate-500" which would false-positive)
        assert "500 Internal Server Error" not in page_content, "Page returned 500 error"
        assert "HTTP 500" not in page_content, "Page returned HTTP 500 error"
        assert "Internal Server Error" not in page_content, "Page returned Internal Server Error"
        assert "error" not in self.page.title().lower(), "Page title indicates error"
