---
name: remediate-cves
description: Remediates CVEs from Sysdig scanner output by applying patch-only dependency bumps across Galileo repos. Accepts Sysdig CSV file paths and/or Coda table URLs. Handles Python, JavaScript, and Go packages. Skips OS packages, the Go runtime, and minor/major bumps. Creates one PR per affected repo. Reports transitive deps, skipped bumps, and out-of-scope CVEs separately.
disable-model-invocation: true
---

# CVE Remediation — Patch Bumps Only

Fix patch-level CVEs in Python, JavaScript, and Go dependencies across Galileo repos. One PR per affected repo.

**Input:** `$ARGUMENTS` — space-separated Sysdig CSV file paths and/or Coda table URLs.

---

## Phase 1: Parse Input

For each argument:

**CSV file path:** Use `Read` to load the file. Extract image name from filename pattern `*-prod-<image>-latest-*`. If it doesn't match, ask the user. Parse rows into records: `{ image, cve_id, severity, package_name, installed_version, package_type, fix_version }`.

Sysdig CSV columns: `CVE ID, CVE Severity, CVSS Score, CVSS Score Version, Package Name, Package Version, Package Path, Package Type, Fix Version, CVE URL, Vuln Disclosure Date, Vuln Fix Date, Risk Accepted, EPSS Score`

**Coda URL:** Call `coda_resolve_link`, then `coda_list_columns` to map columns to fields (image/service, CVE ID, severity, package name, installed version, package type, fix version). If no image column, ask the user. Call `coda_list_rows`, paginating via `pageToken`.

Combine all records. Print: `Loaded N CVE records: api (X), runners (Y), ...`

---

## Phase 2: Filter

1. **`package_type == os`** → `os_cves` (out of scope)
2. **`package_type == golang` and `package_name == Go`** → `runtime_cves` (Go runtime — out of scope)
3. **`fix_version` empty** → `no_fix_cves`
4. **Deduplicate** by `(image, cve_id, package_name, installed_version, fix_version)` — keep one record per unique combination
5. **Semver patch check** — strip leading `v`/`>=`/`~=`, parse as `MAJOR.MINOR.PATCH` (missing parts = 0):
   - Same MAJOR + same MINOR + higher PATCH → `patch_cves` ✓
   - Anything else → `skipped_cves` with reason (Major bump / Minor bump / Already fixed / Unparseable)

Print summary, then stop if `patch_cves` is empty.

---

## Phase 3: Map to Repos

Map `image` (case-insensitive) to sibling repo directories:

| Image | Repo |
|---|---|
| `api`, `galileo-api` | `../api` |
| `runners`, `galileo-runners` | `../runners` |
| `ui`, `galileo-ui` | `../ui` |
| `galileo-js` | `../galileo-js` |
| `orbit` | `../orbit` |
| `wizard`, `galileo-wizard` | `../wizard` |
| `authz` | `../authz` |
| `comet` | `../comet` |

Unmatched image → `skipped_cves` ("Unknown image"). Use `Bash` to verify each repo dir exists (`ls <path>`); missing → `skipped_cves` ("Repo not found"). Group `patch_cves` by repo.

---

## Phase 4: Find Packages in Manifests

Normalize Python package names: lowercase, `-` and `_` equivalent.

**Python** (`api`, `runners`, `wizard`, `comet`, `orbit`): Use `Glob` for `**/pyproject.toml` and `**/requirements*.txt`. Use `Read` to search `[tool.poetry.dependencies]` / `[project.dependencies]` and `package==version` lines. pyproject.toml takes precedence.

**JavaScript** (`ui`, `galileo-js`): Use `Glob` for `**/package.json` (exclude `**/node_modules/**`). Use `Read` to search `dependencies`, `devDependencies`, `peerDependencies`.

**Go** (`authz`, `orbit`): Use `Glob` for `**/go.mod`. Use `Read` to search `require` blocks for `<module> v<version>` lines.

Classify each package: **found** (record file + specifier), **not found** → `transitive_cves`, **already ≥ fix** → `skipped_cves`.

---

## Phase 5: Apply Updates

Use `Edit` to update version digits only. **Preserve constraint operators** (`^`, `~`, `>=`, `==`). For `go.mod`: replace `module v1.1.0` → `module v1.1.1`.

---

## Phase 6: Git + PR — One Per Repo

For each repo with ≥ 1 edit, use `Bash` for these commands only:

```bash
DEFAULT=$(git -C <repo> symbolic-ref refs/remotes/origin/HEAD | sed 's|refs/remotes/origin/||')
git -C <repo> checkout $DEFAULT && git -C <repo> pull
BRANCH="fix/cve-patch-bumps-$(date +%Y-%m-%d)"
# Append -2, -3 if branch already exists
git -C <repo> checkout -b $BRANCH
git -C <repo> add <list edited files explicitly by path>
git -C <repo> commit -m "fix: patch CVE dependency bumps"
git -C <repo> push -u origin $BRANCH
gh pr create --repo rungalileo/<repo-name> \
  --title "fix: patch CVE dependency bumps (N packages)" \
  --body "..."
```

PR body:
```markdown
## CVE Patch Dependency Bumps
Updates **N packages** to remediate patch-level CVEs identified by Sysdig.

> **Note:** Regenerate lock files after merging — Python: `poetry lock --no-update && poetry install` / Node: `pnpm install` / Go: `go mod tidy`

## Updated Dependencies
| CVE ID | Severity | Package | Old Version | New Version |
|--------|----------|---------|-------------|-------------|

## Transitive Dependencies (not in manifests — manual pinning required)
| CVE ID | Severity | Package | Installed | Fix |
|--------|----------|---------|-----------|-----|
```

---

## Phase 7: Summary

```
## CVE Remediation Complete

### PRs Created
- [authz] fix/cve-patch-bumps-2026-04-07 — 3 packages  <url>

### Transitive Dependencies (patch fix available — not in manifests)
| Image | CVE ID | Severity | Package | Installed | Fix |

### Skipped — Minor/Major Bump Required
| Image | CVE ID | Severity | Package | Installed | Fix | Reason |

### Skipped — No Fix Available
| Image | CVE ID | Severity | Package | Installed |

### Out of Scope
OS CVEs: api (N), runners (M), wizard (P)
Go runtime: authz (S)
```

---

## Important Notes

- **Patch-only is a hard rule** — if MAJOR or MINOR differs between installed and fix version, skip it. No exceptions.
- **Never run package managers** — no `pip`, `poetry`, `npm`, `pnpm`, `go mod tidy`, or similar.
- **Never stage with `git add -A` or `git add .`** — list edited files explicitly.
- **Never modify lock files** (`poetry.lock`, `go.sum`, `pnpm-lock.yaml`, `package-lock.json`).
