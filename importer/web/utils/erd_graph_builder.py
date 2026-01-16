"""Build Cytoscape.js graph data from dbt Cloud resource data."""

import json
import time
from typing import Any

# #region agent log
_LOG_PATH = "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log"


def _log_debug(
    location: str,
    message: str,
    data: dict,
    hypothesis_id: str,
    run_id: str = "run1",
) -> None:
    payload = {
        "sessionId": "debug-session",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with open(_LOG_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(payload) + "\n")

# #endregion


# Node styles by resource type
NODE_STYLES = {
    "ACC": {"shape": "round-rectangle", "color": "#3B82F6", "icon": "cloud"},
    "CON": {"shape": "diamond", "color": "#8B5CF6", "icon": "cable"},
    "REP": {"shape": "octagon", "color": "#F59E0B", "icon": "source"},
    "TOK": {"shape": "tag", "color": "#EC4899", "icon": "key"},
    "GRP": {"shape": "ellipse", "color": "#6366F1", "icon": "group"},
    "NOT": {"shape": "rectangle", "color": "#F97316", "icon": "notifications"},
    "WEB": {"shape": "rectangle", "color": "#84CC16", "icon": "webhook"},
    "PLE": {"shape": "rectangle", "color": "#14B8A6", "icon": "lock"},
    "PRJ": {"shape": "round-rectangle", "color": "#FF694A", "icon": "folder"},
    "ENV": {"shape": "ellipse", "color": "#10B981", "icon": "cloud"},
    "VAR": {"shape": "rectangle", "color": "#64748B", "icon": "code"},
    "JOB": {"shape": "hexagon", "color": "#3B82F6", "icon": "play_circle"},
}

# Type display names
TYPE_NAMES = {
    "ACC": "Account",
    "CON": "Connection",
    "REP": "Repository",
    "TOK": "Service Token",
    "GRP": "Group",
    "NOT": "Notification",
    "WEB": "Webhook",
    "PLE": "PrivateLink",
    "PRJ": "Project",
    "ENV": "Environment",
    "VAR": "Env Variable",
    "JOB": "Job",
}


def build_cytoscape_elements(report_items: list[dict]) -> dict:
    """Build Cytoscape.js elements (nodes and edges) from report items.
    
    Args:
        report_items: List of report item dictionaries from fetch
        
    Returns:
        Dictionary with 'nodes' and 'edges' lists for Cytoscape.js
    """
    # #region agent log
    _log_debug(
        "erd_graph_builder.py:build_cytoscape_elements:entry",
        "build_cytoscape_elements entry",
        {
            "report_items_count": len(report_items),
            "none_key_count": sum(1 for item in report_items if item.get("key") is None),
        },
        "H2",
    )
    # #endregion

    nodes = []
    edges = []
    
    # Build lookup maps
    items_by_key = {item.get("key"): item for item in report_items if item.get("key")}
    items_by_id = {}
    for item in report_items:
        dbt_id = item.get("dbt_id")
        type_code = item.get("element_type_code", "")
        if dbt_id:
            items_by_id[(type_code, dbt_id)] = item
    
    # Track which projects have which children
    project_children = {}  # project_key -> {type -> count}
    
    for item in report_items:
        key = item.get("key", "")
        name = item.get("name", "Unknown")
        type_code = item.get("element_type_code", "UNK")
        dbt_id = item.get("dbt_id")
        project_name = item.get("project_name", "")
        parent_key = item.get("parent_key", "")
        
        if not key:
            continue
        
        # Get style for this type
        style = NODE_STYLES.get(type_code, {"shape": "rectangle", "color": "#6B7280", "icon": "help"})
        
        # Build node data
        node = {
            "data": {
                "id": key,
                "label": name,
                "type": type_code,
                "typeName": TYPE_NAMES.get(type_code, type_code),
                "dbtId": dbt_id,
                "projectName": project_name,
                "color": style["color"],
                "shape": style["shape"],
            }
        }
        nodes.append(node)
        
        # Track children for project nodes
        if parent_key and parent_key.startswith("PRJ:"):
            if parent_key not in project_children:
                project_children[parent_key] = {}
            type_name = TYPE_NAMES.get(type_code, type_code)
            project_children[parent_key][type_name] = project_children[parent_key].get(type_name, 0) + 1
        
        # Create edges based on relationships
        
        # Parent-child relationship (project -> environment/job/etc)
        if parent_key and parent_key in items_by_key:
            edges.append({
                "data": {
                    "id": f"{parent_key}_to_{key}",
                    "source": parent_key,
                    "target": key,
                    "relationship": "contains",
                    "style": "solid",
                }
            })
        
        # Job -> Environment relationship (execution environment)
        if type_code == "JOB":
            env_id = item.get("environment_id")
            if env_id:
                # Find the environment by ID
                env_item = items_by_id.get(("ENV", env_id))
                if env_item:
                    edges.append({
                        "data": {
                            "id": f"{key}_executes_in_{env_item.get('key')}",
                            "source": key,
                            "target": env_item.get("key"),
                            "relationship": "executes_in",
                            "style": "dashed",
                        }
                    })
        
        # Job completion triggers
        if type_code == "JOB":
            triggers = item.get("job_completion_trigger_condition", {})
            if triggers:
                trigger_jobs = triggers.get("job_id") or []
                if isinstance(trigger_jobs, int):
                    trigger_jobs = [trigger_jobs]
                for trigger_job_id in trigger_jobs:
                    trigger_job = items_by_id.get(("JOB", trigger_job_id))
                    if trigger_job:
                        edges.append({
                            "data": {
                                "id": f"{trigger_job.get('key')}_triggers_{key}",
                                "source": trigger_job.get("key"),
                                "target": key,
                                "relationship": "triggers",
                                "style": "dotted",
                            }
                        })
        
        # Environment -> Connection relationship
        if type_code == "ENV":
            conn_id = item.get("connection_id")
            if conn_id:
                conn_item = items_by_id.get(("CON", conn_id))
                if conn_item:
                    edges.append({
                        "data": {
                            "id": f"{key}_uses_{conn_item.get('key')}",
                            "source": key,
                            "target": conn_item.get("key"),
                            "relationship": "uses",
                            "style": "dashed",
                        }
                    })
    
    # Update project nodes with child counts
    for node in nodes:
        if node["data"]["type"] == "PRJ":
            key = node["data"]["id"]
            children = project_children.get(key, {})
            if children:
                child_summary = ", ".join(f"{count} {t}" for t, count in sorted(children.items()))
                node["data"]["childSummary"] = child_summary
    
    # #region agent log
    _log_debug(
        "erd_graph_builder.py:build_cytoscape_elements:exit",
        "build_cytoscape_elements exit",
        {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes_without_id": sum(
                1 for node in nodes if not node.get("data", {}).get("id")
            ),
        },
        "H2",
    )
    # #endregion

    return {"nodes": nodes, "edges": edges}


def build_cytoscape_style() -> list[dict]:
    """Build Cytoscape.js stylesheet.
    
    Returns:
        List of style objects for Cytoscape.js
    """
    return [
        # Base node style
        {
            "selector": "node",
            "style": {
                "label": "data(label)",
                "background-color": "data(color)",
                "shape": "data(shape)",
                "text-valign": "bottom",
                "text-halign": "center",
                "font-size": "10px",
                "text-margin-y": "4px",
                "width": "40px",
                "height": "40px",
                "border-width": "2px",
                "border-color": "#ffffff",
            }
        },
        # Project nodes (larger)
        {
            "selector": "node[type='PRJ']",
            "style": {
                "width": "60px",
                "height": "60px",
                "font-size": "12px",
                "font-weight": "bold",
            }
        },
        # Selected node
        {
            "selector": "node:selected",
            "style": {
                "border-width": "4px",
                "border-color": "#FF694A",
                "overlay-opacity": 0.2,
            }
        },
        # Edges
        {
            "selector": "edge",
            "style": {
                "width": "2px",
                "line-color": "#94A3B8",
                "target-arrow-color": "#94A3B8",
                "target-arrow-shape": "triangle",
                "curve-style": "bezier",
                "opacity": 0.7,
            }
        },
        # Contains edges (solid)
        {
            "selector": "edge[relationship='contains']",
            "style": {
                "line-style": "solid",
                "line-color": "#64748B",
            }
        },
        # Executes in edges (dashed)
        {
            "selector": "edge[relationship='executes_in']",
            "style": {
                "line-style": "dashed",
                "line-color": "#10B981",
            }
        },
        # Triggers edges (dotted)
        {
            "selector": "edge[relationship='triggers']",
            "style": {
                "line-style": "dotted",
                "line-color": "#3B82F6",
                "target-arrow-shape": "triangle-backcurve",
            }
        },
        # Uses edges (dashed)
        {
            "selector": "edge[relationship='uses']",
            "style": {
                "line-style": "dashed",
                "line-color": "#8B5CF6",
            }
        },
    ]


def export_to_mermaid(report_items: list[dict]) -> str:
    """Export graph as Mermaid diagram syntax.
    
    Args:
        report_items: List of report item dictionaries
        
    Returns:
        Mermaid diagram string
    """
    # #region agent log
    _log_debug(
        "erd_graph_builder.py:export_to_mermaid:entry",
        "export_to_mermaid entry",
        {
            "report_items_count": len(report_items),
            "none_key_count": sum(1 for item in report_items if item.get("key") is None),
        },
        "H3",
    )
    # #endregion

    lines = ["```mermaid", "flowchart TD"]
    
    # Build lookup
    items_by_key = {item.get("key"): item for item in report_items if item.get("key")}
    
    # Add nodes grouped by project
    projects = [item for item in report_items if item.get("element_type_code") == "PRJ"]
    globals_items = [
        item
        for item in report_items
        if not item.get("parent_key")
        and item.get("element_type_code") not in ("PRJ", "ACC")
    ]
    # #region agent log
    _log_debug(
        "erd_graph_builder.py:export_to_mermaid:globals",
        "export_to_mermaid globals computed",
        {
            "globals_count": len(globals_items),
            "globals_none_key_count": sum(
                1 for item in globals_items if item.get("key") is None
            ),
        },
        "H3",
    )
    # #endregion
    
    # Subgraph for each project
    for project in projects:
        proj_key = project.get("key", "")
        proj_name = project.get("name", "Unknown")
        safe_name = proj_name.replace('"', "'").replace(" ", "_")
        
        lines.append(f"    subgraph {safe_name}[{proj_name}]")
        
        # Add project children
        for item in report_items:
            if item.get("parent_key") == proj_key:
                item_key = (item.get("key") or "").replace(":", "_").replace("-", "_")
                item_name = item.get("name", "Unknown")
                item_type = item.get("element_type_code", "")
                
                # Choose shape based on type
                if item_type == "ENV":
                    lines.append(f'        {item_key}["{item_name}"]')
                elif item_type == "JOB":
                    lines.append(f'        {item_key}{{{{"{item_name}"}}}}')
                elif item_type == "VAR":
                    lines.append(f'        {item_key}[/"{item_name}"/]')
                else:
                    lines.append(f'        {item_key}("{item_name}")')
        
        lines.append("    end")
    
    # Subgraph for globals
    if globals_items:
        lines.append("    subgraph Globals")
        for item in globals_items:
            item_key = (item.get("key") or "").replace(":", "_").replace("-", "_")
            item_name = item.get("name", "Unknown")
            lines.append(f'        {item_key}["{item_name}"]')
        lines.append("    end")
    
    # Add edges
    # #region agent log
    _log_debug(
        "erd_graph_builder.py:export_to_mermaid:edges",
        "export_to_mermaid building edges",
        {
            "report_items_count": len(report_items),
        },
        "H3",
    )
    # #endregion

    for item in report_items:
        item_key = (item.get("key") or "").replace(":", "_").replace("-", "_")
        item_type = item.get("element_type_code") or ""
        
        # Job -> Environment
        if item_type == "JOB":
            env_id = item.get("environment_id")
            if env_id:
                for other in report_items:
                    if other.get("element_type_code") == "ENV" and other.get("dbt_id") == env_id:
                        other_key = (other.get("key") or "").replace(":", "_").replace("-", "_")
                        lines.append(f"    {item_key} -.-> {other_key}")
                        break
    
    lines.append("```")
    return "\n".join(lines)


def get_graph_stats(report_items: list[dict]) -> dict:
    """Get statistics about the graph.
    
    Args:
        report_items: List of report item dictionaries
        
    Returns:
        Dictionary with node/edge counts by type
    """
    type_counts = {}
    for item in report_items:
        type_code = item.get("element_type_code", "UNK")
        type_counts[type_code] = type_counts.get(type_code, 0) + 1
    
    return {
        "total_nodes": len(report_items),
        "by_type": type_counts,
        "type_names": {k: TYPE_NAMES.get(k, k) for k in type_counts.keys()},
    }
