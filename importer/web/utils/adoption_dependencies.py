"""Adoption dependency resolution for grid rows.

Provides functions to:
- Resolve the full parent chain for a given resource type
- Find unadopted parents in grid row data
- Build project-scoped child lists for "Select Whole Project"
"""

import json
import time
from typing import Dict, List, Optional, Set, Tuple

from importer.web.components.hierarchy_index import ENTITY_PARENT_TYPES, TYPE_DEPTH


# Parent types that are adoptable (not account-level, since we don't adopt accounts)
ADOPTABLE_PARENT_TYPES = {"PRJ", "ENV"}


def _dbg_db419a(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": "db419a",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(
            "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-db419a.log",
            "a",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        return


def get_parent_chain(resource_type: str) -> List[str]:
    """Return the ordered parent chain for a resource type (excluding ACC).

    The chain is ordered from immediate parent to root, excluding
    account-level entries since accounts are not individually adopted.

    Args:
        resource_type: Entity type code (e.g., "JOB", "ENV", "PRJ")

    Returns:
        List of parent type codes, immediate parent first.
        E.g., get_parent_chain("JOB") → ["ENV", "PRJ"]
              get_parent_chain("ENV") → ["PRJ"]
              get_parent_chain("PRJ") → []
    """
    chain: List[str] = []
    visited: Set[str] = set()
    current = resource_type

    while current in ENTITY_PARENT_TYPES:
        parents = ENTITY_PARENT_TYPES[current]
        # region agent log
        if resource_type == "CON":
            _dbg_db419a(
                "H45",
                "adoption_dependencies.py:get_parent_chain",
                "evaluating parent candidates for connection",
                {
                    "resource_type": resource_type,
                    "current_type": current,
                    "raw_parent_candidates": list(parents),
                    "visited": sorted(list(visited)),
                },
            )
        # endregion
        # Find the first non-ACC adoptable parent
        next_parent = None
        for p in parents:
            if p == "ACC":
                continue
            if p in visited:
                continue
            next_parent = p
            break

        if not next_parent:
            break

        chain.append(next_parent)
        visited.add(next_parent)
        current = next_parent

    return chain


def find_unadopted_parents(
    child_row: Dict,
    all_rows: List[Dict],
) -> List[Dict]:
    """Find grid rows for parent resources that are not yet marked for adoption.

    Given a child row being adopted, this checks whether its required
    parents (based on the type hierarchy) are also marked for adoption.
    Returns the list of parent rows that need adoption.

    Args:
        child_row: The grid row being adopted.
        all_rows: All grid rows to search for parent matches.

    Returns:
        List of parent row dicts that are NOT yet adopted, ordered
        from immediate parent to root (e.g., [ENV row, PRJ row]).
    """
    child_type = child_row.get("source_type", "")
    child_project = child_row.get("project_name", "")

    parent_chain = get_parent_chain(child_type)
    # region agent log
    if child_type == "CON":
        _dbg_db419a(
            "H46",
            "adoption_dependencies.py:find_unadopted_parents",
            "computed parent chain for connection adoption check",
            {
                "child_type": child_type,
                "child_source_key": child_row.get("source_key", ""),
                "child_project": child_project,
                "parent_chain": parent_chain,
            },
        )
    # endregion
    if not parent_chain:
        return []

    # Build lookup: (type, project_name) → row for quick parent matching
    # Also handle target-only rows which use source_type for the element_type
    type_project_lookup: Dict[Tuple[str, str], List[Dict]] = {}
    for row in all_rows:
        rtype = row.get("source_type", "")
        rproject = row.get("project_name", "")
        key = (rtype, rproject)
        if key not in type_project_lookup:
            type_project_lookup[key] = []
        type_project_lookup[key].append(row)

    unadopted: List[Dict] = []
    for parent_type in parent_chain:
        if parent_type == "PRJ":
            # For project parents, match by project_name
            candidates = type_project_lookup.get(("PRJ", child_project), [])
            # Also try matching by source_name == project_name
            if not candidates:
                for row in all_rows:
                    if row.get("source_type") == "PRJ" and (
                        row.get("source_name") == child_project
                        or row.get("target_name") == child_project
                    ):
                        candidates = [row]
                        break
        elif parent_type == "ENV":
            # For environment parents, match by project_name
            # (there may be multiple envs in the project; we need the specific one)
            candidates = type_project_lookup.get(("ENV", child_project), [])
            # If the child has environment info, try to narrow down
            # For now, take all ENV rows in the same project
        else:
            candidates = type_project_lookup.get((parent_type, child_project), [])

        for candidate in candidates:
            action = candidate.get("action", "")
            if action not in ("adopt", "match"):
                # Parent is not adopted and not already matched → needs adoption
                unadopted.append(candidate)
        # region agent log
        if child_type == "CON":
            _dbg_db419a(
                "H46",
                "adoption_dependencies.py:find_unadopted_parents",
                "evaluated candidates for computed parent type",
                {
                    "child_source_key": child_row.get("source_key", ""),
                    "parent_type": parent_type,
                    "candidate_count": len(candidates),
                    "candidate_keys": [str(c.get("source_key", "")) for c in candidates[:20]],
                    "candidate_actions": [str(c.get("action", "")) for c in candidates[:20]],
                    "unadopted_keys_so_far": [str(u.get("source_key", "")) for u in unadopted[:20]],
                },
            )
        # endregion

    return unadopted


def get_project_children(
    project_row: Dict,
    all_rows: List[Dict],
) -> Dict[str, List[Dict]]:
    """Get all child rows for a project, grouped by resource type.

    Used for the "Select Whole Project" dialog that shows child
    counts and allows checkbox customization.

    Args:
        project_row: The project grid row.
        all_rows: All grid rows.

    Returns:
        Dict mapping type code → list of child rows.
        E.g., {"ENV": [row1, row2], "JOB": [row3], "VAR": [row4]}
    """
    project_name = project_row.get("project_name", "") or project_row.get("source_name", "")
    if not project_name:
        return {}

    children_by_type: Dict[str, List[Dict]] = {}

    for row in all_rows:
        if row is project_row:
            continue
        row_type = row.get("source_type", "")
        row_project = row.get("project_name", "")

        # Check if this row belongs to the project
        if row_project != project_name:
            continue

        # Check if this type is a descendant of PRJ
        if row_type in ("PRJ", "ACC"):
            continue

        depth = TYPE_DEPTH.get(row_type, 0)
        if depth < TYPE_DEPTH.get("PRJ", 1):
            continue  # Skip account-level types

        if row_type not in children_by_type:
            children_by_type[row_type] = []
        children_by_type[row_type].append(row)

    return children_by_type
