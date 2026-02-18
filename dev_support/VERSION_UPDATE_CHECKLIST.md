# Version Update Checklist

**Purpose:** This document lists all files and locations that must be updated when incrementing the importer version.

**Usage:** Reference this checklist when creating a new release to ensure all version references are updated consistently.

---

## Critical Files (Always Update)

### 1. `importer/VERSION`
**Location:** Root of file  
**Format:** `X.Y.Z` (single line)  
**Example:** `0.4.3`

### 2. `CHANGELOG.md`
**Location:** Top of file (after Unreleased section)  
**Format:**
```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Modified features

### Fixed
- Bug fixes
```

### 3. `dev_support/importer_implementation_status.md`
**Locations to update:**
- **Header metadata** (lines 3-6):
  - `Current Importer Version: X.Y.Z`
  - `Last Updated: YYYY-MM-DD`
- **Version Tracking section** (search for "Version Tracking"):
  - Current version reference
- **Change Log section** (bottom of file):
  - Add new entry with date, version, and summary of changes

### 4. `dev_support/phase5_e2e_testing_guide.md`
**Locations to update:**
- **Header metadata** (lines 3-5):
  - `Importer Version: X.Y.Z`
  - `Date: YYYY-MM-DD`

---

## Release-Specific Files (Create New)

### 5. `dev_support/RELEASE_NOTES_vX.Y.Z.md`
**Action:** Create new file for each release  
**Naming:** `RELEASE_NOTES_v0.4.3.md` (use dots in filename)  
**Template:** See existing release notes files

---

## Reference Documents (May Need Updates)

### 6. `README.md`
**Check if:**
- Installation instructions reference specific version
- Quick start examples reference version
- Compatibility matrix mentions version

### 7. `test/e2e_test/main.tf`
**Check if:**
- Provider version constraints need updating
- Comments reference specific versions

### 8. Runtime guardrails/docs for compatibility and performance
**Check if:**
- Any new compatibility fix (for framework/runtime API drift) was captured in:
  - `.ralph/guardrails.md`
  - `docs/guides/intent-workflow-guardrails.md`
- Release notes include a short "Verification" section with latency or behavior checks for affected UI paths

---

## Version Numbering Guidelines

Follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html):

- **MAJOR (X.0.0)**: Breaking changes, incompatible API changes
- **MINOR (0.X.0)**: New features, backwards-compatible functionality
- **PATCH (0.0.X)**: Bug fixes, backwards-compatible fixes

### Examples by Change Type

| Change Type | Version Increment | Example |
|------------|------------------|---------|
| Bug fix (type normalization) | PATCH | 0.4.2 → 0.4.3 |
| New resource support (environments) | MINOR | 0.4.3 → 0.5.0 |
| Schema v3 introduction | MAJOR | 0.5.0 → 1.0.0 |
| Performance improvement (gzip) | PATCH | 0.4.2 → 0.4.3 |
| New CLI command | MINOR | 0.4.3 → 0.5.0 |
| Timeout increase | PATCH | 0.4.2 → 0.4.3 |

---

## Version Update Workflow

### Step-by-Step Process

1. **Decide version increment** (MAJOR, MINOR, or PATCH)
2. **Update `importer/VERSION`** with new version
3. **Update `CHANGELOG.md`** with changes under new version heading
4. **Create `dev_support/RELEASE_NOTES_vX.Y.Z.md`** with detailed notes
5. **Update `dev_support/importer_implementation_status.md`**:
   - Header metadata
   - Version Tracking section
   - Change Log section
6. **Update `dev_support/phase5_e2e_testing_guide.md`** header
7. **Review reference documents** (README, test fixtures)
8. **Update guardrails/docs** if release includes compatibility or performance hardening
9. **Run tests** to verify version is correctly reported and key path behavior is stable
10. **Commit with message**: `chore: release vX.Y.Z`
11. **Tag release** (if applicable): `git tag vX.Y.Z`

---

## Automation Opportunities

### Future Improvements

Consider automating version updates with:
- **Python script**: `scripts/bump_version.py --patch|--minor|--major`
- **Pre-commit hook**: Validate all version references match
- **GitHub Actions**: Automated changelog generation from commit messages
- **Release workflow**: Tag creation triggers documentation updates

---

## Verification Commands

After updating version, verify consistency:

```bash
# Check version in VERSION file
cat importer/VERSION

# Check version is imported correctly
python3 -c "from importer import get_version; print(get_version())"

# Run version command
python3 -m importer --version

# Search for old version references (replace 0.4.2 with previous version)
rg "0\.4\.2" --type md dev_support/

# Check CHANGELOG structure
head -30 CHANGELOG.md
```

---

## Common Mistakes to Avoid

1. ❌ Updating VERSION file but forgetting CHANGELOG
2. ❌ Creating release notes but not updating implementation status
3. ❌ Using wrong date format (use ISO 8601: YYYY-MM-DD)
4. ❌ Inconsistent version format (use X.Y.Z, not vX.Y.Z in VERSION file)
5. ❌ Forgetting to update "Last Updated" dates in documentation
6. ❌ Not creating release notes file for significant changes
7. ❌ Skipping the Version Tracking section in implementation status
8. ❌ Shipping compatibility/performance fixes without updating guardrails/docs
9. ❌ Releasing UI performance fixes without recording verification metrics

---

**Last Updated:** 2026-02-17  
**Document Version:** 1.1


