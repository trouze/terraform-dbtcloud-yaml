# Release Notes v0.6.3

**Release Date:** 2025-12-20  
**Type:** Patch Release (Bug Fix)  
**Previous Version:** 0.6.2

---

## Summary

This patch release fixes notification creation errors during cross-account migration by filtering out incompatible notifications. User-level notifications, Slack notifications, and job-linked notifications are now skipped during initial migration, while still being preserved in the YAML for future migration modes.

---

## Bug Fixes

### Notification Migration Filtering

**Problem:**
- Notifications with user IDs from source account failed: `User instance with id 103835 does not exist`
- Notifications with job IDs from source account failed: `Jobs definition IDs 526578, 542963, ... do not exist`
- Slack notifications require Slack integration setup in target account
- All 14 notification creation attempts were failing during Terraform apply

**Solution:**
- Added filtering in Terraform module to skip incompatible notifications
- Only external email notifications (type 4) without job references are created during initial migration
- All notifications are still fetched and normalized (preserved in YAML for future use)

**Notification Types:**
- **Type 1 (User Email)**: Skipped - source user IDs don't exist in target account
- **Type 2 (Slack)**: Skipped - requires Slack integration in target account
- **Type 4 (External Email)**: Created only if no job references (jobs not yet mapped)

**Files Changed:**
- `modules/projects_v2/globals.tf` - Added notification filtering logic
- `dev_support/KNOWN_ISSUES.md` - Documented notification migration limitations
- `dev_support/importer_implementation_status.md` - Added roadmap item for future notification migration mode

---

## Technical Details

### Terraform Filtering Logic

```hcl
for_each = {
  for notif in var.globals.notifications :
  notif.key => notif
  if (
    # Only external email notifications (type 4)
    try(notif.notification_type, 0) == 4 &&
    # Must have external email set
    try(notif.external_email, null) != null &&
    # Skip if has job references (jobs not yet mapped to target account)
    length(try(notif.on_success, [])) == 0 &&
    length(try(notif.on_failure, [])) == 0 &&
    length(try(notif.on_cancel, [])) == 0 &&
    length(try(notif.on_warning, [])) == 0
  )
}
```

### Key Changes

1. **Filter by Notification Type**: Only type 4 (external email) notifications are created
2. **Filter by Job References**: Notifications with job associations are skipped (jobs not yet mapped)
3. **Set user_id to null**: External email notifications don't require user_id (set to null)
4. **Preserve All Notifications**: All notifications are still fetched and normalized for future migration

---

## Expected Behavior

### Before (v0.6.2)
- 14 notification creation attempts
- All fail with user/job ID errors
- Terraform apply stops with errors

### After (v0.6.3)
- 0 notifications created (all filtered out due to job references or type)
- No notification creation errors
- Terraform apply completes successfully
- Notifications preserved in YAML for future migration

### Future (Planned)
- `--migrate-notifications` mode will:
  - Map source job IDs to target job IDs
  - Detect and configure Slack integrations
  - Handle user notification migration (if user migration becomes possible)

---

## Upgrade Instructions

### For dbt Cloud Account Migration

1. Update importer version:
   ```bash
   git pull  # or pip install -U dbt-cloud-importer
   ```

2. Re-run Terraform apply:
   ```bash
   terraform plan
   terraform apply
   ```

3. Verify notifications are filtered:
   - Check Terraform plan output - should show 0 notifications to create
   - Verify no notification creation errors in apply output
   - Confirm notifications are still present in YAML file

---

## Migration Strategy

### Current Behavior (v0.6.3)
- **Fetch**: All notifications are fetched from source account
- **Normalize**: All notifications are normalized and included in YAML
- **Apply**: Only external email notifications without job references are created

### Future Enhancement
A separate `--migrate-notifications` mode will be implemented to:
- Map source job IDs to target job IDs (after jobs are created)
- Detect Slack integrations in target account
- Create Slack notifications if integration exists
- Handle user notification migration (if user migration becomes possible via API)

---

## Related Issues

- [dbt Cloud Notification API](https://docs.getdbt.com/dbt-cloud/api-v2#/operations/Create%20Notification)
- See `dev_support/KNOWN_ISSUES.md` for detailed notification migration limitations

---

## Contributors

- Notification filtering implementation
- Documentation updates for notification migration strategy

