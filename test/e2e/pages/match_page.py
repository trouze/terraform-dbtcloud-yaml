"""Page Object for Match page.

The Match page is the primary workflow page where users:
- Match source resources to target configurations
- Select resources for protection during import
- Generate protection changes with cascading support
- View protection status badges

This is the "working" reference implementation for protection workflow.

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.4
"""

from typing import List, Optional, Dict, Any
from playwright.sync_api import Page, Locator, expect

from .base_page import BasePage


class MatchPage(BasePage):
    """Page Object for the Match page (/match)."""
    
    PATH = "/match"
    
    # Resource selectors
    RESOURCE_LIST = ".resource-list, .match-list"
    RESOURCE_ITEM = ".resource-item, .match-item"
    SOURCE_PANEL = ".source-panel, [data-panel='source']"
    TARGET_PANEL = ".target-panel, [data-panel='target']"
    
    # Protection controls
    PROTECT_CHECKBOX = "input[type='checkbox'][name*='protect'], .protect-checkbox"
    PROTECTION_PANEL = ".protection-panel, [data-section='protection']"
    PROTECTION_BADGE = ".protection-badge"
    
    # Action buttons
    GENERATE_BUTTON = "button:has-text('Generate Protection')"
    GENERATE_ALL_BUTTON = "button:has-text('Generate All')"
    IMPORT_BUTTON = "button:has-text('Import')"
    NEXT_STEP_BUTTON = "button:has-text('Next')"
    
    # Status indicators
    PENDING_BADGE = ".pending-badge, [class*='pending']"
    APPLIED_BADGE = ".applied-badge, [class*='applied']"
    MISMATCH_INDICATOR = ".mismatch-indicator, [class*='mismatch']"
    
    # Dialogs
    CASCADE_DIALOG = ".q-dialog:has-text('cascade')"
    GENERATE_DIALOG = ".q-dialog:has-text('Generating')"
    STREAMING_OUTPUT = ".streaming-output, pre.output, .terminal-output"
    
    def __init__(self, page: Page, base_url: str = "http://127.0.0.1:8080"):
        super().__init__(page, base_url)
    
    # =========================================================================
    # Navigation
    # =========================================================================
    
    def go_to_match(self) -> None:
        """Navigate to the match page."""
        self.navigate(self.PATH)
    
    def is_on_match_page(self) -> bool:
        """Check if currently on the match page."""
        return self.PATH in self.get_current_path()
    
    def navigate_to_protection_management(self) -> None:
        """Navigate from match page to protection management."""
        # Look for link to protection management
        link = self.page.locator("a:has-text('Protection'), a[href*='protection']")
        if link.count() > 0:
            link.first.click()
            self.wait_for_page_load()
    
    # =========================================================================
    # Resource List
    # =========================================================================
    
    def get_resource_items(self) -> List[Locator]:
        """Get all resource item locators.
        
        Returns:
            List of resource item locators
        """
        self.wait_for_loading_complete()
        return self.page.locator(self.RESOURCE_ITEM).all()
    
    def get_resource_count(self) -> int:
        """Get the number of resources in the list.
        
        Returns:
            Number of resources
        """
        return len(self.get_resource_items())
    
    def find_resource_by_name(self, name: str) -> Optional[Locator]:
        """Find a resource item by name.
        
        Args:
            name: Resource name to find
            
        Returns:
            Locator for the resource, or None
        """
        item = self.page.locator(f'{self.RESOURCE_ITEM}:has-text("{name}")')
        if item.count() > 0:
            return item.first
        return None
    
    def find_resource_by_key(self, key: str) -> Optional[Locator]:
        """Find a resource item by key.
        
        Args:
            key: Resource key (e.g., "PRJ:my_project")
            
        Returns:
            Locator for the resource, or None
        """
        # Try data attribute
        item = self.page.locator(f'{self.RESOURCE_ITEM}[data-key="{key}"]')
        if item.count() > 0:
            return item.first
        
        # Try text content
        item = self.page.locator(f'{self.RESOURCE_ITEM}:has-text("{key}")')
        if item.count() > 0:
            return item.first
        
        return None
    
    # =========================================================================
    # Protection Actions
    # =========================================================================
    
    def is_resource_selected_for_protection(self, key: str) -> bool:
        """Check if a resource is selected for protection.
        
        Args:
            key: Resource key
            
        Returns:
            True if selected for protection
        """
        item = self.find_resource_by_key(key)
        if not item:
            return False
        
        checkbox = item.locator(self.PROTECT_CHECKBOX)
        if checkbox.count() > 0:
            return checkbox.is_checked()
        
        return False
    
    def select_for_protection(self, key: str) -> None:
        """Select a resource for protection.
        
        Args:
            key: Resource key to select
        """
        item = self.find_resource_by_key(key)
        if item:
            checkbox = item.locator(self.PROTECT_CHECKBOX)
            if checkbox.count() > 0 and not checkbox.is_checked():
                checkbox.click()
                self.wait_for_loading_complete()
    
    def deselect_for_protection(self, key: str) -> None:
        """Deselect a resource for protection.
        
        Args:
            key: Resource key to deselect
        """
        item = self.find_resource_by_key(key)
        if item:
            checkbox = item.locator(self.PROTECT_CHECKBOX)
            if checkbox.count() > 0 and checkbox.is_checked():
                checkbox.click()
                self.wait_for_loading_complete()
    
    def get_protection_badge_status(self, key: str) -> Optional[str]:
        """Get the protection badge status for a resource.
        
        Args:
            key: Resource key
            
        Returns:
            Badge status: "pending", "applied", "mismatch", or None
        """
        item = self.find_resource_by_key(key)
        if not item:
            return None
        
        if item.locator(self.MISMATCH_INDICATOR).count() > 0:
            return "mismatch"
        elif item.locator(self.PENDING_BADGE).count() > 0:
            return "pending"
        elif item.locator(self.APPLIED_BADGE).count() > 0:
            return "applied"
        
        return None
    
    # =========================================================================
    # Cascading Protection
    # =========================================================================
    
    def is_cascade_dialog_visible(self) -> bool:
        """Check if the cascade dialog is showing."""
        dialog = self.page.locator(self.CASCADE_DIALOG)
        return dialog.count() > 0 and dialog.is_visible()
    
    def get_cascade_dialog_resources(self) -> List[str]:
        """Get resources listed in the cascade dialog.
        
        Returns:
            List of resource keys/names shown in cascade
        """
        dialog = self.page.locator(self.CASCADE_DIALOG)
        if dialog.count() == 0:
            return []
        
        # Extract resource mentions from dialog text
        text = dialog.text_content() or ""
        resources = []
        
        for prefix in ["PRJ:", "REPO:", "ENV:", "JOB:"]:
            start = 0
            while True:
                idx = text.find(prefix, start)
                if idx == -1:
                    break
                # Find end of key (space or end of line)
                end = idx
                while end < len(text) and text[end] not in " \n\t,":
                    end += 1
                key = text[idx:end].strip()
                if key:
                    resources.append(key)
                start = end
        
        return resources
    
    def confirm_cascade_protection(self) -> None:
        """Confirm cascading protection in the dialog."""
        dialog = self.page.locator(self.CASCADE_DIALOG)
        if dialog.count() > 0:
            confirm = dialog.locator("button:has-text('Confirm'), button:has-text('Protect All')")
            if confirm.count() > 0:
                confirm.first.click()
                self.wait_for_loading_complete()
    
    def cancel_cascade_protection(self) -> None:
        """Cancel cascading protection."""
        dialog = self.page.locator(self.CASCADE_DIALOG)
        if dialog.count() > 0:
            cancel = dialog.locator("button:has-text('Cancel'), button:has-text('No')")
            if cancel.count() > 0:
                cancel.first.click()
    
    def protect_only_selected(self) -> None:
        """In cascade dialog, protect only the selected resource."""
        dialog = self.page.locator(self.CASCADE_DIALOG)
        if dialog.count() > 0:
            only_selected = dialog.locator("button:has-text('Only Selected')")
            if only_selected.count() > 0:
                only_selected.click()
                self.wait_for_loading_complete()
    
    # =========================================================================
    # Generate Workflow
    # =========================================================================
    
    def click_generate_protection(self) -> None:
        """Click the Generate Protection button."""
        btn = self.page.locator(self.GENERATE_BUTTON)
        if btn.count() > 0:
            btn.click()
    
    def is_generate_button_enabled(self) -> bool:
        """Check if the Generate button is enabled."""
        btn = self.page.locator(self.GENERATE_BUTTON)
        if btn.count() == 0:
            return False
        return btn.is_enabled()
    
    def wait_for_generate_dialog(self) -> Locator:
        """Wait for generate dialog to appear."""
        return self.wait_for_element(self.GENERATE_DIALOG)
    
    def wait_for_generate_complete(self, timeout: int = 30000) -> None:
        """Wait for generate process to complete.
        
        Args:
            timeout: Maximum wait time in ms
        """
        # Wait for streaming output
        self.wait_for_element(self.STREAMING_OUTPUT, timeout=timeout)
        
        # Wait for completion
        self.page.wait_for_function(
            """() => {
                const output = document.querySelector('.streaming-output, pre.output');
                if (!output) return false;
                const text = output.textContent || '';
                return text.includes('Complete') || text.includes('Done') || text.includes('✓');
            }""",
            timeout=timeout,
        )
    
    def get_generate_output(self) -> str:
        """Get the output from generate dialog."""
        output = self.page.locator(self.STREAMING_OUTPUT)
        if output.count() > 0:
            return output.text_content() or ""
        return ""
    
    def close_generate_dialog(self) -> None:
        """Close the generate dialog."""
        self.close_dialog()
    
    # =========================================================================
    # Assertions
    # =========================================================================
    
    def assert_resource_has_pending_badge(self, key: str) -> None:
        """Assert a resource shows pending badge."""
        status = self.get_protection_badge_status(key)
        assert status == "pending", f"Expected pending badge for {key}, got {status}"
    
    def assert_resource_has_applied_badge(self, key: str) -> None:
        """Assert a resource shows applied badge."""
        status = self.get_protection_badge_status(key)
        assert status == "applied", f"Expected applied badge for {key}, got {status}"
    
    def assert_cascade_shows_parents(self, expected_parents: List[str]) -> None:
        """Assert cascade dialog shows expected parent resources.
        
        Args:
            expected_parents: List of parent keys expected in cascade
        """
        cascade_resources = self.get_cascade_dialog_resources()
        for parent in expected_parents:
            assert parent in cascade_resources, \
                f"Expected parent {parent} in cascade dialog, got {cascade_resources}"
    
    def assert_generate_output_contains(self, text: str) -> None:
        """Assert generate output contains specific text.
        
        Args:
            text: Expected text in output
        """
        output = self.get_generate_output()
        assert text in output, f"Expected '{text}' in generate output, got: {output[:200]}"
