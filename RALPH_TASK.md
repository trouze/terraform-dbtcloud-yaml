---
task: Persistent Target Intent File
test_command: "cd importer && python -m pytest web/tests/test_target_intent.py -v"
browser_validation: true
base_url: "http://127.0.0.1:8080"
---

# Task: Persistent Target Intent File

Promote target-intent.json from a deploy-time artifact to a persistent project-level file (following the protection-intent.json pattern), extend it to track match mappings, rename 'Match Existing' to 'Set Target Intent'.

**Plan Reference:** `.cursor/plans/persistent_target_intent_40fb41b2.plan.md`

## Success Criteria

### 0. Rename "Match Existing" to "Set Target Intent"

1. [x] Rename step label in state.py STEP_NAMES: "Match Existing" → "Set Target Intent"
2. [x] Change step icon in state.py STEP_ICONS: "link" → "assignment"
3. [x] Rename match.py page header: "Match Source to Target Resources" → "Set Target Intent"
4. [x] Rename match.py subtitle to "Define what Terraform should manage: match, adopt, protect, and remove resources"
5. [x] Rename mapping.py expansion labels: "Match Existing Target Resources" → "Set Target Intent" (already clean)
6. [x] Rename deploy.py comments and user messages: "Match Existing tab" → "Set Target Intent tab"
7. [x] Rename match.py "Save Mapping File" section to "Save Target Intent"
8. [x] Rename match.py dialog title "Target Resource Mapping" → "Target Intent"
9. [x] Rename match.py "View Mapping" button → "View Target Intent"

### 1. Extend TargetIntentResult data model

10. [x] Add SourceToTargetMapping dataclass with from_confirmed_mapping/to_confirmed_mapping interop
11. [x] Add StateToTargetMapping dataclass with state_to_target fields
12. [x] Add MatchMappings container with source_to_target and state_to_target lists
13. [x] Bump version to 2
14. [x] Backward compat: from_dict handles version 1 (no match_mappings)
15. [x] save() includes match_mappings; compute_target_intent preserves from previous

### 2. Promote TargetIntentManager to AppState

16. [x] _target_intent_manager field on AppState (like _protection_intent_manager)
17. [x] get_target_intent_manager() method with lazy init
18. [x] save_target_intent() method
19. [x] Not serialized in to_dict() (Tier 3 SKIP)

### 3. Match page reads/writes target intent

20. [x] Match page loads intent file via state.get_target_intent_manager() on render
21. [x] Populate confirmed_mappings from intent.match_mappings.source_to_target on load
22. [x] Write confirmed_mappings back to intent file on all confirm/reject actions
23. [x] Compute state_to_target when TF state is loaded

### 4. TF state-to-target visibility on Match page

24. [x] State Resources stat card alongside existing cards
25. [x] Collapsible TF State Alignment section with matched/unmatched table

### 5. Target Intent tab in resource detail dialog

26. [x] "Target Intent" tab between TF State and JSON tabs
27. [x] Shows disposition with color badge, source, confirmed status, state-to-target match, protection summary

### 6. Deploy reads persistent intent

28. [x] Deploy generate loads persistent intent via TargetIntentManager
29. [x] compute_target_intent preserves match_mappings from previous_intent

### 7. Tests

30. [x] Test SourceToTargetMapping/StateToTargetMapping/MatchMappings round-trip
31. [x] Test backward compat with version 1 files (no match_mappings)
32. [x] Test sync between confirmed_mappings and intent file (to/from round-trip)

## Notes

- All 31 tests passing
- Many features were partially implemented from prior sessions; this task completed and connected them
