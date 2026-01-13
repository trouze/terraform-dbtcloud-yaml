"""Chart components using Plotly for data visualization."""

from collections import Counter
from typing import Any, Optional

from nicegui import ui

from importer.web.state import AppState


# dbt brand-inspired color palette
CHART_COLORS = [
    "#FF694A",  # dbt orange
    "#3B82F6",  # blue
    "#10B981",  # green
    "#F59E0B",  # amber
    "#8B5CF6",  # purple
    "#EC4899",  # pink
    "#06B6D4",  # cyan
    "#EF4444",  # red
    "#14B8A6",  # teal
    "#F97316",  # orange
]

# Type display names
TYPE_NAMES = {
    "ACC": "Account",
    "CON": "Connections",
    "REP": "Repositories",
    "PRJ": "Projects",
    "ENV": "Environments",
    "JOB": "Jobs",
    "TOK": "Service Tokens",
    "GRP": "Groups",
    "NOT": "Notifications",
    "WEB": "Webhooks",
    "PLE": "PrivateLink",
    "EVR": "Env Variables",
}


def create_charts(report_items: list, state: AppState) -> None:
    """Create all chart visualizations."""
    
    # Calculate data for charts
    type_counts = Counter(item.get("element_type_code", "UNK") for item in report_items)
    
    # Exclude ACC (single account) from charts
    type_counts.pop("ACC", None)
    
    # Get project data for treemap
    project_job_counts = _get_project_job_counts(report_items)
    
    # Get connection types for pie chart  
    connection_types = _get_connection_types(report_items)
    
    with ui.row().classes("w-full gap-4 flex-wrap"):
        # Bar chart - Resource distribution
        with ui.card().classes("flex-1 min-w-[400px] p-4"):
            ui.label("Resource Distribution by Type").classes("text-lg font-semibold mb-2")
            _create_bar_chart(type_counts)
        
        # Pie chart - Connection types (if any connections)
        if connection_types:
            with ui.card().classes("flex-1 min-w-[400px] p-4"):
                ui.label("Connection Types").classes("text-lg font-semibold mb-2")
                _create_pie_chart(connection_types)
    
    # Treemap - Jobs by project (if any jobs)
    if project_job_counts:
        with ui.card().classes("w-full p-4 mt-4"):
            ui.label("Jobs by Project").classes("text-lg font-semibold mb-2")
            _create_treemap(project_job_counts)
    
    # Include/Exclude breakdown
    include_counts = _get_include_breakdown(report_items)
    with ui.card().classes("w-full p-4 mt-4"):
        ui.label("Included vs Excluded Resources").classes("text-lg font-semibold mb-2")
        _create_inclusion_chart(include_counts)


def _get_project_job_counts(report_items: list) -> dict:
    """Get job counts per project."""
    project_jobs = {}
    for item in report_items:
        if item.get("element_type_code") == "JOB":
            project_name = item.get("project_name", "Unknown Project")
            project_jobs[project_name] = project_jobs.get(project_name, 0) + 1
    return project_jobs


def _get_connection_types(report_items: list) -> dict:
    """Get connection type distribution (mock - would need actual data)."""
    # Connection items have element_type_code = "CON"
    # The actual type (snowflake, databricks, etc.) would be in the full data
    # For now, we'll just count connections
    connections = [item for item in report_items if item.get("element_type_code") == "CON"]
    if not connections:
        return {}
    
    # Try to extract type from name patterns (heuristic)
    type_counts = {"Other": 0}
    for conn in connections:
        name = conn.get("name", "").lower()
        if "snowflake" in name:
            type_counts["Snowflake"] = type_counts.get("Snowflake", 0) + 1
        elif "databricks" in name:
            type_counts["Databricks"] = type_counts.get("Databricks", 0) + 1
        elif "bigquery" in name or "bq" in name:
            type_counts["BigQuery"] = type_counts.get("BigQuery", 0) + 1
        elif "redshift" in name:
            type_counts["Redshift"] = type_counts.get("Redshift", 0) + 1
        elif "postgres" in name:
            type_counts["PostgreSQL"] = type_counts.get("PostgreSQL", 0) + 1
        else:
            type_counts["Other"] += 1
    
    # Remove "Other" if 0
    if type_counts["Other"] == 0:
        del type_counts["Other"]
    
    return type_counts


def _get_include_breakdown(report_items: list) -> dict:
    """Get breakdown of included vs excluded by type."""
    breakdown = {}
    for item in report_items:
        type_code = item.get("element_type_code", "UNK")
        if type_code == "ACC":
            continue
        if type_code not in breakdown:
            breakdown[type_code] = {"included": 0, "excluded": 0}
        if item.get("include_in_conversion", True):
            breakdown[type_code]["included"] += 1
        else:
            breakdown[type_code]["excluded"] += 1
    return breakdown


def _create_bar_chart(type_counts: Counter) -> None:
    """Create a bar chart of resource counts by type."""
    import plotly.graph_objects as go
    
    # Sort by count descending
    sorted_items = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
    
    labels = [TYPE_NAMES.get(t, t) for t, _ in sorted_items]
    values = [v for _, v in sorted_items]
    colors = CHART_COLORS[:len(labels)]
    
    fig = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=values,
            textposition="outside",
        )
    ])
    
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=60),
        height=300,
        xaxis_tickangle=-45,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.2)"),
    )
    
    ui.plotly(fig).classes("w-full")


def _create_pie_chart(type_counts: dict) -> None:
    """Create a pie chart of connection types."""
    import plotly.graph_objects as go
    
    labels = list(type_counts.keys())
    values = list(type_counts.values())
    
    fig = go.Figure(data=[
        go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker_colors=CHART_COLORS[:len(labels)],
            textinfo="label+percent",
            textposition="outside",
        )
    ])
    
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
    )
    
    ui.plotly(fig).classes("w-full")


def _create_treemap(project_job_counts: dict) -> None:
    """Create a treemap of jobs grouped by project."""
    import plotly.express as px
    
    # Build data for treemap
    labels = []
    parents = []
    values = []
    
    # Root
    labels.append("All Projects")
    parents.append("")
    values.append(sum(project_job_counts.values()))
    
    # Projects
    for project, count in sorted(project_job_counts.items(), key=lambda x: x[1], reverse=True):
        labels.append(project)
        parents.append("All Projects")
        values.append(count)
    
    fig = px.treemap(
        names=labels,
        parents=parents,
        values=values,
        color_discrete_sequence=CHART_COLORS,
    )
    
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
    )
    
    fig.update_traces(
        textinfo="label+value",
        hovertemplate="<b>%{label}</b><br>Jobs: %{value}<extra></extra>",
    )
    
    ui.plotly(fig).classes("w-full")


def _create_inclusion_chart(breakdown: dict) -> None:
    """Create a stacked bar chart of included vs excluded resources."""
    import plotly.graph_objects as go
    
    # Sort by total descending
    sorted_items = sorted(
        breakdown.items(),
        key=lambda x: x[1]["included"] + x[1]["excluded"],
        reverse=True
    )
    
    labels = [TYPE_NAMES.get(t, t) for t, _ in sorted_items]
    included = [v["included"] for _, v in sorted_items]
    excluded = [v["excluded"] for _, v in sorted_items]
    
    fig = go.Figure(data=[
        go.Bar(
            name="Included",
            x=labels,
            y=included,
            marker_color="#10B981",
        ),
        go.Bar(
            name="Excluded",
            x=labels,
            y=excluded,
            marker_color="#EF4444",
        ),
    ])
    
    fig.update_layout(
        barmode="stack",
        margin=dict(l=20, r=20, t=20, b=60),
        height=250,
        xaxis_tickangle=-45,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.2)"),
    )
    
    ui.plotly(fig).classes("w-full")
