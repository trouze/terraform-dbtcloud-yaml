# dbt Cloud Migration Checklist

**Customer:** _________________  
**Source Account ID:** _________________  
**Target Account ID:** _________________  
**Migration Date:** _________________  
**dbt Labs Contact:** _________________

---

## Pre-Migration (Customer Tasks)

### Target Account Setup

Complete these items **before** the scheduled migration date:

- [ ] **SSO Integration** configured in target account
- [ ] **Git Provider Integration** configured (GitHub, GitLab, Azure DevOps, or Bitbucket)
- [ ] **Slack Integration** configured (if using Slack notifications)
- [ ] **IP Allowlisting** updated in warehouse to include new dbt Cloud IPs
- [ ] **PrivateLink** connections requested (if applicable)
- [ ] **Service Token** created with Account Admin scope

### Credentials to Provide

Fill in the warehouse credentials for each token name listed below. These correspond to `credential.token_name` values in your configuration:

| Token Name | Credential Type | Value Provided |
|------------|-----------------|----------------|
| `_______________` | Password/Token | [ ] |
| `_______________` | Password/Token | [ ] |
| `_______________` | Password/Token | [ ] |
| `_______________` | Password/Token | [ ] |

**Note:** Credentials cannot be migrated automatically. You must provide these values for Terraform to configure warehouse connections.

### LOOKUP Placeholders to Resolve

The following resources need to exist in your target account before migration. Either create them manually or confirm they already exist:

| Placeholder | Resource Type | Action Required |
|-------------|---------------|-----------------|
| `LOOKUP:_______________` | Connection | [ ] Create / [ ] Exists |
| `LOOKUP:_______________` | Connection | [ ] Create / [ ] Exists |
| `LOOKUP:_______________` | Repository | [ ] Create / [ ] Exists |
| `LOOKUP:_______________` | Repository | [ ] Create / [ ] Exists |

### Decisions Required

- [ ] **Job Activation**: Should jobs be created as active or deactivated?
  - [ ] Active (jobs will run on schedule immediately)
  - [ ] Deactivated (jobs created but schedules disabled)

- [ ] **Code Export**: Have you exported/committed all code from managed repositories?
  - [ ] Yes, all code is saved
  - [ ] N/A, not using managed repos

---

## Migration Day

### dbt Labs Tasks

- [ ] Final fetch of source account configuration
- [ ] Normalize to v2 YAML format
- [ ] `terraform plan` executed successfully
- [ ] `terraform apply` completed without errors
- [ ] Verified projects created in target account
- [ ] Verified environments and connections
- [ ] Test job run successful

### Customer Verification

After migration, verify the following in your new dbt Cloud account:

- [ ] **Projects**: All expected projects are visible
- [ ] **Environments**: Each project has the correct environments
- [ ] **Jobs**: Jobs are present with correct schedules
- [ ] **Environment Variables**: Variables are configured correctly
- [ ] **Test Run**: Manual job run completes successfully

---

## Post-Migration (Customer Tasks)

### Developer Actions

Each developer on your team must complete:

- [ ] Accept invitation to new account (via SSO URL or email)
- [ ] Reconnect personal git account in the new account
- [ ] Re-enter warehouse credentials for each project
- [ ] Set up signed commits (if previously configured)
- [ ] Verify IDE access and repository cloning

### External Integrations

Update all external systems that interact with dbt Cloud:

- [ ] **API Base URL**: Update to new account endpoint
- [ ] **API Tokens**: Replace with new account service tokens
- [ ] **Account ID**: Update in all API calls
- [ ] **Job IDs**: Update in orchestration tools (Airflow, Prefect, etc.)

**Job ID Mapping** (provided by dbt Labs):

| Old Job Name | New Job ID |
|--------------|------------|
| `_______________` | `_______________` |
| `_______________` | `_______________` |
| `_______________` | `_______________` |

### Account Transition

- [ ] **Old account jobs deactivated**: Date _____________
- [ ] **Old account locked**: Date _____________
- [ ] **Migration complete sign-off**: Date _____________

---

## Issues / Notes

Use this section to track any issues encountered during migration:

| Issue | Status | Resolution |
|-------|--------|------------|
| | | |
| | | |
| | | |

---

## Contact Information

**dbt Labs Support:**
- Migration Contact: _________________
- Email: _________________
- Slack Channel: _________________

**Customer Contacts:**
- Technical Lead: _________________
- DevOps/Platform: _________________
- Data Engineering: _________________

---

## Attachments

The following files are provided with this checklist:

- [ ] `dbt-config.yml` - Generated v2 YAML configuration
- [ ] `lookups.json` - LOOKUP placeholder manifest
- [ ] `exclusions.md` - Excluded resources report
- [ ] `terraform.tfvars.template` - Variable template to complete
- [ ] `variables.tf` - Variable definitions with descriptions

