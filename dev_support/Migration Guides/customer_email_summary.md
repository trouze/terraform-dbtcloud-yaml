# dbt Cloud Migration - Customer Summary

> **Template Usage**: Customize the bracketed sections `[like this]` for each customer. Remove this note before sending.

---

**Subject:** dbt Cloud Migration Overview - [Customer Name]

Hi [Customer Contact],

Thank you for working with us on your dbt Cloud migration. This email outlines our migration approach, what we'll handle, what we need from you, and considerations for your broader organization.

---

## Migration Phases

We'll approach this migration in phases to minimize risk and allow validation at each step:

**Phase 1: Import and Review** — *dbt Labs leads, Customer advises*
- We extract configuration from your source account
- Generate reports for joint review
- Identify any placeholders, exclusions, or decisions needed

**Phase 2: Target Account-Level Manual Setup** — *Customer leads, dbt Labs advises*
- Configure SSO, git integration, Slack, etc. in target account
- Network/firewall updates, PrivateLink provisioning
- Create service tokens for Terraform operations

**Phase 3: Target Account-Level Migration** — *dbt Labs leads, Customer advises*
- Migrate global resources (connections, repositories, groups, service tokens)
- Verify account-level configuration

**Phase 4: Single POC Project Migration and Verification** — *dbt Labs leads, Customer advises, verifies & approves*
- Migrate one representative project end-to-end
- You validate environments, jobs, and credentials
- Test job execution and integrations
- Identify any issues before broader rollout

**Phase 5: Phased Remainder Migration** — *dbt Labs leads, Customer advises & verifies*
- Migrate remaining projects in agreed batches
- Incremental verification at each stage
- Coordinate external integration updates as projects go live

**Phase 6: Customer External Integration and Post-Migration Changes** — *Customer leads, dbt Labs advises*
- Update external orchestrators with new Job IDs/endpoints
- Update metadata/catalog integrations
- Reconfigure CI/CD pipelines and custom API integrations
- Developer re-onboarding (credentials, git connections)
- Old account deactivation/lockdown

---

## What dbt Labs Will Handle

With access to your dbt Cloud accounts (DWH/git access not required, but helpful), we will:

- **Extract and normalize** your source account configuration into a migration-ready format
- **Review with you** any placeholders, exclusions, or decisions needed before migration
- **Execute the migration** via Terraform, verifying resources in the target account
- **Provide job ID mappings** for updating your external integrations
- **Export historical data** (audit logs, run history/logs) for your archiving, if desired
- **Assist with punch-list items** to ensure a complete lift-and-shift

For the full technical process, see our [Migration Workflow Guide](migration_workflow.md).

---

## What We Need From You

**API Tokens:**
- Read-only service token from the source account
- Account Admin service token for the target account

**Warehouse Credentials:**
- A customer representative will need to gather all database passwords/tokens for your connections
- Credentials can be entered either:
  - **Via Terraform** (recommended for 20+ environments): securely added to your Terraform variables
  - **Via dbt Cloud UI**: manually entered per environment after creation—practical for smaller migrations
- These credentials should **not** be shared with the dbt Labs RA
- *Note: Credentials cannot be exported from dbt Cloud and must be provided fresh*

**Decisions:**
- Should jobs be created as **active** (run on schedule immediately) or **deactivated** (schedules disabled)?
- List of projects to migrate (all or specific subset)
- **Job pruning**: Should we skip migrating stale/unused jobs? (e.g., jobs not run in 30/60/90 days)—this is a good opportunity to clean up before migration

**Availability:**
- Point of contact available for **shared webcalls on migration days**
- This contact should be comfortable with CLI tooling and have the ability to run Python and Terraform (locally or on a platform)

---

## What You'll Need to Plan For

### Pre-Migration Setup (Target Account)

- [ ] SSO/SAML integration configured
- [ ] Git provider integration (GitHub, GitLab, Azure DevOps, Bitbucket)
- [ ] Slack workspace connected (if using notifications)
- [ ] Network/firewall rules updated for new dbt Cloud IPs
- [ ] PrivateLink endpoints provisioned (if applicable)—*requires dbt support ticket & customer INFRA team, typical 5 business day SLA for dbt's tasks*

### Post-Migration Actions

- [ ] Developer re-onboarding (invitations, credential setup, git connections)
- [ ] External integration updates (API endpoints, Job IDs, tokens)
- [ ] Agree on timeline to lock/disable old account

---

## Organizational Coordination Considerations

*Not all items below apply to every customer. This is intended to help identify which teams beyond your data team may need to be involved.*

### What Changes in a Migration

1. **The URL** to access dbt Cloud and its APIs will change
2. **Hardcoded IDs** (Job IDs, Project IDs, etc.) in external systems will need to change
3. **Egress IPs** for dbt Cloud will be different
4. **All service tokens and PATs** will need to be regenerated in the new account
5. **SSO will need to be EDITED** on the customer side. Existing apps can be reused, with new URLs

### Broad Categories of Impact

**Networking:**
- Firewall/allowlist updates for new dbt Cloud egress IPs
- PrivateLink endpoint provisioning (can require lead time)
- VPN or network peering adjustments

**Access Control:**
- SSO/SAML configuration pointing to new account
- Service account provisioning for new tokens

**Authorization:**
- New service tokens and PATs for API access
- Updated permissions and scopes as needed

**API Integrations:**
- External orchestrators (Airflow, Prefect, Dagster) - update Job IDs and endpoints
- Metadata/catalog tools (Atlan, Alation, etc.) - update API connections
- CI/CD pipelines triggering dbt Cloud - update endpoints and tokens
- Custom applications using dbt Cloud APIs

*Migrations tend to require more organizational coordination when you have external orchestration, metadata ingestion to external catalogs, multiple PrivateLink connections, or custom API integrations.*

---

## Legacy Data Access and Retention

### What Cannot Be Migrated

Job history, run logs, audit logs, and build artifacts are tied to your source account and **cannot be transferred** to the target account.

### Access Timeline Planning

Please work with your dbt account team to agree on:

- **Online/API-accessible period**: How long the old account remains active for self-service access to historical data
- **Support-ticket period**: After the account is locked, historical data requests will require a support ticket
- **Final retention cutoff**: When data is no longer retrievable

### Export Assistance Available

We can assist with scripting the export of key logs and artifacts for retention on your own systems before account lockdown. If you have compliance or audit requirements for historical data, please let us know early so we can plan accordingly.

---

## Next Steps

1. **Schedule a kickoff call** to review this summary and answer questions
2. **Provide API tokens** for source and target accounts
3. **Begin target account setup** (SSO, git integration, network configuration)
4. **Identify your POC project** for the initial migration test

Please reply with any questions or to schedule our kickoff call.

Best regards,

[Your Name]  
[Title]  
dbt Labs

---

*For detailed technical documentation, see the [Migration Workflow Guide](migration_workflow.md).*

