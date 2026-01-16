"""Utility for exporting content as Markdown files."""

from datetime import datetime
from pathlib import Path
from typing import Optional


def format_summary_as_markdown(
    content: str,
    account_name: str,
    account_id: str = "",
    host_url: str = "",
) -> str:
    """Format summary content as a downloadable Markdown file.
    
    Args:
        content: The raw summary content (already markdown)
        account_name: Name of the account
        account_id: ID of the account
        host_url: Host URL of the account
        
    Returns:
        Formatted Markdown string with header
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    header_lines = [
        "# dbt Cloud Account Summary",
        "",
        f"**Account:** {account_name or 'Unknown'}",
    ]
    
    if account_id:
        header_lines.append(f"**Account ID:** {account_id}")
    if host_url:
        header_lines.append(f"**Host URL:** {host_url}")
    
    header_lines.extend([
        f"**Generated:** {timestamp}",
        "",
        "---",
        "",
    ])
    
    return "\n".join(header_lines) + content


def format_report_as_markdown(
    content: str,
    account_name: str,
    account_id: str = "",
    host_url: str = "",
) -> str:
    """Format report content as a downloadable Markdown file.
    
    Args:
        content: The raw report content (already markdown)
        account_name: Name of the account
        account_id: ID of the account
        host_url: Host URL of the account
        
    Returns:
        Formatted Markdown string with header
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    header_lines = [
        "# dbt Cloud Account Report",
        "",
        f"**Account:** {account_name or 'Unknown'}",
    ]
    
    if account_id:
        header_lines.append(f"**Account ID:** {account_id}")
    if host_url:
        header_lines.append(f"**Host URL:** {host_url}")
    
    header_lines.extend([
        f"**Generated:** {timestamp}",
        "",
        "---",
        "",
    ])
    
    return "\n".join(header_lines) + content


def format_entities_as_markdown(
    report_items: list[dict],
    account_name: str,
    account_id: str = "",
    host_url: str = "",
) -> str:
    """Format entity data as a Markdown table.
    
    Args:
        report_items: List of report item dictionaries
        account_name: Name of the account
        account_id: ID of the account
        host_url: Host URL of the account
        
    Returns:
        Formatted Markdown string with tables
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    lines = [
        "# dbt Cloud Account Entities",
        "",
        f"**Account:** {account_name or 'Unknown'}",
    ]
    
    if account_id:
        lines.append(f"**Account ID:** {account_id}")
    if host_url:
        lines.append(f"**Host URL:** {host_url}")
    
    lines.extend([
        f"**Generated:** {timestamp}",
        f"**Total Entities:** {len(report_items)}",
        "",
        "---",
        "",
    ])
    
    # Group entities by type
    entities_by_type: dict[str, list[dict]] = {}
    for item in report_items:
        type_code = item.get("element_type_code", "Unknown")
        if type_code not in entities_by_type:
            entities_by_type[type_code] = []
        entities_by_type[type_code].append(item)
    
    # Resource type display names
    type_names = {
        "ACC": "Account",
        "CON": "Connections",
        "REP": "Repositories",
        "TOK": "Service Tokens",
        "GRP": "Groups",
        "NOT": "Notifications",
        "WEB": "Webhooks",
        "PLE": "PrivateLink Endpoints",
        "PRJ": "Projects",
        "ENV": "Environments",
        "VAR": "Environment Variables",
        "JOB": "Jobs",
    }
    
    # Summary table
    lines.extend([
        "## Resource Counts",
        "",
        "| Resource Type | Count |",
        "|--------------|-------|",
    ])
    
    for type_code in sorted(entities_by_type.keys()):
        type_name = type_names.get(type_code, type_code)
        count = len(entities_by_type[type_code])
        lines.append(f"| {type_name} | {count} |")
    
    lines.append("")
    
    # Detailed tables by type
    for type_code in sorted(entities_by_type.keys()):
        type_name = type_names.get(type_code, type_code)
        items = entities_by_type[type_code]
        
        lines.extend([
            f"## {type_name}",
            "",
            "| Name | ID | Project | Key |",
            "|------|----|---------|----|",
        ])
        
        for item in sorted(items, key=lambda x: x.get("name", "")):
            name = item.get("name", "N/A")
            dbt_id = item.get("dbt_id", "N/A")
            project = item.get("project_name", "-")
            key = item.get("key", "-")
            # Escape pipe characters in values
            name = str(name).replace("|", "\\|")
            project = str(project).replace("|", "\\|")
            key = str(key).replace("|", "\\|")
            lines.append(f"| {name} | {dbt_id} | {project} | {key} |")
        
        lines.append("")
    
    return "\n".join(lines)


def generate_download_filename(
    prefix: str,
    account_name: str,
    extension: str = "md",
) -> str:
    """Generate a filename for download.
    
    Args:
        prefix: Prefix like "summary" or "report"
        account_name: Account name to include in filename
        extension: File extension (default "md")
        
    Returns:
        Filename string
    """
    # Sanitize account name for filename
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in account_name)
    safe_name = safe_name[:50]  # Limit length
    
    timestamp = datetime.now().strftime("%Y-%m-%d")
    
    return f"{prefix}_{safe_name}_{timestamp}.{extension}"
