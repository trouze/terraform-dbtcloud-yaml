# Customer Migration Summary Email Template - Plan

## Document Location

Create a new file at [`dev_support/Migration Guides/customer_email_summary.md`](customer_email_summary.md) - a concise, email-ready template that can be customized and sent to customers.

## Document Structure

### Email Template Format

The document should be structured as a ready-to-send email with:
- Brief intro paragraph explaining the migration approach
- Migration phases overview
- Responsibility sections with bullet points (scannable)
- Organizational considerations
- Legacy data access planning
- Call-to-action for next steps

---

### Migration Phases Overview

Introduce the phased approach to set expectations, with clear ownership for each phase:

**Phase 1: Import and Review** — *dbt Labs leads, Customer advises*
- Extract configuration from source account
- Generate reports and review with customer
- Identify placeholders, exclusions, and decisions needed

**Phase 2: Target Account-Level Manual Setup** — *Customer leads, dbt Labs advises*
- Customer configures SSO, git integration, Slack, etc.
- Network/firewall updates, PrivateLink provisioning
- Create service tokens for Terraform operations

**Phase 3: Target Account-Level Migration** — *dbt Labs leads, Customer advises*
- Migrate global resources (connections, repositories, groups, tokens)
- Verify account-level configuration

**Phase 4: Single POC Project Migration and Verification** — *dbt Labs leads, Customer advises, verifies & approves*
- Migrate one representative project end-to-end
- Customer validates environments, jobs, credentials
- Test job execution and integrations
- Identify any issues before broader rollout

**Phase 5: Phased Remainder Migration** — *dbt Labs leads, Customer advises & verifies*
- Migrate remaining projects in agreed batches
- Incremental verification at each stage
- Coordinate external integration updates as projects go live

**Phase 6: Customer External Integration and Post-Migration Changes** — *Customer leads, dbt Labs advises*
- Customer updates external orchestrators with new Job IDs/endpoints
- Update metadata/catalog integrations
- Reconfigure CI/CD pipelines and custom API integrations
- Developer re-onboarding (credentials, git connections)
- Old account deactivation/lockdown

---

### Section 1: What dbt Labs Will Handle

Items the Resident Architect can do with system access:
- Extract configuration from source account (projects, environments, jobs, env vars)
- Generate normalized YAML configuration for target account
- Review and document any placeholders or issues
- Prepare Terraform configuration files
- Execute `terraform plan` and `terraform apply` on migration day
- Verify resources created correctly in target account
- Provide job ID mapping for external integrations

### Section 2: What We Need From You (Customer Provides)

Items the customer must supply:
- **API Tokens**: Read-only token from source account, Account Admin token for target account
- **Warehouse Credentials**: All passwords/tokens for database connections (cannot be exported)
- **Decisions**: Job activation preference (active vs deactivated on creation)
- **Availability**: Point of contact on migration day for questions

### Section 3: What You'll Need to Plan For

**Pre-migration setup (target account):**
- SSO integration configuration
- Git provider integration (GitHub, GitLab, etc.)
- Network/firewall updates for new dbt Cloud IPs
- PrivateLink setup (if applicable)

**Post-migration actions:**
- Developer re-onboarding (re-invite, credential setup)
- External integration updates (API endpoints, Job IDs)
- Account transition timeline (when to lock old account)

### Section 4: Organizational Coordination Considerations

**Intro disclaimer**: Not all items apply to every customer, and this is not exhaustive. The goal is to help identify which teams beyond the data team may need to be involved.

**Root Causes - What Changes in a Migration:**
1. The URL to access dbt Cloud and its APIs will change
2. Any hardcoded IDs (Job IDs, Project IDs, etc.) in external systems will need to change
3. The egress IP for dbt Cloud will be different
4. All dbt Cloud service tokens and PATs will need to be regenerated

**Broad Categories of Impact:**

- **Networking**: Firewall/allowlist updates for new egress IPs, PrivateLink provisioning, VPN/peering adjustments
- **Access Control**: SSO/SAML configuration, service account provisioning
- **Authorization**: New service tokens and PATs, updated permissions/scopes
- **API Integrations**: External orchestrators, metadata/catalog tools, CI/CD pipelines, custom applications

**Complexity Note**: Migrations tend to require more organizational coordination when customers have external orchestration, metadata ingestion to catalogs, multiple PrivateLink connections, or custom API integrations.

### Section 5: Legacy Data Access and Retention

**What Cannot Be Migrated:**
Job history, run logs, audit logs, and build artifacts are tied to the source account and cannot be transferred to the target account.

**Access Timeline Planning:**
Work with your dbt account team to agree on:
- **Online/API-accessible period**: How long the old account remains active for self-service access to historical data
- **Support-ticket period**: After the account is locked, historical data requests require a support ticket
- **Final retention cutoff**: When data is no longer retrievable

**Export Assistance Available:**
dbt Labs can assist with scripting the export of key logs and artifacts for retention on your own systems before account lockdown. If you have compliance or audit requirements for historical data, let us know early so we can plan accordingly.

### Footer

- Contact information for questions
- Suggested next step (e.g., schedule kickoff call)

---

## Tone and Length

- Professional but approachable
- Scannable with bullet points and bold headers
- Approximately 700-900 words (2-2.5 pages) - acceptable given migration complexity
- No unnecessary technical jargon
- Clear that organizational considerations are "if applicable" not mandatory

