"""Generate human-readable reports from account snapshots."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from . import get_version

if TYPE_CHECKING:
    from .models import AccountSnapshot


def generate_summary_report(snapshot: AccountSnapshot) -> str:
    """Generate a high-level summary with counts by object type."""
    lines = [
        "# dbt Cloud Account Import Summary",
        "",
        f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Importer Version:** {get_version()}",
        f"**Account ID:** {snapshot.account_id}",
        f"**Account Name:** {snapshot.account_name or 'N/A'}",
        "",
        "## Global Resources",
        "",
        f"- **Connections:** {len(snapshot.globals.connections)}",
        f"- **Repositories:** {len(snapshot.globals.repositories)}",
        f"- **Service Tokens:** {len(snapshot.globals.service_tokens)}",
        f"- **Groups:** {len(snapshot.globals.groups)}",
        f"- **Notifications:** {len(snapshot.globals.notifications)}",
        f"- **Webhooks:** {len(snapshot.globals.webhooks)}",
        f"- **PrivateLink Endpoints:** {len(snapshot.globals.privatelink_endpoints)}",
        f"- **Account Features:** {'Yes' if snapshot.globals.account_features else 'No'}",
        f"- **IP Restrictions:** {len(snapshot.globals.ip_restrictions)}",
        f"- **OAuth Configurations:** {len(snapshot.globals.oauth_configurations)}",
        f"- **User Groups:** {len(snapshot.globals.user_groups)}",
        "",
        "## Projects Overview",
        "",
        f"**Total Projects:** {len(snapshot.projects)}",
        "",
    ]

    # Calculate aggregated counts across all projects
    total_envs = sum(len(p.environments) for p in snapshot.projects)
    total_jobs = sum(len(p.jobs) for p in snapshot.projects)
    total_ext_attr = sum(len(p.extended_attributes) for p in snapshot.projects)
    total_env_vars = 0
    total_secret_vars = 0
    
    for p in snapshot.projects:
        for var in p.environment_variables:
            var_name = getattr(var, "name", "")
            if var_name.startswith("DBT_ENV_SECRET"):
                total_secret_vars += 1
            else:
                total_env_vars += 1

    total_lineage = sum(len(p.lineage_integrations) for p in snapshot.projects)
    total_sl_configs = sum(1 for p in snapshot.projects if p.semantic_layer_config)
    total_artefacts = sum(
        1 for p in snapshot.projects if p.docs_job_id or p.freshness_job_id
    )

    lines.extend(
        [
            "### Aggregate Counts",
            "",
            f"- **Total Environments:** {total_envs}",
            f"- **Total Jobs:** {total_jobs}",
            f"- **Total Extended Attributes (EXTATTR):** {total_ext_attr}",
            f"- **Total Environment Variables:** {total_env_vars}",
            f"- **Total Environment Variable Secrets:** {total_secret_vars}",
            f"- **Total Lineage Integrations:** {total_lineage}",
            f"- **Total Semantic Layer Configs:** {total_sl_configs}",
            f"- **Total Project Artefacts:** {total_artefacts}",
            "",
            "---",
            "",
            "## Projects Detail",
            "",
        ]
    )

    # Per-project breakdown
    for project in sorted(snapshot.projects, key=lambda p: p.name):
        project_envs = len(project.environments)
        project_jobs = len(project.jobs)
        project_ext_attr = len(project.extended_attributes)
        
        # Count regular and secret variables
        project_vars = 0
        project_secrets = 0
        for var in project.environment_variables:
            var_name = getattr(var, "name", "")
            if var_name.startswith("DBT_ENV_SECRET"):
                project_secrets += 1
            else:
                project_vars += 1

        project_lineage = len(project.lineage_integrations)
        project_sl = "Yes" if project.semantic_layer_config else "No"
        project_artefacts = "Yes" if (project.docs_job_id or project.freshness_job_id) else "No"

        lines.extend(
            [
                f"### {project.name} (PRJ ID: {project.id})",
                "",
                f"- **Environments:** {project_envs}",
                f"- **Jobs:** {project_jobs}",
                f"- **Extended Attributes (EXTATTR):** {project_ext_attr}",
                f"- **Environment Variables:** {project_vars}",
                f"- **Environment Variable Secrets:** {project_secrets}",
                f"- **Lineage Integrations:** {project_lineage}",
                f"- **Semantic Layer Config:** {project_sl}",
                f"- **Project Artefacts:** {project_artefacts}",
                "",
            ]
        )

    return "\n".join(lines)


def generate_detailed_report(snapshot: AccountSnapshot) -> str:
    """Generate a detailed report showing IDs, names, and nested structure."""
    lines = [
        "# dbt Cloud Account Detailed Report",
        "",
        f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Importer Version:** {get_version()}",
        "",
        "## Account",
        "",
        f"- **ID:** {snapshot.account_id}",
        f"- **Name:** {snapshot.account_name or 'N/A'}",
        "",
        "---",
        "",
        "## Global Resources",
        "",
    ]

    # Connections
    if snapshot.globals.connections:
        lines.append("### Connections")
        lines.append("")
        lines.append("| Key | ID | Name | Type | Adapter Version | OAuth | PrivateLink Endpoint |")
        lines.append("|-----|----|----- |------|-----------------|-------|----------------------|")
        for key, conn in sorted(snapshot.globals.connections.items()):
            conn_id = conn.id or "N/A"
            conn_name = conn.name or "N/A"
            conn_type = conn.type or "N/A"
            
            # Extract adapter version from details
            adapter_version = conn.details.get("adapter_version", "N/A")
            
            # Check if OAuth is configured
            oauth_configured = "Yes" if conn.details.get("is_configured_for_oauth", False) else "No"
            
            # Extract PrivateLink endpoint ID
            privatelink_endpoint_id = conn.details.get("private_link_endpoint_id") or "N/A"
            
            lines.append(f"| `{key}` | {conn_id} | {conn_name} | {conn_type} | {adapter_version} | {oauth_configured} | {privatelink_endpoint_id} |")
        lines.append("")

    # PrivateLink Endpoints
    if snapshot.globals.privatelink_endpoints:
        lines.append("### PrivateLink Endpoints")
        lines.append("")
        lines.append("| Key | ID | Name | Type | State | CIDR Range |")
        lines.append("|-----|----|------|------|-------|------------|")
        for key, endpoint in sorted(snapshot.globals.privatelink_endpoints.items()):
            endpoint_id = endpoint.id or "N/A"
            endpoint_name = endpoint.name or "N/A"
            endpoint_type = endpoint.type or "N/A"
            endpoint_state = endpoint.state or "N/A"
            cidr_range = endpoint.cidr_range or "N/A"
            lines.append(f"| `{key}` | {endpoint_id} | {endpoint_name} | {endpoint_type} | {endpoint_state} | {cidr_range} |")
        lines.append("")

    # Repositories
    if snapshot.globals.repositories:
        lines.append("### Repositories")
        lines.append("")
        lines.append("| Key | ID | Remote URL | Clone Strategy |")
        lines.append("|-----|----|-----------:|----------------|")
        for key, repo in sorted(snapshot.globals.repositories.items()):
            repo_id = repo.id or "N/A"
            remote = repo.remote_url or "N/A"
            clone_strategy = repo.git_clone_strategy or "N/A"
            lines.append(f"| `{key}` | {repo_id} | {remote} | {clone_strategy} |")
        lines.append("")

    # Service Tokens
    if snapshot.globals.service_tokens:
        lines.append("### Service Tokens")
        lines.append("")
        lines.append("| Key | ID | Name | State | Permission Sets | Project IDs |")
        lines.append("|-----|----|------|-------|-----------------|-------------|")
        for key, token in sorted(snapshot.globals.service_tokens.items()):
            token_id = token.id or "N/A"
            token_name = token.name or "N/A"
            state = "Active" if token.state == 1 else "Inactive" if token.state == 2 else "N/A"
            
            # Format permission sets
            perm_count = len(token.permission_sets)
            if perm_count > 0:
                perm_display = ", ".join(f"`{p}`" for p in token.permission_sets)
            else:
                perm_display = "All Projects"
            
            # Format project IDs
            proj_count = len(token.project_ids)
            if proj_count > 0:
                proj_display = ", ".join(str(p) for p in token.project_ids)
            else:
                proj_display = "All"
            
            lines.append(f"| `{key}` | {token_id} | {token_name} | {state} | {perm_display} | {proj_display} |")
        lines.append("")

    # Groups
    if snapshot.globals.groups:
        lines.append("### Groups")
        lines.append("")
        lines.append("| Key | ID | Name | Assign by Default | Permission Sets | SSO Mappings |")
        lines.append("|-----|----|------|-------------------|-----------------|--------------|")
        for key, group in sorted(snapshot.globals.groups.items()):
            group_id = group.id or "N/A"
            group_name = group.name or "N/A"
            assign_default = "Yes" if group.assign_by_default else "No"
            
            # Format permission sets
            perm_count = len(group.permission_sets)
            if perm_count > 0:
                perm_display = ", ".join(f"`{p}`" for p in group.permission_sets)
            else:
                perm_display = "None"
            
            # Format SSO mappings
            sso_count = len(group.sso_mapping_groups)
            sso_display = f"{sso_count} mapping(s)" if sso_count > 0 else "None"
            
            lines.append(f"| `{key}` | {group_id} | {group_name} | {assign_default} | {perm_display} | {sso_display} |")
        lines.append("")

    # Notifications
    if snapshot.globals.notifications:
        lines.append("### Notifications")
        lines.append("")
        lines.append("| Key | ID | Type | Destination | State | Jobs on Success | Jobs on Failure | Jobs on Cancel |")
        lines.append("|-----|----|------|-------------|-------|-----------------|-----------------|----------------|")
        for key, notif in sorted(snapshot.globals.notifications.items()):
            notif_id = notif.id or "N/A"
            notif_type_map = {1: "Email", 2: "Slack", 3: "Webhook"}
            notif_type = notif_type_map.get(notif.notification_type, "Unknown")
            state = "Active" if notif.state == 1 else "Inactive" if notif.state == 2 else "N/A"
            
            # Extract destination (email, slack channel, or webhook URL)
            destination = "N/A"
            if notif.notification_type == 1:  # Email
                destination = notif.metadata.get("external_email", "N/A")
            elif notif.notification_type == 2:  # Slack
                channel_name = notif.metadata.get("slack_channel_name", "")
                if channel_name:
                    destination = channel_name
                else:
                    destination = notif.metadata.get("slack_channel_id", "N/A")
            elif notif.notification_type == 3:  # Webhook
                destination = notif.metadata.get("url", "N/A")
            
            on_success_count = len(notif.on_success)
            on_failure_count = len(notif.on_failure)
            on_cancel_count = len(notif.on_cancel)
            
            lines.append(f"| `{key}` | {notif_id} | {notif_type} | {destination} | {state} | {on_success_count} | {on_failure_count} | {on_cancel_count} |")
        lines.append("")

    # Webhooks
    if snapshot.globals.webhooks:
        lines.append("### Webhook Subscriptions")
        lines.append("")
        lines.append("| Key | ID | Name | Client URL | Event Types | Job IDs | Active |")
        lines.append("|-----|----|------|------------|-------------|---------|--------|")
        for key, webhook in sorted(snapshot.globals.webhooks.items()):
            webhook_id = webhook.id or "N/A"
            webhook_name = webhook.name or "N/A"
            client_url = webhook.client_url or "N/A"
            
            # Format event types (may be complex objects or strings)
            event_types_str = "N/A"
            if webhook.event_types:
                if isinstance(webhook.event_types, list):
                    # Handle both string and dict event types
                    formatted_events = []
                    for evt in webhook.event_types[:3]:  # Limit to first 3 for readability
                        if isinstance(evt, dict):
                            formatted_events.append(evt.get("event_type", str(evt)))
                        else:
                            formatted_events.append(str(evt))
                    event_types_str = ", ".join(formatted_events)
                    if len(webhook.event_types) > 3:
                        event_types_str += f" (+{len(webhook.event_types) - 3} more)"
            
            job_ids_str = ", ".join(str(jid) for jid in webhook.job_ids) if webhook.job_ids else "All"
            active_str = "Yes" if webhook.active else "No"
            
            lines.append(f"| `{key}` | {webhook_id} | {webhook_name} | {client_url} | {event_types_str} | {job_ids_str} | {active_str} |")
        lines.append("")

    # Account Features
    if snapshot.globals.account_features:
        lines.append("### Account Features")
        lines.append("")
        af = snapshot.globals.account_features
        for field_name in sorted(vars(af)):
            if not field_name.startswith("_"):
                lines.append(f"- **{field_name}:** {getattr(af, field_name, 'N/A')}")
        lines.append("")

    # IP Restrictions
    if snapshot.globals.ip_restrictions:
        lines.append("### IP Restrictions")
        lines.append("")
        lines.append("| Key | ID | Name | Type | Enabled |")
        lines.append("|-----|----|------|------|---------|")
        for key, rule in sorted(snapshot.globals.ip_restrictions.items()):
            rule_id = getattr(rule, "id", "N/A")
            rule_name = getattr(rule, "name", "N/A")
            rule_type = getattr(rule, "type", "N/A")
            enabled = getattr(rule, "enabled", "N/A")
            lines.append(f"| `{key}` | {rule_id} | {rule_name} | {rule_type} | {enabled} |")
        lines.append("")

    # OAuth Configurations
    if snapshot.globals.oauth_configurations:
        lines.append("### OAuth Configurations")
        lines.append("")
        lines.append("| Key | ID | Name | Type |")
        lines.append("|-----|----|------|------|")
        for key, oauth in sorted(snapshot.globals.oauth_configurations.items()):
            oauth_id = getattr(oauth, "id", "N/A")
            oauth_name = getattr(oauth, "name", "N/A")
            oauth_type = getattr(oauth, "type", "N/A")
            lines.append(f"| `{key}` | {oauth_id} | {oauth_name} | {oauth_type} |")
        lines.append("")

    # User Groups
    if snapshot.globals.user_groups:
        lines.append("### User Groups")
        lines.append("")
        lines.append("| Key | ID | Name |")
        lines.append("|-----|----|------|")
        for key, ug in sorted(snapshot.globals.user_groups.items()):
            ug_id = getattr(ug, "id", "N/A")
            ug_name = getattr(ug, "name", key)
            lines.append(f"| `{key}` | {ug_id} | {ug_name} |")
        lines.append("")

    lines.extend(["---", "", "## Projects", ""])

    # Projects tree
    for idx, project in enumerate(sorted(snapshot.projects, key=lambda p: p.name)):
        if idx > 0:
            lines.append("---")
            lines.append("---")
            lines.append("---")
            lines.append("")
        
        lines.append(f"### {project.name}")
        lines.append("")
        lines.append(f"  - **Project ID:** {project.id}")
        lines.append(f"  - **Key:** `{project.key}`")
        if project.repository_key:
            lines.append(f"  - **Repository:** `{project.repository_key}`")
        lines.append("")

        # Extended Attributes (EXTATTR)
        if project.extended_attributes:
            lines.append("#### Extended Attributes (EXTATTR)")
            lines.append("")
            lines.append("| Key | ID | State | Payload (keys) |")
            lines.append("|-----|----|-------|-----------------|")
            for eat in project.extended_attributes:
                eat_key = getattr(eat, "key", "N/A")
                eat_id = getattr(eat, "id", "N/A")
                eat_state = "Active" if getattr(eat, "state", 1) == 1 else "Inactive"
                ext_attrs = getattr(eat, "extended_attributes", {}) or {}
                payload_keys = ", ".join(sorted(ext_attrs.keys())) if isinstance(ext_attrs, dict) else "—"
                lines.append(f"| `{eat_key}` | {eat_id} | {eat_state} | {payload_keys} |")
            lines.append("")
            lines.append("")

        # Project Artefacts
        if project.docs_job_id or project.freshness_job_id:
            lines.append("#### Project Artefacts")
            lines.append("")
            if project.docs_job_id:
                lines.append(f"- **Docs Job ID:** {project.docs_job_id}")
            if project.freshness_job_id:
                lines.append(f"- **Freshness Job ID:** {project.freshness_job_id}")
            lines.append("")

        # Lineage Integrations
        if project.lineage_integrations:
            lines.append("#### Lineage Integrations")
            lines.append("")
            lines.append("| ID | Name | Host |")
            lines.append("|----|------|------|")
            for lngi in project.lineage_integrations:
                lngi_id = getattr(lngi, "id", "N/A")
                lngi_name = getattr(lngi, "name", "N/A")
                lngi_host = getattr(lngi, "host", "N/A")
                lines.append(f"| {lngi_id} | {lngi_name} | {lngi_host} |")
            lines.append("")

        # Semantic Layer Configuration
        if project.semantic_layer_config:
            lines.append("#### Semantic Layer Configuration")
            lines.append("")
            sl = project.semantic_layer_config
            lines.append(f"- **Environment ID:** {getattr(sl, 'environment_id', 'N/A')}")
            lines.append("")

        # Environment variables (split into regular and secrets)
        if project.environment_variables:
            regular_vars = []
            secret_vars = []
            
            for var in project.environment_variables:
                var_name = getattr(var, "name", "Unnamed")
                if var_name.startswith("DBT_ENV_SECRET"):
                    secret_vars.append(var)
                else:
                    regular_vars.append(var)
            
            # Regular environment variables
            if regular_vars:
                lines.append("#### Environment Variables")
                lines.append("")
                for var in regular_vars:
                    var_name = getattr(var, "name", "Unnamed")
                    project_default = getattr(var, "project_default", None)
                    env_values = getattr(var, "environment_values", {})
                    
                    # Build the header line
                    total_values = len(env_values) + (1 if project_default else 0)
                    lines.append(f"**`{var_name}`** — {total_values} value(s)")
                    lines.append("")
                    
                    # Create a table for values
                    if project_default or env_values:
                        lines.append("| Environment | Value |")
                        lines.append("|-------------|-------|")
                        
                        # Show project default if it exists
                        if project_default:
                            lines.append(f"| Project (default) | `{project_default}` |")
                        
                        # Show environment-specific values
                        if env_values:
                            for env_name, value in sorted(env_values.items()):
                                lines.append(f"| {env_name} | `{value}` |")
                        
                        lines.append("")
                lines.append("")
            
            # Secret environment variables
            if secret_vars:
                lines.append("#### Environment Variable Secrets")
                lines.append("")
                for var in secret_vars:
                    var_name = getattr(var, "name", "Unnamed")
                    project_default = getattr(var, "project_default", None)
                    env_values = getattr(var, "environment_values", {})
                    
                    # Build the header line
                    total_values = len(env_values) + (1 if project_default else 0)
                    lines.append(f"**`{var_name}`** — {total_values} value(s)")
                    lines.append("")
                    
                    # Create a table showing masked values
                    if project_default or env_values:
                        lines.append("| Environment | Value |")
                        lines.append("|-------------|-------|")
                        
                        # Show project default (masked)
                        if project_default:
                            lines.append(f"| Project (default) | `{project_default}` |")
                        
                        # Show environment-specific values (masked)
                        if env_values:
                            for env_name, value in sorted(env_values.items()):
                                lines.append(f"| {env_name} | `{value}` |")
                        
                        lines.append("")
                lines.append("")

        # Environments
        if project.environments:
            lines.append("#### Environments")
            lines.append("")
            for env in project.environments:
                env_name = getattr(env, "name", "Unnamed")
                env_id = getattr(env, "id", "N/A")
                env_type = getattr(env, "type", "N/A")
                env_version = getattr(env, "dbt_version", None) or "N/A"
                ext_attr_key = getattr(env, "extended_attributes_key", None)
                ext_attr_part = f" — Extended Attributes: `{ext_attr_key}`" if ext_attr_key else ""
                lines.append(f"##### (ENV ID: {env_id}) **{env_name}** — Type: `{env_type}` — Version: `{env_version}`{ext_attr_part}")

                # Jobs under this environment
                env_jobs = [job for job in project.jobs if job.environment_key == env.key]
                if env_jobs:
                    lines.append("")
                    lines.append(f"**{env_name} Jobs**")
                    lines.append("")
                    lines.append("| ID | Job Name | Type | Execute Steps |")
                    lines.append("|----|----------|------|---------------|")
                    for job in env_jobs:
                        job_name = getattr(job, "name", "Unnamed Job")
                        job_id = getattr(job, "id", "N/A")
                        
                        # Get job type from settings (more reliable than triggers)
                        job_settings = getattr(job, "settings", {})
                        job_type = job_settings.get("job_type", "other")
                        
                        # Get execute steps
                        execute_steps = getattr(job, "execute_steps", [])
                        if execute_steps:
                            steps_str = "<br>".join(f"`{step}`" for step in execute_steps)
                        else:
                            steps_str = "*None*"
                        
                        lines.append(f"| {job_id} | {job_name} | `{job_type}` | {steps_str} |")
                else:
                    lines.append("  ")
                    if env_type == "development":
                        lines.append("  - *No jobs configured. Development environment.*")
                    else:
                        lines.append("  - *No jobs configured.*")
                
                lines.append("")
            
            lines.append("")

        lines.append("")

    return "\n".join(lines)


def write_reports(snapshot: AccountSnapshot, output_dir: Path) -> tuple[Path, Path]:
    """Write both summary and detailed reports to timestamped markdown files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    account_id = snapshot.account_id

    summary_path = output_dir / f"account_{account_id}_summary__{timestamp}.md"
    report_path = output_dir / f"account_{account_id}_report__{timestamp}.md"

    summary_path.write_text(generate_summary_report(snapshot), encoding="utf-8")
    report_path.write_text(generate_detailed_report(snapshot), encoding="utf-8")

    return summary_path, report_path

