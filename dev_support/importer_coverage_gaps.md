# Importer Coverage Gaps Assessment

**Version:** 0.3.0-dev  
**Date:** 2025-11-20

This document tracks which dbt Cloud resources are currently captured by the importer and which are still pending.

---

## ✅ Currently Implemented

### Account-Level
- [x] **Account Name** - Fetched from `/` endpoint
- [x] **Account ID** - From configuration
- [x] **Run Metadata & Hashes** - `_metadata` now captures `run_label`, `source_url_hash`, `source_url_slug`, `account_source_hash`, and `unique_run_identifier` for traceability.

### Global Resources
- [x] **Connections** - v3 `/connections/` endpoint
  - Captures: ID, name, type, connection details
- [x] **Repositories** - v2 `/repositories/` endpoint
  - Captures: ID, remote URL, git clone strategy
- [x] **Service Tokens** - v3 `/service-tokens/` endpoint (v0.3.0-dev)
  - Captures: ID, name, state, permission grants (permission sets, project IDs)
  - Note: Token string itself is not returned by API for security
- [x] **Groups** - v3 `/groups/` endpoint (v0.3.0-dev)
  - Captures: ID, name, assign by default, SSO mapping count, permission sets
- [x] **Notifications** - v2 `/notifications/` endpoint (v0.3.0-dev)
  - Captures: Type (Email, Slack, Webhook), state, destination, job trigger counts
- [x] **Webhook Subscriptions** - v3 `/webhooks/subscriptions` endpoint (v0.3.0-dev)
  - Captures: ID, name, client URL, event types, job IDs, active status
- [x] **PrivateLink Endpoints** - v3 `/private-link-endpoints/` endpoint (v0.3.0-dev)
  - Captures: ID, name, type, state, CIDR range
  - Referenced by connections via `private_link_endpoint_id`
- [x] **Report Line Items** - Derived export listing every element with `element_type_code`, `element_mapping_id`, `line_item_number` (default start `1001`, configurable via `DBT_REPORT_LINE_ITEM_START`), and `include_in_conversion` flag.

### Project-Level
- [x] **Projects** - v2 `/projects/` endpoint
  - Captures: ID, name, repository linkage
- [x] **Environments** - v2 `/environments/` endpoint
  - Captures: ID, name, type, connection linkage, credentials, dbt version, custom branch
- [x] **Jobs** - v2 `/jobs/` endpoint
  - Captures: ID, name, job type (ci/scheduled/merge/other), execute steps, triggers, settings
- [x] **Environment Variables** - v3 `/projects/{id}/environment-variables/environment/` endpoint
  - Captures: Variable name, project default, environment-specific overrides
  - Separates secrets (DBT_ENV_SECRET prefix) from regular variables

---

## ❌ Coverage Gaps (Account-Level)

### High Priority (User-Visible Configuration) - COMPLETE ✅
- [x] **Service Tokens** - v3 `/service-tokens/` (implemented v0.3.0-dev)
- [x] **Groups** - v3 `/groups/` (implemented v0.3.0-dev)
- [x] **Notifications** - v2 `/notifications/` (implemented v0.3.0-dev)
- [x] **Webhook Subscriptions** - v3 `/webhooks/subscriptions` (implemented v0.3.0-dev)

### Medium Priority (Advanced Features)

#### 1. **Semantic Layer Configs**
- **Endpoint**: v3 `/semantic-layer-credentials/` + project-level semantic layer fields
- **Impact**: Semantic layer enablement and configuration
- **Captures Needed**: Credentials, environment assignments, proxy settings
- **Terraform Module**: May exist
- **Phase 1 Status**: Documented but not implemented

#### 2. **License Maps / Seats**
- **Endpoint**: TBD (may be v3 `/license/` or `/seats/`)
- **Impact**: License allocation and usage tracking
- **Captures Needed**: Total seats, assigned users, license type
- **Terraform Module**: Unlikely (typically managed in UI)
- **Phase 1 Status**: Not documented in Phase 1 plan
- **Note**: May be read-only informational

### Low Priority (Metadata / Audit)

#### 8. **Account Features / Feature Flags**
- **Endpoint**: TBD (may be embedded in account response)
- **Impact**: Account-level feature toggles (Unity Catalog, etc.)
- **Captures Needed**: Enabled features, beta flags
- **Terraform Module**: Unlikely (typically controlled by dbt Labs)
- **Phase 1 Status**: Not documented in Phase 1 plan
- **Note**: Informational only; cannot be managed via Terraform

#### 9. **User Groups / SSO Mappings**
- **Endpoint**: May overlap with Groups endpoint or separate v3 `/users/` endpoint
- **Impact**: User management and SSO configuration
- **Captures Needed**: User list, group assignments, SSO provider details
- **Terraform Module**: Unlikely (user management typically external)
- **Phase 1 Status**: Partially covered under Groups
- **Note**: May be read-only for audit purposes

#### 10. **Model Notifications**
- **Endpoint**: TBD (may be part of dbt Cloud Discovery or Exposures)
- **Impact**: Notifications for model freshness, tests, or exposures
- **Captures Needed**: Model names, notification rules, channels
- **Terraform Module**: Unknown
- **Phase 1 Status**: Not documented in Phase 1 plan
- **Note**: May be newer feature not yet in API

#### 11. **OAuth Configurations**
- **Endpoint**: v3 `/oauth-configurations/`
- **Impact**: OAuth app configurations for Git integrations
- **Captures Needed**: Provider, client ID, install URLs
- **Terraform Module**: Unlikely (typically one-time setup)
- **Phase 1 Status**: Documented but noted as manual remapping only

---

## 📋 Next Steps

### Immediate (0.3.0-dev) - COMPLETE ✅
1. ~~**Service Tokens**~~ - ✅ Added to global resources with permission grants
2. ~~**Groups**~~ - ✅ Added to global resources with permission sets
3. ~~**Notifications**~~ - ✅ Added to global resources with destinations and job triggers
4. ~~**Webhook Subscriptions**~~ - ✅ Added to global resources with event types and job IDs

### Near-Term (0.4.0-dev)
1. **Semantic Layer Configs** - Add to project-level resources

### Future / As Needed
2. **License Maps** - Add as read-only metadata in summary report
3. **Account Features** - Add as read-only metadata in summary report
4. **OAuth Configurations** - Add as informational (not Terraform-managed)
5. **Model Notifications** - Research availability and add if API exists
6. **User Groups** - Add as read-only audit information

---

## 🔍 API Research Needed

The following items need API endpoint research:
- [ ] License/seats endpoint availability
- [ ] Account features/flags in account response
- [ ] Model notifications API (if exists)
- [ ] User management endpoints (beyond groups)

---

## 📊 Coverage Statistics

**Current Coverage:**
- Account-level: 2/2 (100%) - ID, Name
- Global Resources: 7/8 (88%) - Connections, Repositories, Service Tokens, Groups, Notifications, Webhooks, PrivateLink Endpoints
- Project Resources: 5/5 (100%) - Projects, Environments, Jobs, Env Vars, Credentials

**Overall:** ~85% of identified resources implemented

**Target for 1.0:** 90%+ coverage of Terraform-manageable resources

