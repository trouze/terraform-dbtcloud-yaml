"""Page Object for Adopt page.

The Adopt page sits between Match and Configure in the Migration workflow.
Users can:
- Review resources to adopt into Terraform state
- Toggle adopt/ignore per resource
- Toggle protection (shield) per resource
- Confirm adoption+protection for ignored resources via dialog
- Run Plan Adoption / Apply Adoption
- View plan output and execution logs

Reference: PRD 43.02-Adoption-Terraform-Step.md
"""

from typing import List, Optional
from playwright.sync_api import Page, Locator, expect

from .base_page import BasePage


class AdoptPage(BasePage):
    """Page Object for the Adopt page (/adopt)."""

    PATH = "/adopt"

    # ── Selectors ─────────────────────────────────────────────────────────
    # AG Grid
    AG_GRID = ".adopt-grid"
    AG_ROW = ".adopt-grid .ag-row"
    AG_CELL = ".adopt-grid .ag-cell"

    # Summary card
    SUMMARY_CARD = ".q-card"
    SUMMARY_TITLE = "text=Adoption Summary"
    ADOPT_COUNT = "text=Resources to Import"
    PROTECTED_COUNT = "text=Protected"
    STATE_RM_COUNT = "text=Need State RM"

    # Alternative states
    NOTHING_TO_ADOPT = "text=Nothing to adopt"
    ADOPTION_COMPLETE = "text=Adoption Complete"

    # Dialogs
    PROTECTION_DIALOG = ".q-dialog:has-text('Protection Requires Adoption')"
    PLAN_VIEWER_DIALOG = ".q-dialog:has-text('Adoption Plan')"
    OUTPUT_VIEWER_DIALOG = ".q-dialog:has-text('Adoption Output')"
    DETAIL_DIALOG = ".q-dialog:has-text('Resource Detail')"

    # Terminal / Execution log
    TERMINAL_OUTPUT = ".terminal-output, pre.output"

    def __init__(self, page: Page, base_url: str = "http://127.0.0.1:8080"):
        super().__init__(page, base_url)

    # =====================================================================
    # Navigation
    # =====================================================================

    def go_to_adopt(self) -> None:
        """Navigate to the adopt page."""
        self.navigate(self.PATH)

    def is_on_adopt_page(self) -> bool:
        """Check if currently on the adopt page."""
        return self.PATH in self.get_current_path()

    # =====================================================================
    # Page State Checks
    # =====================================================================

    def has_nothing_to_adopt(self) -> bool:
        """Check if the 'Nothing to adopt' message is displayed."""
        loc = self.page.locator(self.NOTHING_TO_ADOPT)
        return loc.count() > 0 and loc.is_visible()

    def is_adoption_complete(self) -> bool:
        """Check if the 'Adoption Complete' message is displayed."""
        loc = self.page.locator(self.ADOPTION_COMPLETE)
        return loc.count() > 0 and loc.is_visible()

    def has_adopt_grid(self) -> bool:
        """Check if the AG Grid is present."""
        loc = self.page.locator(self.AG_GRID)
        return loc.count() > 0 and loc.is_visible()

    def assert_page_loads_without_error(self) -> None:
        """Assert the Adopt page loads without 500 errors."""
        self.assert_page_has_no_server_error()

    # =====================================================================
    # Summary Card
    # =====================================================================

    def get_adopt_count_text(self) -> str:
        """Get the 'Resources to Import' counter text (the big number)."""
        # The counter is a label above "Resources to Import"
        parent = self.page.locator(self.ADOPT_COUNT).locator("..")
        big_number = parent.locator(".text-3xl")
        if big_number.count() > 0:
            return big_number.text_content() or "0"
        return "0"

    def get_protected_count_text(self) -> str:
        """Get the 'Protected' counter text."""
        parent = self.page.locator(self.PROTECTED_COUNT).locator("..")
        big_number = parent.locator(".text-3xl")
        if big_number.count() > 0:
            return big_number.text_content() or "0"
        return "0"

    def get_summary_badge_text(self) -> str:
        """Get the summary badge below the grid (e.g. '3 to adopt, 2 ignored')."""
        badge = self.page.locator("text=/\\d+ to adopt/")
        if badge.count() > 0:
            return badge.first.text_content() or ""
        return ""

    # =====================================================================
    # AG Grid Interaction
    # =====================================================================

    def get_grid_row_count(self) -> int:
        """Count the number of rows in the adopt grid."""
        rows = self.page.locator(self.AG_ROW)
        return sum(1 for i in range(rows.count()) if rows.nth(i).is_visible())

    def get_grid_rows(self) -> List[Locator]:
        """Get all row locators from the adopt grid."""
        rows = self.page.locator(self.AG_ROW)
        return [rows.nth(i) for i in range(rows.count()) if rows.nth(i).is_visible()]

    def find_row_by_name(self, name: str) -> Optional[Locator]:
        """Find a grid row by resource name.

        Args:
            name: Resource name to find (text in the Name column)

        Returns:
            Locator for the row, or None
        """
        row = self.page.locator(f'{self.AG_ROW}:has-text("{name}")')
        if row.count() > 0:
            return row.first
        return None

    def get_row_action(self, row: Locator) -> str:
        """Get the action value for a grid row.

        Args:
            row: Locator for the row

        Returns:
            Action text (e.g. 'Adopt', 'Ignore')
        """
        action_cell = row.locator('[col-id="action"]')
        return action_cell.text_content() or ""

    def get_row_protection_status(self, row: Locator) -> bool:
        """Check if a row shows the blue shield (protected).

        Args:
            row: Locator for the row

        Returns:
            True if the shield emoji is present (protected)
        """
        shield_cell = row.locator('[col-id="protected"]')
        text = shield_cell.text_content() or ""
        return "🛡" in text

    def click_shield(self, row: Locator) -> None:
        """Click the shield/protection cell in a row.

        Args:
            row: Locator for the row
        """
        shield_cell = row.locator('[col-id="protected"]')
        shield_cell.scroll_into_view_if_needed()

        clickable_selectors = [
            "button",
            "[role='button']",
            ".q-btn",
            "span:has-text('🛡')",
            "span:has-text('⚪')",
            ".cursor-pointer",
            "svg",
        ]
        for selector in clickable_selectors:
            candidate = shield_cell.locator(selector)
            if candidate.count() > 0 and candidate.first.is_visible():
                candidate.first.click()
                self.page.wait_for_timeout(500)
                return

        shield_cell.first.click(force=True)
        self.page.wait_for_timeout(500)

    def click_details(self, row: Locator) -> None:
        """Click the details (magnifying glass) cell in a row.

        Args:
            row: Locator for the row
        """
        details_cell = row.locator('[col-id="details_btn"]')
        details_cell.click()
        self.page.wait_for_timeout(500)

    def set_row_action(self, row: Locator, action: str) -> None:
        """Set the action for a row by clicking the action cell and selecting.

        Args:
            row: Locator for the row
            action: "adopt" or "ignore"
        """
        action_cell = row.locator('[col-id="action"]')
        action_cell.click()
        self.page.wait_for_timeout(200)
        # The AG Grid select editor opens — click the option
        option = self.page.locator(f'.ag-rich-select-row:has-text("{action}")')
        if option.count() > 0:
            option.click()
        else:
            # Fallback: use keyboard to select
            self.page.keyboard.press("ArrowDown" if action == "ignore" else "ArrowUp")
            self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(300)

    # =====================================================================
    # Protection Dialog
    # =====================================================================

    def is_protection_dialog_visible(self) -> bool:
        """Check if the 'Protection Requires Adoption' dialog is showing."""
        dialog = self.page.locator(self.PROTECTION_DIALOG)
        return dialog.count() > 0 and dialog.is_visible()

    def wait_for_protection_dialog(self, timeout: int = 5000) -> Locator:
        """Wait for the protection dialog to appear."""
        return self.wait_for_element(self.PROTECTION_DIALOG, timeout=timeout)

    def confirm_adopt_and_protect(self) -> None:
        """Click 'Yes — Adopt & Protect' in the protection dialog."""
        dialog = self.page.locator(self.PROTECTION_DIALOG)
        yes_btn = dialog.locator("button:has-text('Yes')")
        if yes_btn.count() > 0:
            yes_btn.click()
            self.page.wait_for_timeout(500)

    def cancel_adopt_and_protect(self) -> None:
        """Click 'No' in the protection dialog."""
        dialog = self.page.locator(self.PROTECTION_DIALOG)
        no_btn = dialog.locator("button:has-text('No')")
        if no_btn.count() > 0:
            no_btn.click()
            self.page.wait_for_timeout(500)

    def get_protection_dialog_text(self) -> str:
        """Get the text content of the protection dialog."""
        dialog = self.page.locator(self.PROTECTION_DIALOG)
        if dialog.count() > 0:
            return dialog.text_content() or ""
        return ""

    # =====================================================================
    # Action Buttons
    # =====================================================================

    def click_back_to_match(self) -> None:
        """Click the 'Back to Match' button."""
        self.click_button("Back to Match")

    def click_plan_adoption(self) -> None:
        """Click the 'Plan Adoption' button."""
        self.click_button("Plan Adoption")

    def click_apply_adoption(self) -> None:
        """Click the 'Apply Adoption' button."""
        self.click_button("Apply Adoption")

    def click_view_plan(self) -> None:
        """Click the 'View Plan' button."""
        self.click_button("View Plan")

    def click_view_output(self) -> None:
        """Click the 'View Output' button."""
        self.click_button("View Output")

    def click_skip(self) -> None:
        """Click the 'Skip' button."""
        btn = self.page.locator("button:has-text('Skip')")
        if btn.count() > 0:
            btn.first.click()

    def click_continue_to_configure(self) -> None:
        """Click the 'Continue to Configure' button."""
        self.click_button("Continue to Configure")

    def is_plan_button_visible(self) -> bool:
        """Check if the 'Plan Adoption' button is visible."""
        btn = self.page.locator("button:has-text('Plan Adoption')")
        return btn.count() > 0 and btn.is_visible()

    def is_apply_button_visible(self) -> bool:
        """Check if the 'Apply Adoption' button is visible."""
        btn = self.page.locator("button:has-text('Apply Adoption')")
        return btn.count() > 0 and btn.is_visible()

    def is_view_plan_button_visible(self) -> bool:
        """Check if the 'View Plan' button is visible."""
        btn = self.page.locator("button:has-text('View Plan')")
        return btn.count() > 0 and btn.is_visible()

    # =====================================================================
    # Plan & Output Viewers
    # =====================================================================

    def is_plan_viewer_visible(self) -> bool:
        """Check if the plan viewer dialog is open."""
        dialog = self.page.locator(self.PLAN_VIEWER_DIALOG)
        return dialog.count() > 0 and dialog.is_visible()

    def get_plan_viewer_text(self) -> str:
        """Get the text content of the plan viewer dialog."""
        dialog = self.page.locator(self.PLAN_VIEWER_DIALOG)
        if dialog.count() > 0:
            return dialog.text_content() or ""
        return ""

    def close_plan_viewer(self) -> None:
        """Close the plan viewer dialog."""
        dialog = self.page.locator(self.PLAN_VIEWER_DIALOG)
        if dialog.count() > 0:
            close_btn = dialog.locator("button:has-text('Close')")
            if close_btn.count() > 0:
                close_btn.click()
            else:
                self.page.keyboard.press("Escape")

    # =====================================================================
    # Assertions
    # =====================================================================

    def assert_on_adopt_page(self) -> None:
        """Assert we're on the adopt page."""
        assert self.is_on_adopt_page(), (
            f"Expected to be on {self.PATH}, but at {self.get_current_path()}"
        )

    def assert_grid_has_rows(self) -> None:
        """Assert the grid has at least one row."""
        count = self.get_grid_row_count()
        assert count > 0, "Expected at least one row in the adopt grid"

    def assert_adopt_count(self, expected: int) -> None:
        """Assert the adopt counter shows the expected value."""
        actual = self.get_adopt_count_text()
        assert actual == str(expected), (
            f"Expected adopt count {expected}, got {actual}"
        )

    def assert_protected_count(self, expected: int) -> None:
        """Assert the protected counter shows the expected value."""
        actual = self.get_protected_count_text()
        assert actual == str(expected), (
            f"Expected protected count {expected}, got {actual}"
        )

    def assert_protection_dialog_visible(self) -> None:
        """Assert the protection dialog is showing."""
        assert self.is_protection_dialog_visible(), (
            "Expected 'Protection Requires Adoption' dialog to be visible"
        )

    def assert_protection_dialog_hidden(self) -> None:
        """Assert the protection dialog is not showing."""
        dialog = self.page.locator(self.PROTECTION_DIALOG)
        assert dialog.count() == 0 or not dialog.is_visible(), (
            "Expected protection dialog to be hidden"
        )

    def assert_row_is_protected(self, row: Locator) -> None:
        """Assert a row shows the blue shield (protected)."""
        assert self.get_row_protection_status(row), "Expected row to be protected"

    def assert_row_is_not_protected(self, row: Locator) -> None:
        """Assert a row shows the gray circle (unprotected)."""
        assert not self.get_row_protection_status(row), (
            "Expected row to be unprotected"
        )

    def assert_plan_button_visible(self) -> None:
        """Assert Plan Adoption button is visible."""
        assert self.is_plan_button_visible(), (
            "Expected 'Plan Adoption' button to be visible"
        )

    def assert_apply_button_hidden(self) -> None:
        """Assert Apply Adoption button is hidden."""
        assert not self.is_apply_button_visible(), (
            "Expected 'Apply Adoption' button to be hidden"
        )
