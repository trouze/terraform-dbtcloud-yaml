"""Utilities for viewing and analyzing YAML configuration files."""

from pathlib import Path
from typing import Any, Dict, Optional, Callable

import yaml
from nicegui import ui


def load_yaml_file(yaml_path: str) -> Optional[Dict[str, Any]]:
    """Load and parse a YAML file.

    Args:
        yaml_path: Path to the YAML file

    Returns:
        Parsed YAML data or None if file doesn't exist
    """
    path = Path(yaml_path)
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def get_yaml_stats(yaml_path: str) -> Dict[str, int]:
    """Extract resource counts from a normalized YAML file.

    Args:
        yaml_path: Path to the YAML file

    Returns:
        Dictionary with resource type counts
    """
    data = load_yaml_file(yaml_path)
    if not data:
        return {}

    stats = {}

    # Count global resources
    globals_data = data.get("globals", {})
    stats["connections"] = len(globals_data.get("connections", []))
    stats["repositories"] = len(globals_data.get("repositories", []))
    stats["privatelink_endpoints"] = len(globals_data.get("privatelink_endpoints", []))
    stats["service_tokens"] = len(globals_data.get("service_tokens", []))
    stats["groups"] = len(globals_data.get("groups", []))
    stats["notifications"] = len(globals_data.get("notifications", []))

    # Count project-level resources
    projects = data.get("projects", [])
    stats["projects"] = len(projects)

    environments = 0
    jobs = 0
    env_vars = 0

    for project in projects:
        environments += len(project.get("environments", []))
        jobs += len(project.get("jobs", []))
        env_vars += len(project.get("environment_variables", []))

    stats["environments"] = environments
    stats["jobs"] = jobs
    stats["environment_variables"] = env_vars

    return stats


def get_yaml_content(yaml_path: str) -> str:
    """Read raw YAML file content.

    Args:
        yaml_path: Path to the YAML file

    Returns:
        File content as string or error message
    """
    path = Path(yaml_path)
    if not path.exists():
        return f"# File not found: {yaml_path}"

    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"# Error reading file: {e}"


def create_yaml_viewer_dialog(
    yaml_path: str,
    title: str = "YAML Configuration",
) -> ui.dialog:
    """Create a dialog for viewing YAML content with search functionality.

    Args:
        yaml_path: Path to the YAML file
        title: Dialog title

    Returns:
        The dialog element (call .open() to show it)
    """
    content = get_yaml_content(yaml_path)
    stats = get_yaml_stats(yaml_path)

    # Search state
    search_results = {"count": 0, "current": 0}

    with ui.dialog() as dialog:
        dialog.props("maximized")

        with ui.card().classes("w-full h-full").style("display: flex; flex-direction: column;"):
            # Header
            with ui.row().classes("w-full items-center justify-between mb-2"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("description", size="lg").classes("text-orange-500")
                    ui.label(title).classes("text-xl font-bold")

                ui.button(icon="close", on_click=dialog.close).props("flat round")

            # Stats bar
            if stats:
                with ui.row().classes("w-full gap-4 mb-2 p-3 bg-slate-100 dark:bg-slate-800 rounded flex-wrap"):
                    for resource, count in stats.items():
                        if count > 0:
                            with ui.column().classes("items-center min-w-[60px]"):
                                ui.label(str(count)).classes("text-lg font-bold")
                                ui.label(resource.replace("_", " ").title()).classes(
                                    "text-xs text-slate-500"
                                )

            # File path and char count
            with ui.row().classes("items-center justify-between gap-2 mb-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("folder", size="xs").classes("text-slate-500")
                    ui.label(yaml_path).classes("text-xs text-slate-500 font-mono")
                ui.label(f"{len(content):,} chars").classes("text-xs text-slate-400")

            # Search input with result count and navigation
            with ui.row().classes("w-full mb-2 items-center gap-2"):
                search_input = ui.input(
                    placeholder="Search in YAML...",
                ).props("outlined dense clearable").classes("flex-1")

                # Navigation buttons (hidden initially)
                with ui.row().classes("items-center gap-1"):
                    prev_btn = ui.button(
                        icon="keyboard_arrow_up",
                        on_click=lambda: None,
                    ).props("flat dense round size=sm").classes("hidden")
                    next_btn = ui.button(
                        icon="keyboard_arrow_down",
                        on_click=lambda: None,
                    ).props("flat dense round size=sm").classes("hidden")

                search_count_label = ui.label("").classes("text-xs text-slate-400 min-w-[80px]")

            # YAML content with syntax highlighting
            with ui.scroll_area().classes("w-full").style("flex: 1; min-height: 0;"):
                ui.code(content, language="yaml").classes("w-full text-sm yaml-viewer-code")

            # JavaScript for search highlighting
            async def on_search(e):
                search_term = e.args if e.args else ""
                if not search_term:
                    search_count_label.set_text("")
                    search_results["count"] = 0
                    search_results["current"] = 0
                    prev_btn.classes("hidden", remove=False)
                    next_btn.classes("hidden", remove=False)
                    # Clear highlights
                    await ui.run_javascript('''
                        document.querySelectorAll('.yaml-viewer-code mark').forEach(m => {
                            m.outerHTML = m.textContent;
                        });
                    ''')
                    return

                # Count matches
                count = content.lower().count(search_term.lower())
                search_results["count"] = count
                search_results["current"] = 1 if count > 0 else 0

                if count > 1:
                    search_count_label.set_text(f"1 of {count}")
                    prev_btn.classes(remove="hidden")
                    next_btn.classes(remove="hidden")
                elif count == 1:
                    search_count_label.set_text("1 of 1")
                    prev_btn.classes("hidden", remove=False)
                    next_btn.classes("hidden", remove=False)
                else:
                    search_count_label.set_text("No matches")
                    prev_btn.classes("hidden", remove=False)
                    next_btn.classes("hidden", remove=False)

                # Highlight matches using JavaScript
                escaped_term = search_term.replace("'", "\\'").replace('"', '\\"')
                await ui.run_javascript(f'''
                    const codeEl = document.querySelector('.yaml-viewer-code code');
                    if (codeEl) {{
                        // Restore original text first
                        const originalText = codeEl.textContent;
                        const regex = new RegExp('({escaped_term})', 'gi');
                        const highlighted = originalText.replace(regex, '<mark class="bg-yellow-300 dark:bg-yellow-600">$1</mark>');
                        codeEl.innerHTML = highlighted;
                        // Scroll to first match
                        const firstMark = document.querySelector('.yaml-viewer-code mark');
                        if (firstMark) {{
                            firstMark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                            firstMark.classList.add('ring-2', 'ring-orange-500');
                        }}
                    }}
                ''')

            async def go_to_match(direction):
                count = search_results["count"]
                if count <= 1:
                    return

                current = search_results["current"]
                if direction == "next":
                    new_idx = current + 1 if current < count else 1
                else:
                    new_idx = current - 1 if current > 1 else count

                search_results["current"] = new_idx
                search_count_label.set_text(f"{new_idx} of {count}")

                # Update highlighting in JavaScript
                await ui.run_javascript(f'''
                    const marks = document.querySelectorAll('.yaml-viewer-code mark');
                    marks.forEach((m, i) => {{
                        m.classList.remove('ring-2', 'ring-orange-500');
                        if (i === {new_idx - 1}) {{
                            m.classList.add('ring-2', 'ring-orange-500');
                            m.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    }});
                ''')

            prev_btn.on("click", lambda: go_to_match("prev"))
            next_btn.on("click", lambda: go_to_match("next"))
            search_input.on("update:model-value", on_search)

            # Actions
            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button(
                    "Copy to Clipboard",
                    icon="content_copy",
                    on_click=lambda: _copy_to_clipboard(content),
                ).props("outline")
                ui.button("Close", on_click=dialog.close)

    return dialog


def _copy_to_clipboard(content: str) -> None:
    """Copy content to clipboard."""
    ui.run_javascript(f'navigator.clipboard.writeText({repr(content)})')
    ui.notify("Copied to clipboard", type="positive")


def parse_plan_stats(plan_output: str) -> Dict[str, int]:
    """Extract resource counts from terraform plan output.

    Args:
        plan_output: Raw terraform plan output text

    Returns:
        Dictionary with add/change/destroy counts
    """
    import re
    
    stats = {"add": 0, "change": 0, "destroy": 0}
    
    # Count from action comments like "# ... will be created"
    stats["add"] = len(re.findall(r"# .+ will be created", plan_output))
    stats["change"] = len(re.findall(r"# .+ will be updated", plan_output))
    stats["destroy"] = len(re.findall(r"# .+ will be destroyed", plan_output))
    
    # Also try the summary line: "Plan: X to add, Y to change, Z to destroy"
    summary_match = re.search(
        r"Plan:\s*(\d+)\s+to add,\s*(\d+)\s+to change,\s*(\d+)\s+to destroy",
        plan_output
    )
    if summary_match:
        stats["add"] = int(summary_match.group(1))
        stats["change"] = int(summary_match.group(2))
        stats["destroy"] = int(summary_match.group(3))
    
    return stats


def create_plan_viewer_dialog(
    plan_output: str,
    title: str = "Terraform Plan",
) -> ui.dialog:
    """Create a dialog for viewing terraform plan output with search functionality.

    Args:
        plan_output: The terraform plan output text
        title: Dialog title

    Returns:
        The dialog element (call .open() to show it)
    """
    stats = parse_plan_stats(plan_output)

    # Search state
    search_results = {"count": 0, "current": 0}

    with ui.dialog() as dialog:
        dialog.props("maximized")

        with ui.card().classes("w-full h-full").style("display: flex; flex-direction: column;"):
            # Header
            with ui.row().classes("w-full items-center justify-between mb-2"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("assignment", size="lg").classes("text-orange-500")
                    ui.label(title).classes("text-xl font-bold")

                ui.button(icon="close", on_click=dialog.close).props("flat round")

            # Plan stats bar
            with ui.row().classes("w-full gap-4 mb-2 p-3 bg-slate-100 dark:bg-slate-800 rounded items-center"):
                ui.label("Plan Summary:").classes("font-semibold")
                
                # Add count (green)
                with ui.row().classes("items-center gap-1"):
                    ui.icon("add_circle", size="sm").classes("text-green-600")
                    ui.label(f"{stats['add']} to add").classes(
                        "text-green-600 font-medium"
                    )
                
                # Change count (yellow)
                with ui.row().classes("items-center gap-1"):
                    ui.icon("change_circle", size="sm").classes("text-amber-600")
                    ui.label(f"{stats['change']} to change").classes(
                        "text-amber-600 font-medium"
                    )
                
                # Destroy count (red)
                with ui.row().classes("items-center gap-1"):
                    ui.icon("remove_circle", size="sm").classes("text-red-600")
                    ui.label(f"{stats['destroy']} to destroy").classes(
                        "text-red-600 font-medium"
                    )
                
                # Spacer and line count
                ui.element("div").classes("flex-1")
                ui.label(f"{len(plan_output.splitlines()):,} lines").classes(
                    "text-xs text-slate-400"
                )

            # Search input with result count and navigation
            with ui.row().classes("w-full mb-2 items-center gap-2"):
                search_input = ui.input(
                    placeholder="Search in plan...",
                ).props("outlined dense clearable").classes("flex-1")

                # Navigation buttons (hidden initially)
                with ui.row().classes("items-center gap-1"):
                    prev_btn = ui.button(
                        icon="keyboard_arrow_up",
                        on_click=lambda: None,
                    ).props("flat dense round size=sm").classes("hidden")
                    next_btn = ui.button(
                        icon="keyboard_arrow_down",
                        on_click=lambda: None,
                    ).props("flat dense round size=sm").classes("hidden")

                search_count_label = ui.label("").classes("text-xs text-slate-400 min-w-[80px]")

            # Plan content with syntax coloring
            # Apply color coding to plan output for better readability
            def colorize_plan_line(line: str) -> str:
                """Apply HTML color spans to terraform plan lines."""
                import html
                escaped = html.escape(line)
                
                # Resource creation lines (green)
                if line.strip().startswith("+") or "will be created" in line:
                    return f'<span class="text-green-600 dark:text-green-400">{escaped}</span>'
                # Resource destruction lines (red)
                elif line.strip().startswith("-") or "will be destroyed" in line:
                    return f'<span class="text-red-600 dark:text-red-400">{escaped}</span>'
                # Resource change lines (yellow/amber)
                elif line.strip().startswith("~") or "will be updated" in line:
                    return f'<span class="text-amber-600 dark:text-amber-400">{escaped}</span>'
                # Resource replacement (red + green)
                elif "-/+" in line or "+/-" in line:
                    return f'<span class="text-purple-600 dark:text-purple-400">{escaped}</span>'
                # Comments and headers
                elif line.strip().startswith("#"):
                    return f'<span class="text-slate-500 dark:text-slate-400 font-semibold">{escaped}</span>'
                else:
                    return escaped

            colorized_lines = [colorize_plan_line(line) for line in plan_output.splitlines()]
            colorized_content = "\n".join(colorized_lines)

            with ui.scroll_area().classes("w-full").style("flex: 1; min-height: 0;"):
                # Use html element with pre/code for monospace display
                ui.html(
                    f'<pre class="plan-viewer-code text-sm font-mono whitespace-pre-wrap p-4 bg-slate-50 dark:bg-slate-900 rounded overflow-x-auto"><code>{colorized_content}</code></pre>',
                    sanitize=False,  # Safe - we control the content and escape user input
                ).classes("w-full")

            # JavaScript for search highlighting
            async def on_search(e):
                search_term = e.args if e.args else ""
                if not search_term:
                    search_count_label.set_text("")
                    search_results["count"] = 0
                    search_results["current"] = 0
                    prev_btn.classes("hidden", remove=False)
                    next_btn.classes("hidden", remove=False)
                    # Restore colorized content
                    return

                # Count matches
                count = plan_output.lower().count(search_term.lower())
                search_results["count"] = count
                search_results["current"] = 1 if count > 0 else 0

                if count > 1:
                    search_count_label.set_text(f"1 of {count}")
                    prev_btn.classes(remove="hidden")
                    next_btn.classes(remove="hidden")
                elif count == 1:
                    search_count_label.set_text("1 of 1")
                    prev_btn.classes("hidden", remove=False)
                    next_btn.classes("hidden", remove=False)
                else:
                    search_count_label.set_text("No matches")
                    prev_btn.classes("hidden", remove=False)
                    next_btn.classes("hidden", remove=False)

                # Highlight matches using JavaScript
                escaped_term = search_term.replace("'", "\\'").replace('"', '\\"')
                await ui.run_javascript(f'''
                    const codeEl = document.querySelector('.plan-viewer-code code');
                    if (codeEl) {{
                        // Get text content but preserve structure
                        const walker = document.createTreeWalker(codeEl, NodeFilter.SHOW_TEXT);
                        const textNodes = [];
                        while (walker.nextNode()) textNodes.push(walker.currentNode);
                        
                        const regex = new RegExp('({escaped_term})', 'gi');
                        textNodes.forEach(node => {{
                            if (regex.test(node.textContent)) {{
                                const span = document.createElement('span');
                                span.innerHTML = node.textContent.replace(regex, '<mark class="bg-yellow-300 dark:bg-yellow-600 px-0.5 rounded">$1</mark>');
                                node.parentNode.replaceChild(span, node);
                            }}
                        }});
                        
                        // Scroll to first match
                        const firstMark = document.querySelector('.plan-viewer-code mark');
                        if (firstMark) {{
                            firstMark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                            firstMark.classList.add('ring-2', 'ring-orange-500');
                        }}
                    }}
                ''')

            async def go_to_match(direction):
                count = search_results["count"]
                if count <= 1:
                    return

                current = search_results["current"]
                if direction == "next":
                    new_idx = current + 1 if current < count else 1
                else:
                    new_idx = current - 1 if current > 1 else count

                search_results["current"] = new_idx
                search_count_label.set_text(f"{new_idx} of {count}")

                # Update highlighting in JavaScript
                await ui.run_javascript(f'''
                    const marks = document.querySelectorAll('.plan-viewer-code mark');
                    marks.forEach((m, i) => {{
                        m.classList.remove('ring-2', 'ring-orange-500');
                        if (i === {new_idx - 1}) {{
                            m.classList.add('ring-2', 'ring-orange-500');
                            m.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    }});
                ''')

            prev_btn.on("click", lambda: go_to_match("prev"))
            next_btn.on("click", lambda: go_to_match("next"))
            search_input.on("update:model-value", on_search)

            # Actions
            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button(
                    "Copy to Clipboard",
                    icon="content_copy",
                    on_click=lambda: _copy_to_clipboard(plan_output),
                ).props("outline")
                ui.button("Close", on_click=dialog.close)

    return dialog


def create_migration_summary_card(
    yaml_path: Optional[str],
    on_view_yaml: Optional[Callable[[], None]] = None,
    show_yaml_button: bool = True,
) -> None:
    """Create a migration summary card showing YAML resource counts.

    Args:
        yaml_path: Path to the YAML file
        on_view_yaml: Callback when View YAML is clicked
        show_yaml_button: Whether to show the View YAML button
    """
    stats = get_yaml_stats(yaml_path) if yaml_path else {}

    with ui.card().classes("w-full"):
        with ui.row().classes("items-center justify-between mb-4"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("inventory", size="md").classes("text-orange-500")
                ui.label("Migration Summary").classes("text-lg font-semibold")

            if show_yaml_button and yaml_path:
                ui.button(
                    "View YAML",
                    icon="visibility",
                    on_click=on_view_yaml,
                ).props("outline size=sm")

        if stats:
            # Group resources by category
            global_resources = {
                k: v for k, v in stats.items()
                if k in ["connections", "repositories", "privatelink_endpoints", 
                        "service_tokens", "groups", "notifications"]
                and v > 0
            }

            project_resources = {
                k: v for k, v in stats.items()
                if k in ["projects", "environments", "jobs", "environment_variables"]
                and v > 0
            }

            # Projects section
            if project_resources:
                ui.label("Project Resources").classes(
                    "text-xs text-slate-500 uppercase tracking-wide"
                )
                with ui.row().classes("w-full gap-3 mb-4 flex-wrap"):
                    for resource, count in project_resources.items():
                        with ui.column().classes(
                            "items-center p-3 bg-slate-50 dark:bg-slate-800 rounded min-w-[70px]"
                        ):
                            ui.label(str(count)).classes("text-xl font-bold")
                            ui.label(resource.replace("_", " ").title()).classes(
                                "text-xs text-slate-500 text-center"
                            )

            # Globals section
            if global_resources:
                ui.label("Global Resources").classes(
                    "text-xs text-slate-500 uppercase tracking-wide mt-2"
                )
                with ui.row().classes("w-full gap-3 flex-wrap"):
                    for resource, count in global_resources.items():
                        with ui.column().classes(
                            "items-center p-3 bg-slate-50 dark:bg-slate-800 rounded min-w-[70px]"
                        ):
                            ui.label(str(count)).classes("text-xl font-bold")
                            ui.label(resource.replace("_", " ").title()).classes(
                                "text-xs text-slate-500 text-center"
                            )

            # Total count
            total = sum(stats.values())
            ui.label(f"Total: {total} resources").classes(
                "text-sm text-slate-500 mt-4"
            )
        else:
            ui.label("No YAML configuration available").classes(
                "text-slate-500 dark:text-slate-400"
            )

        # YAML file reference
        if yaml_path:
            with ui.row().classes("mt-4 items-center gap-2"):
                ui.icon("description", size="sm").classes("text-slate-400")
                ui.label(yaml_path).classes(
                    "text-xs text-slate-500 font-mono truncate"
                )
