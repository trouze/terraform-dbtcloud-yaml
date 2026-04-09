# Release Preparation

Prepare a new release of terraform-dbtcloud-as-yaml. This skill handles two workflows:

1. **Terraform provider upgrade** — bump the dbt Cloud provider version across all lock files and docs
2. **Version release** — update all version references to cut a new `vX.Y.Z` release

## Arguments

`$ARGUMENTS` — one of:
- `provider <new_version>` — e.g. `provider 1.10` — upgrades provider constraint and lock files
- `release <new_version>` — e.g. `release 0.3.0` — bumps module version references and CHANGELOG

---

## Workflow: `provider <new_version>`

When the user passes `provider <new_version>` (e.g. `provider 1.10`):

1. **Update provider constraint** in `versions.tf` (root) and all `modules/*/versions.tf` from the old `~> X.Y` to the new version.

2. **Regenerate lock files** by running:
   ```bash
   terraform init -upgrade -backend=false
   for dir in modules/*/; do
     terraform -chdir="$dir" init -upgrade -backend=false
   done
   ```

3. **Update docs badge** in `docs/index.md`:
   - Shield badge: `dbt--cloud--provider-vX.Y-blue`
   - Quick Start code block: `version = "~> X.Y"`

4. **Summarize** all changed files and remind the user to commit.

---

## Workflow: `release <new_version>`

When the user passes `release <new_version>` (e.g. `release 0.3.0`), use today's date for the CHANGELOG entry:

1. **Update topology source ref** in `topologies/basic/main.tf`:
   ```
   source = "github.com/dbt-labs/terraform-dbtcloud-as-yaml?ref=v<new_version>"
   ```

2. **Update CHANGELOG.md**:
   - Rename `## [Unreleased]` section to `## [<new_version>] - <YYYY-MM-DD>` (today's date)
   - Add a fresh empty `## [Unreleased]` section above it (with empty Added/Changed/Fixed/Removed subsections)
   - Update the diff links at the bottom:
     - `[Unreleased]: .../compare/v<new_version>...HEAD`
     - `[<new_version>]: .../compare/v<prev_version>...v<new_version>`
   - To find `<prev_version>`, look at the existing diff links or the most recent versioned `## [X.Y.Z]` heading.

3. **Verify no other stale version references** by grepping for the old version string across `**/*.tf`, `**/*.md`.

4. **Summarize** all changed files and remind the user to:
   - Commit the changes
   - Push and open a PR
   - After merge, create and push the git tag: `git tag v<new_version> && git push origin v<new_version>`
   - Create a GitHub release from the tag

---

## Notes

- Lock files live at: root `.terraform.lock.hcl` and `modules/*/.terraform.lock.hcl`
- The 5 modules tested in CI that **require** lock files: `project`, `environments`, `jobs`, `credentials`, `repository`
- Other modules (`environment_variables`, `environment_variable_job_overrides`, `lineage_integrations`, `project_artefacts`, `semantic_layer`) have lock files but are not in the CI test matrix
- Never commit `.terraform/` directories (provider cache), only `.terraform.lock.hcl` files
