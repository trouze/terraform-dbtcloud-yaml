"""Interactive ERD viewer component using Cytoscape.js."""

from typing import Callable, Optional
import inspect
import json
import uuid

from nicegui import ui

from importer.web.utils.erd_graph_builder import (
    build_cytoscape_elements,
    build_cytoscape_style,
    export_to_mermaid,
    get_graph_stats,
    NODE_STYLES,
    TYPE_NAMES,
)


# Colors
DBT_ORANGE = "#FF694A"
DBT_TEAL = "#047377"


def create_erd_viewer(
    report_items: list[dict],
    on_node_click: Optional[Callable[[dict], None]] = None,
    is_target: bool = False,
) -> None:
    """Create the interactive ERD viewer tab content.
    
    Args:
        report_items: List of report item dictionaries
        on_node_click: Callback when a node is clicked
        is_target: Whether this is for target account (uses teal accent)
    """
    accent_color = DBT_TEAL if is_target else DBT_ORANGE
    
    if not report_items:
        with ui.card().classes("w-full p-6 text-center"):
            ui.icon("account_tree", size="2rem").classes("text-slate-400")
            ui.label("No data available for ERD").classes("text-slate-500 mt-2")
        return
    
    # Build graph data
    graph_data = build_cytoscape_elements(report_items)
    # Cytoscape.js expects a flat list of elements (nodes + edges)
    elements = graph_data.get("nodes", []) + graph_data.get("edges", [])
    style = build_cytoscape_style()
    stats = get_graph_stats(report_items)
    
    # Generate unique container ID for this instance (use underscore, not hyphen, for JS compatibility)
    container_id = f"cy_{uuid.uuid4().hex[:8]}"
    
    # State for filters
    filter_state = {
        "types": set(stats["by_type"].keys()),
        "search": "",
        "layout": "cose",
    }
    
    with ui.element("div").style(
        "display: grid; "
        "grid-template-rows: auto 1fr auto; "
        "width: 100%; "
        "height: 100%; "
        "gap: 8px; "
        "overflow: hidden;"
    ):
        # Toolbar
        with ui.card().classes("w-full p-2"):
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
                # Left: Search and filters
                with ui.row().classes("items-center gap-2"):
                    search_input = ui.input(
                        placeholder="Search resources...",
                    ).props("outlined dense clearable").classes("w-48")
                    
                    layout_select = ui.select(
                        options={
                            "cose": "Force-Directed",
                            "breadthfirst": "Hierarchical",
                            "grid": "Grid",
                            "circle": "Circle",
                        },
                        value="cose",
                        label="Layout",
                    ).props("outlined dense").classes("w-36")
                
                # Center: Stats
                with ui.row().classes("items-center gap-3"):
                    ui.label(f"{stats['total_nodes']} resources").classes("text-sm font-medium")
                    for type_code, count in sorted(stats["by_type"].items(), key=lambda x: -x[1])[:5]:
                        type_name = TYPE_NAMES.get(type_code, type_code)
                        color = NODE_STYLES.get(type_code, {}).get("color", "#6B7280")
                        with ui.row().classes("items-center gap-1"):
                            ui.element("span").style(
                                f"width: 8px; height: 8px; border-radius: 50%; background: {color};"
                            )
                            ui.label(f"{count}").classes("text-xs")
                
                # Right: Export buttons
                with ui.row().classes("items-center gap-2"):
                    async def export_mermaid():
                        mermaid_content = export_to_mermaid(report_items)
                        escaped = mermaid_content.replace('`', '\\`')
                        await ui.run_javascript(f'''
                            navigator.clipboard.writeText(`{escaped}`);
                        ''')
                        ui.notify("Mermaid copied to clipboard", type="positive")
                    
                    async def download_mermaid():
                        mermaid_content = export_to_mermaid(report_items)
                        escaped = mermaid_content.replace('`', '\\`')
                        await ui.run_javascript(f'''
                            const blob = new Blob([`{escaped}`], {{type: 'text/markdown'}});
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = 'erd_diagram.md';
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(url);
                        ''')
                        ui.notify("Downloaded erd_diagram.md", type="positive")
                    
                    ui.button(
                        "Copy Mermaid",
                        icon="content_copy",
                        on_click=export_mermaid,
                    ).props("flat dense size=sm")
                    
                    ui.button(
                        "Download",
                        icon="download",
                        on_click=download_mermaid,
                    ).props("flat dense size=sm")
        
        # Main graph area with "Load Graph" button
        graph_card = ui.card().classes("w-full h-full relative").style("min-height: 400px; flex: 1;")
        with graph_card:
            # State to track if graph is loaded
            graph_loaded = {"value": False}
            
            # Placeholder shown before graph loads
            placeholder = ui.column().classes("w-full h-full items-center justify-center").style("display: flex;")
            with placeholder:
                ui.icon("account_tree", size="4rem").classes("text-slate-400")
                ui.label("Entity Relationship Diagram").classes("text-xl font-medium text-slate-500 mt-4")
                ui.label(f"{stats['total_nodes']} resources ready to visualize").classes("text-sm text-slate-400 mt-2")
                
                load_button = ui.button(
                    "Load Graph",
                    icon="play_arrow",
                    on_click=lambda: None,  # Will be replaced
                ).classes("mt-6").style(f"background-color: {accent_color};")
            
            # Container for the graph - initially hidden via style (not class)
            graph_container_wrapper = ui.element("div").classes("w-full h-full").style(
                "display: none; min-height: 400px; width: 100%;"
            )
            with graph_container_wrapper:
                # Use ui.html with a real div that has the ID - this ensures it's in the DOM
                # Use absolute pixel dimensions to ensure Cytoscape has valid size
                html_content = (
                    f'<div id="{container_id}" style="width: 100%; height: 400px; '
                    'background: #1e293b; border-radius: 8px;"></div>'
                )
                if "sanitize" in inspect.signature(ui.html).parameters:
                    ui.html(html_content, sanitize=False)
                else:
                    ui.html(html_content)
            
            # Load Cytoscape and initialize graph
            # Use base64 encoding to safely transmit JSON data
            import base64
            elements_b64 = base64.b64encode(json.dumps(elements).encode()).decode()
            style_b64 = base64.b64encode(json.dumps(style).encode()).decode()
            
            async def init_cytoscape():
                """Initialize Cytoscape after the component is mounted."""
                try:
                    # Build JavaScript code using string concatenation to avoid escaping issues
                    cy_var = f"cy_{container_id}"
                    js_code = (
                        "(function() {\n"
                        "  const targetId = '" + container_id + "';\n"
                        "  const elements = JSON.parse(atob('" + elements_b64 + "'));\n"
                        "  const style = JSON.parse(atob('" + style_b64 + "'));\n"
                        "\n"
                        "  function initGraph(container) {\n"
                        "    if (!container) { console.error('ERD container not found'); return; }\n"
                        "    try {\n"
                        "      window." + cy_var + " = cytoscape({\n"
                        "        container: container,\n"
                        "        elements: elements,\n"
                        "        style: style,\n"
                        "        layout: { name: 'cose', animate: true, animationDuration: 500, randomize: false, componentSpacing: 100, nodeRepulsion: 10000, idealEdgeLength: 100 },\n"
                        "        wheelSensitivity: 0.3\n"
                        "      });\n"
                        "      console.log('Cytoscape graph created with', window." + cy_var + ".nodes().length, 'nodes');\n"
                        "      window." + cy_var + ".on('tap', 'node', function(evt) {\n"
                        "        window.dispatchEvent(new CustomEvent('erd-node-click', { detail: evt.target.data() }));\n"
                        "      });\n"
                        "    } catch (err) { console.error('Cytoscape init error:', err); }\n"
                        "  }\n"
                        "\n"
                        "  function waitAndInit() {\n"
                        "    const el = document.getElementById(targetId);\n"
                        "    if (el) { initGraph(el); return; }\n"
                        "    const observer = new MutationObserver(() => {\n"
                        "      const el = document.getElementById(targetId);\n"
                        "      if (el) { observer.disconnect(); initGraph(el); }\n"
                        "    });\n"
                        "    observer.observe(document.body, {childList: true, subtree: true});\n"
                        "  }\n"
                        "\n"
                        "  if (typeof cytoscape === 'undefined') {\n"
                        "    const script = document.createElement('script');\n"
                        "    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js';\n"
                        "    script.onload = waitAndInit;\n"
                        "    script.onerror = () => console.error('Failed to load Cytoscape');\n"
                        "    document.head.appendChild(script);\n"
                        "  } else {\n"
                        "    waitAndInit();\n"
                        "  }\n"
                        "})();"
                    )
                    await ui.run_javascript(js_code, timeout=10.0)
                except TimeoutError:
                    # Graph initialization is async, timeout is expected
                    pass
            
            # Schedule initialization after a small delay
            # Wire up the load button to init the graph
            async def on_load_click():
                if graph_loaded["value"]:
                    return
                graph_loaded["value"] = True
                load_button.disable()
                load_button.props("loading")
                # Hide placeholder, show graph container using style changes
                placeholder.style("display: none;")
                graph_container_wrapper.style("display: block; width: 100%; min-height: 400px;")
                # Small delay to let the DOM update before initializing Cytoscape
                await ui.run_javascript("await new Promise(r => setTimeout(r, 100));", timeout=2.0)
                await init_cytoscape()
            
            load_button.on("click", on_load_click)
            
            # Graph controls overlay
            with ui.row().classes("absolute bottom-4 right-4 gap-2"):
                async def zoom_in():
                    try:
                        await ui.run_javascript(f'if(window.cy_{container_id}) window.cy_{container_id}.zoom(window.cy_{container_id}.zoom() * 1.2);', timeout=5.0)
                    except TimeoutError:
                        pass
                
                async def zoom_out():
                    try:
                        await ui.run_javascript(f'if(window.cy_{container_id}) window.cy_{container_id}.zoom(window.cy_{container_id}.zoom() / 1.2);', timeout=5.0)
                    except TimeoutError:
                        pass
                
                async def fit_graph():
                    try:
                        await ui.run_javascript(f'if(window.cy_{container_id}) window.cy_{container_id}.fit(50);', timeout=5.0)
                    except TimeoutError:
                        pass
                
                async def reset_layout():
                    layout = filter_state.get("layout", "cose")
                    try:
                        await ui.run_javascript(f'''
                            if(window.cy_{container_id}) {{
                                window.cy_{container_id}.layout({{
                                    name: '{layout}',
                                    animate: true,
                                    animationDuration: 500,
                                }}).run();
                            }}
                        ''', timeout=5.0)
                    except TimeoutError:
                        pass
                
                ui.button(icon="remove", on_click=zoom_out).props("round dense size=sm")
                ui.button(icon="add", on_click=zoom_in).props("round dense size=sm")
                ui.button(icon="fit_screen", on_click=fit_graph).props("round dense size=sm")
                ui.button(icon="refresh", on_click=reset_layout).props("round dense size=sm")
            
            # Search handler
            async def on_search_change(e):
                # NiceGUI's update:model-value passes value in e.args
                search_term = e.args if isinstance(e.args, str) else (e.args or "")
                filter_state["search"] = search_term
                
                try:
                    if not search_term:
                        # Show all nodes
                        await ui.run_javascript(f'''
                            if(window.cy_{container_id}) {{
                                window.cy_{container_id}.nodes().style('opacity', 1);
                                window.cy_{container_id}.edges().style('opacity', 0.7);
                            }}
                        ''', timeout=5.0)
                    else:
                        # Filter nodes
                        escaped_term = search_term.replace("'", "\\'").lower()
                        await ui.run_javascript(f'''
                            if(window.cy_{container_id}) {{
                                window.cy_{container_id}.nodes().forEach(node => {{
                                    const label = (node.data('label') || '').toLowerCase();
                                    const match = label.includes('{escaped_term}');
                                    node.style('opacity', match ? 1 : 0.2);
                                }});
                                window.cy_{container_id}.edges().style('opacity', 0.2);
                            }}
                        ''', timeout=5.0)
                except TimeoutError:
                    pass
            
            search_input.on("update:model-value", on_search_change)
            
            # Layout change handler
            async def on_layout_change(e):
                # NiceGUI's update:model-value passes value in e.args
                layout = e.args if isinstance(e.args, str) else "cose"
                filter_state["layout"] = layout
                try:
                    await ui.run_javascript(f'''
                        if(window.cy_{container_id}) {{
                            window.cy_{container_id}.layout({{
                                name: '{layout}',
                                animate: true,
                                animationDuration: 500,
                            }}).run();
                        }}
                    ''', timeout=5.0)
                except TimeoutError:
                    pass
            
            layout_select.on("update:model-value", on_layout_change)
        
        # Legend
        with ui.card().classes("w-full p-2"):
            with ui.row().classes("w-full items-center justify-center gap-6 flex-wrap"):
                ui.label("Legend:").classes("text-xs font-medium text-slate-500")
                for type_code, info in sorted(NODE_STYLES.items(), key=lambda x: x[0]):
                    type_name = TYPE_NAMES.get(type_code, type_code)
                    count = stats["by_type"].get(type_code, 0)
                    if count > 0:
                        with ui.row().classes("items-center gap-1"):
                            ui.element("span").style(
                                f"width: 12px; height: 12px; background: {info['color']}; "
                                f"border-radius: 2px;"
                            )
                            ui.label(f"{type_name} ({count})").classes("text-xs")
                
                ui.element("span").classes("mx-2 text-slate-300")
                
                # Edge types
                with ui.row().classes("items-center gap-1"):
                    ui.element("span").style(
                        "width: 20px; height: 2px; background: #64748B;"
                    )
                    ui.label("Contains").classes("text-xs text-slate-500")
                
                with ui.row().classes("items-center gap-1"):
                    ui.element("span").style(
                        "width: 20px; height: 2px; background: #10B981; border-style: dashed;"
                    )
                    ui.label("Executes In").classes("text-xs text-slate-500")
                
                with ui.row().classes("items-center gap-1"):
                    ui.element("span").style(
                        "width: 20px; height: 2px; background: #3B82F6; border-style: dotted;"
                    )
                    ui.label("Triggers").classes("text-xs text-slate-500")
