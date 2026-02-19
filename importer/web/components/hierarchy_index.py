"""Hierarchy index for parent-child relationship lookups on entity data."""

from typing import Dict, List, Optional, Set, Tuple


# Entity type hierarchy - defines parent-child relationships
# Format: child_type -> parent_type(s)
ENTITY_PARENT_TYPES = {
    "JOB": ["ENV", "PRJ"],  # Job belongs to Environment and Project
    "CRD": ["ENV"],         # Credential belongs to Environment
    "ENV": ["PRJ"],         # Environment belongs to Project
    "VAR": ["PRJ"],         # Environment Variable belongs to Project
    "EXTATTR": ["PRJ"],     # Extended Attributes belong to Project
    "PRJ": ["ACC"],         # Project belongs to Account
    # Connections are account-level resources. Environments may reference a
    # connection, but that reference does not make CON a child of ENV.
    "CON": ["ACC"],
    # Other globals belong to Account
    "REP": ["ACC"],
    "TOK": ["ACC"],
    "GRP": ["ACC"],
    "NOT": ["ACC"],
    "WEB": ["ACC"],
    "PLE": ["ACC"],
    "ACC": [],              # Account is root
}

# Entity types that can have children
PARENT_TYPES = {"ACC", "PRJ", "ENV"}  # ENV can have credentials and jobs as children

# Depth levels for each type (used for indentation)
TYPE_DEPTH = {
    "ACC": 0,  # Account at root
    "CON": 1,  # Globals at depth 1
    "REP": 1,
    "TOK": 1,
    "GRP": 1,
    "NOT": 1,
    "WEB": 1,
    "PLE": 1,
    "PRJ": 1,  # Projects at depth 1
    "ENV": 2,  # Environments at depth 2
    "VAR": 2,  # Env Variables at depth 2
    "EXTATTR": 2,  # Extended Attributes at depth 2 (project-scoped)
    "CRD": 3,  # Credentials at depth 3 (under environments)
    "JOB": 3,  # Jobs at depth 3
}

# Sort order for entity types (for hierarchical display)
TYPE_SORT_ORDER = {
    "ACC": 0,
    "CON": 10,
    "REP": 11,
    "TOK": 12,
    "GRP": 13,
    "NOT": 14,
    "WEB": 15,
    "PLE": 16,
    "PRJ": 20,
    "ENV": 30,
    "VAR": 31,
    "EXTATTR": 25,  # Extended Attributes sort between project and environment
    "CRD": 35,  # Credentials sort after environments but before jobs
    "JOB": 40,
}


class HierarchyIndex:
    """Index for fast parent-child relationship lookups on entity data.
    
    Builds indexes from entity report items that contain parent references
    (parent_project_id, environment_mapping_id, etc.).
    """
    
    def __init__(self, entities: Optional[List[Dict]] = None):
        """Initialize the hierarchy index.
        
        Args:
            entities: Optional list of entity dicts to index immediately
        """
        # Mapping ID -> Entity data
        self._entities: Dict[str, Dict] = {}
        
        # Parent -> Children mappings
        self._children: Dict[str, Set[str]] = {}
        
        # Child -> Parent mappings
        self._parents: Dict[str, Set[str]] = {}
        
        # Type -> Mapping IDs
        self._by_type: Dict[str, Set[str]] = {}
        
        # Project key -> Mapping ID (for project lookups)
        self._project_by_key: Dict[str, str] = {}
        
        # Repository key -> Mapping ID (for repository lookups)
        self._repo_by_key: Dict[str, str] = {}
        
        # Connection key -> Mapping ID (for connection lookups by key)
        self._connection_by_key: Dict[str, str] = {}
        
        # Connection dbt_id -> Mapping ID (for ID-based connection lookups)
        self._connection_by_id: Dict[int, str] = {}
        
        if entities:
            self.build_index(entities)
    
    def build_index(self, entities: List[Dict]) -> None:
        """Build the hierarchy index from entity data.
        
        Args:
            entities: List of entity dicts with element_mapping_id and parent references
        """
        # Clear existing data
        self._entities.clear()
        self._children.clear()
        self._parents.clear()
        self._by_type.clear()
        self._project_by_key.clear()
        self._repo_by_key.clear()
        self._connection_by_key.clear()
        self._connection_by_id.clear()
        
        # First pass: index all entities by mapping_id and type
        for entity in entities:
            mapping_id = entity.get("element_mapping_id")
            if not mapping_id:
                continue
            
            self._entities[mapping_id] = entity
            
            # Index by type
            entity_type = entity.get("element_type_code", "")
            if entity_type not in self._by_type:
                self._by_type[entity_type] = set()
            self._by_type[entity_type].add(mapping_id)
            
            # Index projects by key
            if entity_type == "PRJ":
                project_key = entity.get("project_key") or entity.get("key")
                if project_key:
                    self._project_by_key[project_key] = mapping_id
            
            # Index repositories by key
            if entity_type == "REP":
                repo_key = entity.get("key")
                if repo_key:
                    self._repo_by_key[repo_key] = mapping_id
            
            # Index connections by key and ID
            if entity_type == "CON":
                conn_key = entity.get("key")
                conn_dbt_id = entity.get("dbt_id")
                if conn_key:
                    self._connection_by_key[conn_key] = mapping_id
                if conn_dbt_id:
                    self._connection_by_id[conn_dbt_id] = mapping_id
            
            # Initialize parent/child sets
            if mapping_id not in self._children:
                self._children[mapping_id] = set()
            if mapping_id not in self._parents:
                self._parents[mapping_id] = set()
        
        # Second pass: build parent-child relationships
        for entity in entities:
            mapping_id = entity.get("element_mapping_id")
            if not mapping_id:
                continue
            
            entity_type = entity.get("element_type_code", "")
            
            # Check for parent_project_id (ENV, VAR, JOB, REP all have this)
            parent_project_id = entity.get("parent_project_id")
            if parent_project_id:
                self._link_parent_child(parent_project_id, mapping_id)
            
            # Check for environment_mapping_id (JOB has this)
            env_mapping_id = entity.get("environment_mapping_id")
            if env_mapping_id:
                self._link_parent_child(env_mapping_id, mapping_id)
            
            # Check for parent_environment_id (CRD has this)
            parent_env_id = entity.get("parent_environment_id")
            if parent_env_id:
                self._link_parent_child(parent_env_id, mapping_id)
            
            # Note: We intentionally do NOT link connections as children of environments.
            # Environments REFERENCE connections, but connections aren't CONTAINED by environments.
            # Connections are global resources owned by the Account, not by environments.
            # The connection_key on ENV is tracked in _connection_by_key for lookup purposes only.
            
            # Link globals (without parent_project_id) to account
            if entity_type in {"CON", "TOK", "GRP", "NOT", "WEB", "PLE"}:
                account_ids = self._by_type.get("ACC", set())
                if account_ids:
                    account_id = next(iter(account_ids))
                    self._link_parent_child(account_id, mapping_id)
            
            # Link repositories without parent_project_id to account (orphan repos)
            if entity_type == "REP" and not entity.get("parent_project_id"):
                account_ids = self._by_type.get("ACC", set())
                if account_ids:
                    account_id = next(iter(account_ids))
                    self._link_parent_child(account_id, mapping_id)
            
            # Link projects to account
            if entity_type == "PRJ":
                account_ids = self._by_type.get("ACC", set())
                if account_ids:
                    account_id = next(iter(account_ids))
                    self._link_parent_child(account_id, mapping_id)
    
    def _link_parent_child(self, parent_id: str, child_id: str) -> None:
        """Create a parent-child link.
        
        Args:
            parent_id: Parent entity mapping ID
            child_id: Child entity mapping ID
        """
        if parent_id not in self._children:
            self._children[parent_id] = set()
        if child_id not in self._parents:
            self._parents[child_id] = set()
        
        self._children[parent_id].add(child_id)
        self._parents[child_id].add(parent_id)
    
    def get_entity(self, mapping_id: str) -> Optional[Dict]:
        """Get entity data by mapping ID.
        
        Args:
            mapping_id: Entity mapping ID
            
        Returns:
            Entity dict or None if not found
        """
        return self._entities.get(mapping_id)
    
    def get_children(self, mapping_id: str) -> Set[str]:
        """Get direct children of an entity.
        
        Args:
            mapping_id: Parent entity mapping ID
            
        Returns:
            Set of child mapping IDs
        """
        return self._children.get(mapping_id, set()).copy()
    
    def get_parents(self, mapping_id: str) -> Set[str]:
        """Get direct parents of an entity.
        
        Args:
            mapping_id: Child entity mapping ID
            
        Returns:
            Set of parent mapping IDs
        """
        return self._parents.get(mapping_id, set()).copy()
    
    def get_all_descendants(self, mapping_id: str) -> Set[str]:
        """Get all descendants (children, grandchildren, etc.) of an entity.
        
        Args:
            mapping_id: Parent entity mapping ID
            
        Returns:
            Set of all descendant mapping IDs (not including self)
        """
        result = set()
        to_visit = list(self._children.get(mapping_id, set()))
        
        while to_visit:
            child_id = to_visit.pop()
            if child_id not in result:
                result.add(child_id)
                to_visit.extend(self._children.get(child_id, set()))
        
        return result
    
    def get_required_ancestors(self, mapping_id: str) -> Set[str]:
        """Get all required ancestors (parents, grandparents, etc.) of an entity.
        
        Args:
            mapping_id: Child entity mapping ID
            
        Returns:
            Set of all ancestor mapping IDs (not including self)
        """
        result = set()
        to_visit = list(self._parents.get(mapping_id, set()))
        
        while to_visit:
            parent_id = to_visit.pop()
            if parent_id not in result:
                result.add(parent_id)
                to_visit.extend(self._parents.get(parent_id, set()))
        
        return result
    
    def get_linked_entities(self, mapping_id: str) -> Set[str]:
        """Get linked entity mapping IDs for ENV↔EXTATTR (same project).
        
        When an ENV references extended attributes via extended_attributes_key,
        protecting/selecting one should include the other.
        
        Args:
            mapping_id: Entity mapping ID (ENV or EXTATTR)
            
        Returns:
            Set of linked mapping IDs (EXTATTR for ENV; ENVs that reference this EXTATTR for EXTATTR)
        """
        result: Set[str] = set()
        entity = self._entities.get(mapping_id)
        if not entity:
            return result
        entity_type = entity.get("element_type_code", "")
        entity_key = entity.get("key") or mapping_id

        if entity_type == "ENV":
            ext_key = entity.get("extended_attributes_key") or ""
            project_key = entity.get("project_key") or (entity_key.rsplit("_", 1)[0] if "_" in entity_key else "")
            if not ext_key or not project_key:
                return result
            eat_composite = f"{project_key}_{ext_key}"
            for eid, e in self._entities.items():
                if e.get("element_type_code") != "EXTATTR":
                    continue
                if (e.get("key") or eid) == eat_composite:
                    result.add(eid)
                    break
        elif entity_type == "EXTATTR":
            project_key = entity.get("project_key") or (entity_key.rsplit("_", 1)[0] if "_" in entity_key else "")
            ext_key = entity.get("name") or (entity_key.rsplit("_", 1)[1] if "_" in entity_key else "")
            if not project_key or not ext_key:
                return result
            for eid, e in self._entities.items():
                if e.get("element_type_code") != "ENV":
                    continue
                e_project = e.get("project_key") or (e.get("key") or "").rsplit("_", 1)[0] if "_" in (e.get("key") or "") else ""
                if e_project != project_key or (e.get("extended_attributes_key") or "") != ext_key:
                    continue
                result.add(eid)
        return result
    
    def get_entities_by_type(self, entity_type: str) -> Set[str]:
        """Get all entity mapping IDs of a specific type.
        
        Args:
            entity_type: Entity type code (e.g., "PRJ", "ENV")
            
        Returns:
            Set of mapping IDs for that type
        """
        return self._by_type.get(entity_type, set()).copy()
    
    def get_connection_by_id(self, connection_id: int) -> Optional[str]:
        """Get connection mapping ID by dbt Cloud connection ID.
        
        Args:
            connection_id: The dbt Cloud connection ID (integer)
            
        Returns:
            The element_mapping_id for the connection, or None if not found
        """
        return self._connection_by_id.get(connection_id)
    
    def get_depth(self, mapping_id: str) -> int:
        """Get the depth level of an entity in the hierarchy.
        
        Args:
            mapping_id: Entity mapping ID
            
        Returns:
            Depth level (0 = root, higher = deeper)
        """
        entity = self._entities.get(mapping_id)
        if not entity:
            return 0
        
        entity_type = entity.get("element_type_code", "")
        return TYPE_DEPTH.get(entity_type, 0)
    
    def get_hierarchy_path(self, mapping_id: str) -> List[str]:
        """Get the full hierarchy path from root to entity.
        
        Args:
            mapping_id: Entity mapping ID
            
        Returns:
            List of mapping IDs from root to entity (inclusive)
        """
        path = [mapping_id]
        current = mapping_id
        
        # Walk up the tree
        while True:
            parents = self._parents.get(current, set())
            if not parents:
                break
            # Take the first parent (there should typically be one main parent)
            parent = next(iter(parents))
            path.insert(0, parent)
            current = parent
        
        return path
    
    def get_sort_key(self, mapping_id: str) -> Tuple:
        """Get a sort key for hierarchical ordering.
        
        Sort order:
        1. Account first
        2. Globals (by type order)
        3. Projects (alphabetical by name)
        4. Children nested under parents (by type, then name)
        
        Args:
            mapping_id: Entity mapping ID
            
        Returns:
            Tuple for sorting
        """
        entity = self._entities.get(mapping_id)
        if not entity:
            return (999, "", "", "")
        
        entity_type = entity.get("element_type_code", "")
        type_order = TYPE_SORT_ORDER.get(entity_type, 99)
        name = entity.get("name", "") or ""
        project_name = entity.get("project_name", "") or ""
        
        # For globals and account, sort by type then name
        if entity_type in {"ACC", "CON", "REP", "TOK", "GRP", "NOT", "WEB", "PLE"}:
            return (type_order, "", name.lower(), "")
        
        # For project-scoped items, sort by project, type, name
        return (type_order, project_name.lower(), name.lower(), mapping_id)
    
    def get_hierarchical_order(self) -> List[str]:
        """Get all entity mapping IDs in hierarchical display order.
        
        Returns entities ordered for tree-like display:
        - Account
        - Globals (grouped by type)
        - Projects
          - Environments (under parent project)
          - Environment Variables (under parent project)
            - Jobs (under parent environment)
        
        Returns:
            List of mapping IDs in display order
        """
        result = []
        visited = set()
        
        def visit(mapping_id: str, depth: int = 0):
            """Visit an entity and its children in order."""
            if mapping_id in visited:
                return
            visited.add(mapping_id)
            result.append(mapping_id)
            
            # Get and sort children
            children = self._children.get(mapping_id, set())
            if children:
                # Sort children by type order, then name
                sorted_children = sorted(
                    children,
                    key=lambda mid: self.get_sort_key(mid)
                )
                for child_id in sorted_children:
                    visit(child_id, depth + 1)
        
        # Start with account
        account_ids = self._by_type.get("ACC", set())
        if account_ids:
            account_id = next(iter(account_ids))
            visit(account_id)
        
        # Handle any orphaned entities (shouldn't happen normally)
        for mapping_id in self._entities:
            if mapping_id not in visited:
                visit(mapping_id)
        
        return result
    
    def check_missing_dependencies(
        self, 
        selected_ids: Set[str]
    ) -> List[Dict[str, str]]:
        """Check for missing dependencies in a selection.
        
        When a child is selected but its required parent is not,
        this returns a list of warnings.
        
        Args:
            selected_ids: Set of selected entity mapping IDs
            
        Returns:
            List of warning dicts with 'entity', 'entity_type', 'missing', 'missing_type'
        """
        warnings = []
        
        for mapping_id in selected_ids:
            entity = self._entities.get(mapping_id)
            if not entity:
                continue
            
            entity_type = entity.get("element_type_code", "")
            entity_name = entity.get("name", mapping_id)
            
            # Check required parents
            required_parents = self.get_required_ancestors(mapping_id)
            
            for parent_id in required_parents:
                if parent_id not in selected_ids:
                    parent = self._entities.get(parent_id)
                    if parent:
                        parent_type = parent.get("element_type_code", "")
                        parent_name = parent.get("name", parent_id)
                        
                        # Skip account-level warnings (account is typically always included)
                        if parent_type == "ACC":
                            continue
                        
                        warnings.append({
                            "entity": entity_name,
                            "entity_type": entity_type,
                            "entity_id": mapping_id,
                            "missing": parent_name,
                            "missing_type": parent_type,
                            "missing_id": parent_id,
                        })
        
        return warnings
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the indexed entities.
        
        Returns:
            Dict with counts by type and totals
        """
        stats = {
            "total": len(self._entities),
        }
        for entity_type, ids in self._by_type.items():
            stats[entity_type] = len(ids)
        return stats
