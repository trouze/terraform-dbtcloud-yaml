# Release Notes v0.6.4

**Release Date:** 2025-12-20  
**Type:** Patch Release (Bug Fix)  
**Previous Version:** 0.6.3

---

## Summary

This patch release fixes Terraform validation errors for the notification resource by skipping ALL notifications during initial migration. The dbt Cloud provider requires `user_id` for all notification types, including external email, and source user IDs cannot be mapped to target user IDs.

---

## Bug Fix

### Skip All Notifications During Migration

**Problem:**
- v0.6.3 attempted to create external email notifications (type 4) with `user_id = null`
- Provider requires `user_id` even for external email notifications
- Provider documentation: "we still need the ID of a user in dbt Cloud even though it is not used for sending notifications"
- Terraform validation failed: "Missing Configuration for Required Attribute"

**Solution:**
- Changed `for_each` filter to `if false` to skip all notifications
- Added placeholder required fields to satisfy Terraform schema validation
- Notifications are still fetched and normalized (preserved for future migration mode)

**Files Changed:**
- `modules/projects_v2/globals.tf` - Updated notification resource filtering

---

## Technical Details

### Terraform Resource Configuration

```hcl
resource "dbtcloud_notification" "notifications" {
  # Skip all notifications during initial migration
  # The for_each is empty, so no notifications will be created
  for_each = {
    for notif in var.globals.notifications :
    notif.key => notif
    if false  # Skip all notifications - user_id mapping required
  }

  # Required fields (placeholder values - no instances will be created due to for_each = {})
  user_id           = 0  # Placeholder - never used since for_each is always empty
  notification_type = 1  # Type 1 (user email) - no external_email required
  state             = 1
}
```

### Why Placeholders Are Needed

Terraform validates the resource schema even when `for_each` evaluates to an empty set. The provider's schema marks `user_id` as required, so a value must be provided even though no instances will be created.

---

## Expected Behavior

### Before (v0.6.3)
- Attempted to create external email notifications with `user_id = null`
- Terraform validation failed: "Missing Configuration for Required Attribute"

### After (v0.6.4)
- All notifications are skipped during initial migration
- Terraform validation passes
- Notifications preserved in YAML for future `--migrate-notifications` mode

---

## Future Enhancement

A separate `--migrate-notifications` mode will be implemented to:
- Accept target account user ID mappings (source user ID → target user ID)
- Map source job IDs to target job IDs (after jobs are created)
- Detect and configure Slack integrations in target account
- Create notifications with valid target account references

---

## Upgrade Instructions

No action required. The update is backward compatible and automatically applied when using the updated Terraform module.

---

## Related Issues

- Provider requires `user_id` for all notification types
- See `dev_support/KNOWN_ISSUES.md` for notification migration limitations

