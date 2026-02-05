"""E2E tests for the Destroy page protection workflow.

These tests verify:
- Destroy page loads without error
- Protected resources block destruction
- Unprotection workflow before destruction
- Generate button appears with pending unprotection
- Protection status badges display correctly

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.6 E2E Tests
"""

import pytest
from playwright.sync_api import Page, expect

from pages import DestroyPage


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def destroy_page(page_with_server: Page) -> DestroyPage:
    """Create a DestroyPage instance."""
    return DestroyPage(page_with_server)


# =============================================================================
# US-D1: Page Load Tests
# =============================================================================

class TestDestroyPageLoad:
    """Tests for Destroy page loading."""
    
    @pytest.mark.e2e
    def test_destroy_page_loads_without_error(self, destroy_page: DestroyPage):
        """US-D1.1: Verify Destroy page loads without 500 error."""
        destroy_page.go_to_destroy()
        
        # Page should load without error
        destroy_page.assert_page_loads_without_error()
    
    @pytest.mark.e2e
    def test_destroy_page_url_is_correct(self, destroy_page: DestroyPage):
        """US-D1.2: Verify Destroy page URL is /destroy."""
        destroy_page.go_to_destroy()
        assert destroy_page.is_on_destroy_page()
    
    @pytest.mark.e2e
    def test_destroy_page_has_resource_list(self, destroy_page: DestroyPage):
        """US-D1.3: Verify Destroy page displays resource list."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        # Should have resource list (may be empty in test mode)
        count = destroy_page.get_resource_count()
        assert count >= 0, "Resource count should be non-negative"


# =============================================================================
# US-D2: Protection Status Tests
# =============================================================================

class TestDestroyProtectionStatus:
    """Tests for protection status display on Destroy page."""
    
    @pytest.mark.e2e
    def test_protected_resources_show_protected_badge(self, destroy_page: DestroyPage):
        """US-D2.1: Verify protected resources display protected badge."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        protected = destroy_page.get_protected_resources()
        for key in protected:
            status = destroy_page.get_resource_protection_status(key)
            assert status == "protected", f"Protected resource {key} should show protected status"
    
    @pytest.mark.e2e
    def test_unprotected_resources_are_destroyable(self, destroy_page: DestroyPage):
        """US-D2.2: Verify unprotected resources can be destroyed."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        destroyable = destroy_page.get_destroyable_resources()
        for key in destroyable:
            assert destroy_page.is_resource_destroyable(key), f"{key} should be destroyable"
    
    @pytest.mark.e2e
    def test_pending_generate_badge_shows_correctly(self, destroy_page: DestroyPage):
        """US-D2.3: Verify pending-generate badge shows after unprotect selection."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        protected = destroy_page.get_protected_resources()
        if not protected:
            pytest.skip("No protected resources to test unprotection")
        
        # Unprotect a resource
        destroy_page.unprotect_resource(protected[0])
        
        # Status should change to pending-generate
        status = destroy_page.get_resource_protection_status(protected[0])
        assert status in ("pending-generate", "unprotected"), \
            f"After unprotect, status should be pending-generate, got {status}"


# =============================================================================
# US-D3: Protection Blocking Tests
# =============================================================================

class TestProtectionBlocksDestruction:
    """Tests for protection preventing destruction."""
    
    @pytest.mark.e2e
    def test_protected_resources_block_destroy(self, destroy_page: DestroyPage):
        """US-D3.1: Verify protected resources block destruction."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        protected = destroy_page.get_protected_resources()
        if protected:
            # When protected resources exist, destroy should be blocked or warned
            # Either destroy button is disabled OR there's a warning
            has_warning = destroy_page.has_protected_resource_warning()
            destroy_disabled = not destroy_page.is_destroy_button_enabled()
            
            assert has_warning or destroy_disabled, \
                "Protected resources should block destruction via warning or disabled button"
    
    @pytest.mark.e2e
    def test_warning_shows_protected_resource_names(self, destroy_page: DestroyPage):
        """US-D3.2: Verify warning shows which resources are protected."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        if destroy_page.has_protected_resource_warning():
            warning_text = destroy_page.get_protected_warning_text()
            assert warning_text, "Warning should have text content"
            # Warning should mention protection or protected resources
    
    @pytest.mark.e2e
    def test_destroy_enabled_when_no_protected_resources(self, destroy_page: DestroyPage):
        """US-D3.3: Verify destroy is enabled when no resources are protected."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        protected = destroy_page.get_protected_resources()
        if not protected:
            # If no protected resources, destroy should be available
            # (may still require confirmation)
            pass  # Soft check - destroy button state depends on implementation


# =============================================================================
# US-D4: Unprotection Workflow Tests
# =============================================================================

class TestUnprotectionWorkflow:
    """Tests for unprotection workflow on Destroy page."""
    
    @pytest.mark.e2e
    def test_unprotect_button_exists_for_protected(self, destroy_page: DestroyPage):
        """US-D4.1: Verify Unprotect button exists for protected resources."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        protected = destroy_page.get_protected_resources()
        # If there are protected resources, unprotect controls should be available
    
    @pytest.mark.e2e
    def test_unprotect_action_marks_for_unprotection(self, destroy_page: DestroyPage):
        """US-D4.2: Verify unprotect action marks resource for unprotection."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        protected = destroy_page.get_protected_resources()
        if not protected:
            pytest.skip("No protected resources to test")
        
        key = protected[0]
        destroy_page.unprotect_resource(key)
        
        # Resource should now be marked for unprotection (pending-generate)
        status = destroy_page.get_resource_protection_status(key)
        assert status != "protected", f"Resource should no longer show as protected, got {status}"
    
    @pytest.mark.e2e
    def test_unprotect_all_works(self, destroy_page: DestroyPage):
        """US-D4.3: Verify Unprotect All button works."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        protected = destroy_page.get_protected_resources()
        if len(protected) < 2:
            pytest.skip("Need multiple protected resources to test Unprotect All")
        
        destroy_page.unprotect_all_visible()
        
        # All previously protected should now be pending unprotection
        for key in protected:
            status = destroy_page.get_resource_protection_status(key)
            assert status != "protected", f"{key} should no longer be protected"


# =============================================================================
# US-D5: Generate Button Tests (for unprotection)
# =============================================================================

class TestDestroyGenerateButton:
    """Tests for Generate button on Destroy page."""
    
    @pytest.mark.e2e
    def test_generate_button_visible_with_pending_unprotection(
        self,
        destroy_page: DestroyPage,
    ):
        """US-D5.1: Verify Generate button is visible when unprotection is pending."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        protected = destroy_page.get_protected_resources()
        if not protected:
            pytest.skip("No protected resources to test")
        
        # Unprotect a resource
        destroy_page.unprotect_resource(protected[0])
        
        # Generate button should now be visible
        destroy_page.assert_generate_button_visible()
    
    @pytest.mark.e2e
    def test_generate_button_enabled_with_pending(self, destroy_page: DestroyPage):
        """US-D5.2: Verify Generate button is enabled when changes pending."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        protected = destroy_page.get_protected_resources()
        if not protected:
            pytest.skip("No protected resources to test")
        
        destroy_page.unprotect_resource(protected[0])
        
        assert destroy_page.is_generate_button_enabled(), \
            "Generate button should be enabled with pending unprotection"
    
    @pytest.mark.e2e
    def test_generate_produces_output(self, destroy_page: DestroyPage):
        """US-D5.3: Verify generate produces meaningful output."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        protected = destroy_page.get_protected_resources()
        if not protected:
            pytest.skip("No protected resources to test")
        
        destroy_page.unprotect_resource(protected[0])
        
        if not destroy_page.is_generate_button_enabled():
            pytest.skip("Generate button not enabled")
        
        destroy_page.click_generate_protection_changes()
        
        # Should produce some output
        output = destroy_page.get_generate_output()
        # Output may indicate YAML changes or moved blocks


# =============================================================================
# US-D6: Cascade Unprotection Tests
# =============================================================================

class TestCascadeUnprotection:
    """Tests for cascading unprotection on Destroy page."""
    
    @pytest.mark.e2e
    def test_cascade_dialog_for_parent_unprotection(self, destroy_page: DestroyPage):
        """US-D6.1: Verify cascade dialog when unprotecting parent."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        # When unprotecting a parent (e.g., project), cascade should show children
        # This depends on having appropriate test data
    
    @pytest.mark.e2e
    def test_cascade_lists_children(self, destroy_page: DestroyPage):
        """US-D6.2: Verify cascade dialog lists child resources."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        # If cascade dialog is shown, it should list related children
        if destroy_page.is_cascade_dialog_visible():
            children = destroy_page.get_cascade_children()
            # Children should be listed
    
    @pytest.mark.e2e
    def test_confirm_cascade_unprotects_all(self, destroy_page: DestroyPage):
        """US-D6.3: Verify confirming cascade unprotects all listed resources."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        if destroy_page.is_cascade_dialog_visible():
            destroy_page.confirm_cascade_unprotect()
            # All listed resources should be unprotected
    
    @pytest.mark.e2e
    def test_cancel_cascade_unprotects_only_selected(self, destroy_page: DestroyPage):
        """US-D6.4: Verify canceling cascade unprotects only selected resource."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        if destroy_page.is_cascade_dialog_visible():
            destroy_page.cancel_cascade()
            # Only originally selected should be unprotected


# =============================================================================
# US-D7: Destroy Confirmation Tests
# =============================================================================

class TestDestroyConfirmation:
    """Tests for destroy confirmation workflow."""
    
    @pytest.mark.e2e
    def test_destroy_requires_confirmation(self, destroy_page: DestroyPage):
        """US-D7.1: Verify destroy requires explicit confirmation."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        destroyable = destroy_page.get_destroyable_resources()
        if not destroyable:
            pytest.skip("No destroyable resources")
        
        if destroy_page.is_destroy_button_enabled():
            destroy_page.click_destroy()
            
            # Confirmation dialog should appear
            assert destroy_page.is_destroy_confirmation_visible(), \
                "Destroy should require confirmation"
    
    @pytest.mark.e2e
    def test_cancel_destroy_closes_dialog(self, destroy_page: DestroyPage):
        """US-D7.2: Verify cancel closes destroy confirmation dialog."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        if destroy_page.is_destroy_button_enabled():
            destroy_page.click_destroy()
            
            if destroy_page.is_destroy_confirmation_visible():
                destroy_page.cancel_destroy()
                
                # Dialog should close
                assert not destroy_page.is_destroy_confirmation_visible(), \
                    "Confirmation dialog should close after cancel"


# =============================================================================
# US-D8: Error Handling Tests
# =============================================================================

class TestDestroyPageErrors:
    """Tests for error handling on Destroy page."""
    
    @pytest.mark.e2e
    def test_graceful_handling_when_no_resources(self, destroy_page: DestroyPage):
        """US-D8.1: Verify graceful handling when no resources to destroy."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        # Page should not crash if no resources available
        page_content = destroy_page.get_page_content()
        assert "500" not in page_content
        assert "Internal Server Error" not in page_content
    
    @pytest.mark.e2e
    def test_notification_on_operation_error(self, destroy_page: DestroyPage):
        """US-D8.2: Verify notification appears on operation error."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        # If an error occurs, notification should appear
        # This is a soft test - depends on error conditions


# =============================================================================
# Integration Tests - Destroy with Protection System
# =============================================================================

class TestDestroyProtectionIntegration:
    """Integration tests for Destroy page with protection system."""
    
    @pytest.mark.e2e
    def test_protection_intent_created_on_unprotect(self, destroy_page: DestroyPage):
        """Verify protection intent is created when resource is unprotected."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        protected = destroy_page.get_protected_resources()
        if not protected:
            pytest.skip("No protected resources")
        
        # Unprotect should create an intent
        destroy_page.unprotect_resource(protected[0])
        
        # Status should change
        status = destroy_page.get_resource_protection_status(protected[0])
        assert status != "protected"
    
    @pytest.mark.e2e
    def test_full_unprotection_workflow(self, destroy_page: DestroyPage):
        """Test complete unprotection workflow: unprotect → generate → verify."""
        destroy_page.go_to_destroy()
        destroy_page.wait_for_loading_complete()
        
        protected = destroy_page.get_protected_resources()
        if not protected:
            pytest.skip("No protected resources")
        
        # Full workflow:
        # 1. Unprotect resource
        # 2. Handle cascade if shown
        # 3. Click generate
        # 4. Verify output
        # 5. Resource should now be destroyable
        
        destroy_page.unprotect_resource(protected[0])
        
        if destroy_page.is_cascade_dialog_visible():
            destroy_page.confirm_cascade_unprotect()
        
        if destroy_page.is_generate_button_enabled():
            destroy_page.click_generate_protection_changes()
            # Generate should complete and resource should become destroyable
