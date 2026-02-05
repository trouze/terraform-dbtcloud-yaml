"""Page Object for Destroy page.

The Destroy page allows users to:
- View resources that can be destroyed
- See protection status that prevents destruction
- Unprotect resources before destruction
- Generate protection changes for unprotection
- Execute terraform destroy (with safeguards)

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.4
"""

from typing import List, Optional, Dict
from playwright.sync_api import Page, Locator, expect

from .base_page import BasePage


class DestroyPage(BasePage):
    """Page Object for the Destroy Target Resources page (/destroy)."""
    
    PATH = "/destroy"
    
    # Resource selectors
    RESOURCE_LIST = ".destroy-list, .resource-list"
    RESOURCE_ITEM = ".destroy-item, .resource-item"
    
    # Protection controls in destroy context
    PROTECTION_PANEL = ".protection-panel, [data-section='protection']"
    UNPROTECT_BUTTON = "button:has-text('Unprotect')"
    UNPROTECT_ALL_BUTTON = "button:has-text('Unprotect All')"
    GENERATE_BUTTON = "button:has-text('Generate Protection Changes')"
    
    # Status badges
    PROTECTED_BADGE = ".badge-green, [class*='protected'], .protected-indicator"
    UNPROTECTED_BADGE = ".badge-gray, [class*='unprotected']"
    PENDING_GENERATE_BADGE = ".badge-orange, [class*='pending-generate']"
    PENDING_APPLY_BADGE = ".badge-blue, [class*='pending-apply']"
    BLOCKED_BADGE = ".badge-red, [class*='blocked'], [class*='destroy-blocked']"
    
    # Destroy controls
    DESTROY_BUTTON = "button:has-text('Destroy')"
    CONFIRM_DESTROY_INPUT = "input[placeholder*='confirm'], input[name*='confirm']"
    CONFIRM_DESTROY_BUTTON = "button:has-text('Confirm Destroy')"
    
    # Dialogs
    CASCADE_DIALOG = ".q-dialog:has-text('cascade')"
    GENERATE_DIALOG = ".q-dialog:has-text('Generate')"
    DESTROY_CONFIRM_DIALOG = ".q-dialog:has-text('Confirm'), .q-dialog:has-text('Destroy')"
    STREAMING_OUTPUT = ".streaming-output, pre.output"
    
    # Warning elements
    PROTECTED_WARNING = ".protected-warning, [class*='destroy-warning']"
    PREVENT_DESTROY_MESSAGE = "text=prevent_destroy"
    
    def __init__(self, page: Page, base_url: str = "http://127.0.0.1:8080"):
        super().__init__(page, base_url)
    
    # =========================================================================
    # Navigation
    # =========================================================================
    
    def go_to_destroy(self) -> None:
        """Navigate to the destroy page."""
        self.navigate(self.PATH)
    
    def is_on_destroy_page(self) -> bool:
        """Check if currently on the destroy page."""
        return self.PATH in self.get_current_path()
    
    # =========================================================================
    # Resource List
    # =========================================================================
    
    def get_resource_items(self) -> List[Locator]:
        """Get all resource items on the page."""
        self.wait_for_loading_complete()
        return self.page.locator(self.RESOURCE_ITEM).all()
    
    def get_resource_count(self) -> int:
        """Get the number of resources available for destruction."""
        return len(self.get_resource_items())
    
    def find_resource(self, key: str) -> Optional[Locator]:
        """Find a resource by key.
        
        Args:
            key: Resource key
            
        Returns:
            Locator or None
        """
        item = self.page.locator(f'{self.RESOURCE_ITEM}[data-key="{key}"]')
        if item.count() > 0:
            return item.first
        
        item = self.page.locator(f'{self.RESOURCE_ITEM}:has-text("{key}")')
        if item.count() > 0:
            return item.first
        
        return None
    
    def get_destroyable_resources(self) -> List[str]:
        """Get keys of resources that can be destroyed (unprotected).
        
        Returns:
            List of resource keys that can be destroyed
        """
        destroyable = []
        for item in self.get_resource_items():
            # Check if not protected and not blocked
            if item.locator(self.PROTECTED_BADGE).count() == 0 and \
               item.locator(self.BLOCKED_BADGE).count() == 0:
                key = item.get_attribute("data-key") or item.text_content() or ""
                if key:
                    destroyable.append(key.strip())
        return destroyable
    
    def get_protected_resources(self) -> List[str]:
        """Get keys of protected resources that block destruction.
        
        Returns:
            List of protected resource keys
        """
        protected = []
        for item in self.get_resource_items():
            if item.locator(self.PROTECTED_BADGE).count() > 0:
                key = item.get_attribute("data-key") or item.text_content() or ""
                if key:
                    protected.append(key.strip())
        return protected
    
    # =========================================================================
    # Protection Status
    # =========================================================================
    
    def get_resource_protection_status(self, key: str) -> Optional[str]:
        """Get the protection status of a resource.
        
        Args:
            key: Resource key
            
        Returns:
            Status: "protected", "unprotected", "pending-generate", "pending-apply", "blocked"
        """
        item = self.find_resource(key)
        if not item:
            return None
        
        if item.locator(self.BLOCKED_BADGE).count() > 0:
            return "blocked"
        elif item.locator(self.PROTECTED_BADGE).count() > 0:
            return "protected"
        elif item.locator(self.PENDING_GENERATE_BADGE).count() > 0:
            return "pending-generate"
        elif item.locator(self.PENDING_APPLY_BADGE).count() > 0:
            return "pending-apply"
        else:
            return "unprotected"
    
    def is_resource_destroyable(self, key: str) -> bool:
        """Check if a resource can be destroyed.
        
        Args:
            key: Resource key
            
        Returns:
            True if resource can be destroyed
        """
        status = self.get_resource_protection_status(key)
        return status == "unprotected"
    
    # =========================================================================
    # Unprotection Actions
    # =========================================================================
    
    def unprotect_resource(self, key: str) -> None:
        """Mark a resource for unprotection.
        
        Args:
            key: Resource key to unprotect
        """
        item = self.find_resource(key)
        if item:
            unprotect_btn = item.locator(self.UNPROTECT_BUTTON)
            if unprotect_btn.count() > 0:
                unprotect_btn.click()
                self.wait_for_loading_complete()
    
    def unprotect_all_visible(self) -> None:
        """Unprotect all visible resources."""
        btn = self.page.locator(self.UNPROTECT_ALL_BUTTON)
        if btn.count() > 0:
            btn.click()
            self.wait_for_loading_complete()
    
    # =========================================================================
    # Generate Workflow (for unprotection)
    # =========================================================================
    
    def is_generate_button_visible(self) -> bool:
        """Check if the Generate Protection Changes button is visible."""
        btn = self.page.locator(self.GENERATE_BUTTON)
        return btn.count() > 0 and btn.is_visible()
    
    def is_generate_button_enabled(self) -> bool:
        """Check if the Generate button is enabled."""
        btn = self.page.locator(self.GENERATE_BUTTON)
        if btn.count() == 0:
            return False
        return btn.is_enabled()
    
    def click_generate_protection_changes(self) -> None:
        """Click the Generate Protection Changes button."""
        btn = self.page.locator(self.GENERATE_BUTTON)
        if btn.count() > 0:
            btn.click()
    
    def wait_for_generate_complete(self, timeout: int = 30000) -> None:
        """Wait for generate process to complete."""
        self.wait_for_element(self.STREAMING_OUTPUT, timeout=timeout)
        
        self.page.wait_for_function(
            """() => {
                const output = document.querySelector('.streaming-output, pre.output');
                if (!output) return false;
                const text = output.textContent || '';
                return text.includes('Complete') || text.includes('Done');
            }""",
            timeout=timeout,
        )
    
    def get_generate_output(self) -> str:
        """Get the generate output text."""
        output = self.page.locator(self.STREAMING_OUTPUT)
        if output.count() > 0:
            return output.text_content() or ""
        return ""
    
    # =========================================================================
    # Cascade Dialog
    # =========================================================================
    
    def is_cascade_dialog_visible(self) -> bool:
        """Check if cascade dialog is showing."""
        dialog = self.page.locator(self.CASCADE_DIALOG)
        return dialog.count() > 0 and dialog.is_visible()
    
    def get_cascade_children(self) -> List[str]:
        """Get child resources shown in cascade dialog.
        
        Returns:
            List of child resource keys
        """
        dialog = self.page.locator(self.CASCADE_DIALOG)
        if dialog.count() == 0:
            return []
        
        text = dialog.text_content() or ""
        children = []
        
        for prefix in ["ENV:", "JOB:", "REPO:"]:
            start = 0
            while True:
                idx = text.find(prefix, start)
                if idx == -1:
                    break
                end = idx
                while end < len(text) and text[end] not in " \n\t,":
                    end += 1
                key = text[idx:end].strip()
                if key:
                    children.append(key)
                start = end
        
        return children
    
    def confirm_cascade_unprotect(self) -> None:
        """Confirm cascading unprotection."""
        dialog = self.page.locator(self.CASCADE_DIALOG)
        if dialog.count() > 0:
            confirm = dialog.locator("button:has-text('Confirm'), button:has-text('Unprotect All')")
            if confirm.count() > 0:
                confirm.first.click()
                self.wait_for_loading_complete()
    
    def cancel_cascade(self) -> None:
        """Cancel cascade operation."""
        dialog = self.page.locator(self.CASCADE_DIALOG)
        if dialog.count() > 0:
            cancel = dialog.locator("button:has-text('Cancel')")
            if cancel.count() > 0:
                cancel.click()
    
    # =========================================================================
    # Destroy Actions
    # =========================================================================
    
    def is_destroy_button_enabled(self) -> bool:
        """Check if the Destroy button is enabled."""
        btn = self.page.locator(self.DESTROY_BUTTON)
        if btn.count() == 0:
            return False
        return btn.is_enabled()
    
    def click_destroy(self) -> None:
        """Click the Destroy button."""
        btn = self.page.locator(self.DESTROY_BUTTON)
        if btn.count() > 0:
            btn.click()
    
    def is_destroy_confirmation_visible(self) -> bool:
        """Check if destroy confirmation dialog is showing."""
        dialog = self.page.locator(self.DESTROY_CONFIRM_DIALOG)
        return dialog.count() > 0 and dialog.is_visible()
    
    def confirm_destroy(self, confirm_text: str = "DESTROY") -> None:
        """Confirm destruction by typing confirmation text.
        
        Args:
            confirm_text: Text to type for confirmation (usually "DESTROY")
        """
        input_field = self.page.locator(self.CONFIRM_DESTROY_INPUT)
        if input_field.count() > 0:
            input_field.fill(confirm_text)
        
        confirm_btn = self.page.locator(self.CONFIRM_DESTROY_BUTTON)
        if confirm_btn.count() > 0 and confirm_btn.is_enabled():
            confirm_btn.click()
    
    def cancel_destroy(self) -> None:
        """Cancel the destroy operation."""
        dialog = self.page.locator(self.DESTROY_CONFIRM_DIALOG)
        if dialog.count() > 0:
            cancel = dialog.locator("button:has-text('Cancel')")
            if cancel.count() > 0:
                cancel.click()
    
    # =========================================================================
    # Warnings
    # =========================================================================
    
    def has_protected_resource_warning(self) -> bool:
        """Check if there's a warning about protected resources."""
        warning = self.page.locator(self.PROTECTED_WARNING)
        return warning.count() > 0 and warning.is_visible()
    
    def get_protected_warning_text(self) -> str:
        """Get the text of the protected resource warning."""
        warning = self.page.locator(self.PROTECTED_WARNING)
        if warning.count() > 0:
            return warning.text_content() or ""
        return ""
    
    # =========================================================================
    # Assertions
    # =========================================================================
    
    def assert_resource_protected(self, key: str) -> None:
        """Assert a resource is protected."""
        status = self.get_resource_protection_status(key)
        assert status == "protected", f"Expected {key} to be protected, got {status}"
    
    def assert_resource_unprotected(self, key: str) -> None:
        """Assert a resource is unprotected (can be destroyed)."""
        status = self.get_resource_protection_status(key)
        assert status == "unprotected", f"Expected {key} to be unprotected, got {status}"
    
    def assert_resource_pending_generate(self, key: str) -> None:
        """Assert a resource has pending generate status."""
        status = self.get_resource_protection_status(key)
        assert status == "pending-generate", f"Expected {key} pending-generate, got {status}"
    
    def assert_destroy_blocked_by_protection(self) -> None:
        """Assert that destroy is blocked due to protected resources."""
        assert self.has_protected_resource_warning(), "Expected protected resource warning"
        # Or destroy button should be disabled
        assert not self.is_destroy_button_enabled() or self.has_protected_resource_warning()
    
    def assert_generate_button_visible(self) -> None:
        """Assert the Generate button is visible."""
        assert self.is_generate_button_visible(), "Generate button should be visible"
    
    def assert_page_loads_without_error(self) -> None:
        """Assert the page loads successfully."""
        self.wait_for_page_load()
        page_content = self.get_page_content()
        assert "500" not in page_content, "Page returned 500 error"
        assert "Internal Server Error" not in page_content
