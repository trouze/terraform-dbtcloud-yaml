# Versioning & Changelog Policy

This repo now tracks three distinct deliverables. Each has explicit versioning rules so we can release Terraform modules, evolve YAML schemas, and ship the importer CLI with build-level logging.

| Artifact | Purpose | Version Source | Release Tag |
|----------|---------|----------------|-------------|
| Terraform module bundle | Module published to the Terraform Registry | `terraform-registry-manifest.json:version` (Semantic Versioning) | Git tag `module/vX.Y.Z` |
| YAML schemas (`schemas/v*.json`) | IDE + Terraform validation contract | Schema file name (`v1`, `v2`, …) and in-file semantics (`version: 2`) | Git tag `schema/vX` when introducing a new file |
| Importer CLI / scripts | Extract→normalize→emit YAML toolchain | `importer/VERSION` (Semantic Versioning with optional build metadata) | Git tag `importer/vX.Y.Z` |

---

## Terraform Module Versioning

1. **Bump** the `version` field in `terraform-registry-manifest.json` when releasing new module functionality or fixes.
2. **Document** the changes under `CHANGELOG.md` → `## [Unreleased]` before cutting a tag. Use subsections (`### Added`, `### Changed`, etc.) and prefix entries with `Module:` when ambiguity exists.
3. **Tag** the commit `module/vX.Y.Z` after pushing the manifest + changelog updates. The tag drives Terraform Registry releases.
4. **Backport** critical fixes by branching from the relevant tag, updating the manifest + changelog, and tagging again.

> The manifest is **only** for the Terraform module. It should not be reused for schema or importer versioning.

---

## YAML Schema Versioning

- Each incompatible schema change requires a new file under `schemas/` (`v3.json`, etc.) and a matching `version: 3` root field.
- Backwards-compatible additions (e.g., optional fields) can land in the existing schema file but must be noted in `CHANGELOG.md` under `Schema:`.
- IDE references (`# yaml-language-server: $schema=…/schemas/v2.json`) and docs are the canonical source for which schema to use.
- Tag schema releases with `schema/vN` so tooling can pin to a known contract even before a Terraform module release.

---

## Importer CLI Versioning & Logging

### Version Source
- `importer/VERSION` stores the semantic version string (e.g., `0.1.0-dev`).
- Build pipelines may append metadata (timestamp, git SHA) via the `IMPORTER_BUILD_META` environment variable without touching the file. Example build info string:
  ```
  0.1.0-dev+20241119.abc1234
  ```

### Logging Rule
Every CLI invocation must log the build string at startup:
```
[info] dbtcloud-importer version=0.1.0-dev build=20241119.abc1234
```
- Load `importer/VERSION` at runtime.
- Append `IMPORTER_BUILD_META` if set; otherwise append the current git short SHA when available.
- Include the same version in error telemetry or structured logs for traceability.

### Bumping Importer Versions
1. Update `importer/VERSION`.
2. Add an entry under `CHANGELOG.md` (prefix `Importer:`).
3. Tag the commit `importer/vX.Y.Z`.

---

## Changelog Workflow

`CHANGELOG.md` (Keep a Changelog format) covers **all** artifacts:

```
## [Unreleased]
### Added
- Module: …
- Importer: …
### Changed
- Schema: …
```

Guidelines:
- Always mention the artifact prefix (`Module`, `Schema`, `Importer`) when the entry isn’t obvious.
- After releasing, copy the `Unreleased` section into a dated section (e.g., `## [Importer 0.2.0] - 2024-11-19`) and reset `Unreleased`.
- Reference tags at the bottom of the file using multiple compare links if needed (module/importer/schema).

--- 

## Release Checklist (Condensed)

1. Implement changes.
2. Update `CHANGELOG.md` with artifact-prefixed entries.
3. Bump the relevant version source(s):
   - Module → `terraform-registry-manifest.json`
   - Schema → new `schemas/vX.json`
   - Importer → `importer/VERSION`
4. Run tests (`go test ./test`, `python -m unittest test/schema_validation_test.py`, importer unit tests once available).
5. Tag and push using the artifact-specific tag convention.

