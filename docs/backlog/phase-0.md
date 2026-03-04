# Phase 0: Foundation

> **Goal**: Establish a clean, secure, fully-equipped development environment before writing any application code.

**Status**: Complete
**Progress**: 4/4 tasks complete

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P0-T01 | Verify and Install Pre-commit Hooks | Complete | None |
| P0-T02 | Create Secrets Baseline | Complete | P0-T01 |
| P0-T03 | Setup Project & Test Directory Structure | Complete | P0-T01 |
| P0-T04 | Verify CI Pipeline | Complete | P0-T01 through P0-T03 |

---

## P0-T01: Verify and Install Pre-commit Hooks

**Description**: Ensure pre-commit hooks are properly installed and all hooks pass on the existing codebase. This establishes the security and quality foundation for all future work.

**Status**: Complete

### User Story

As a developer, I need pre-commit hooks installed and working so that every commit is automatically checked for code quality, security issues, and secrets before it enters the repository.

### Acceptance Criteria

- [ ] `pre-commit --version` returns a valid version
- [ ] `pre-commit install` completes without error
- [ ] `pre-commit install --hook-type commit-msg` installs the commitizen hook
- [ ] `pre-commit run --all-files` passes (or only fails on expected empty stubs)
- [ ] Running `git commit` triggers hooks automatically
- [ ] All security hooks are active: `gitleaks`, `detect-secrets`, `bandit`

### Implementation Steps

1. Ensure Poetry virtual environment is active: `poetry shell`
2. Install hooks: `poetry run pre-commit install && poetry run pre-commit install --hook-type commit-msg`
3. Run all hooks: `poetry run pre-commit run --all-files`
4. Fix any formatting or linting failures
5. Verify hooks trigger on a test commit attempt

### Test Expectations

This is a tooling task — no pytest tests required. Verification is via exit code:
- `pre-commit run --all-files` exits with code 0

### Files to Create/Modify

- None (hooks already configured in `.pre-commit-config.yaml`)
- May need minor fixes to `src/argent/__init__.py` to pass mypy/ruff

### Commit Message

```
chore: verify and install pre-commit hooks

- Install pre-commit and commit-msg hook types
- Fix any stub files that fail hooks
- Confirm security scanning (gitleaks, bandit, detect-secrets) is active
```

### Notes

- If `gitleaks` binary is missing: `brew install gitleaks`
- `detect-secrets` will fail until baseline exists — do P0-T02 immediately after
- mypy may complain about empty `__init__.py` stubs — that is expected at this phase

---

## P0-T02: Create Secrets Baseline

**Description**: Initialize the detect-secrets baseline file (`.secrets.baseline`) so the secret detection hook can distinguish known safe patterns from actual leaked secrets.

**Status**: Complete

### User Story

As a developer, I need a secrets baseline so that detect-secrets can track known false positives and alert me only to genuinely new secrets in the codebase.

### Acceptance Criteria

- [ ] `.secrets.baseline` file exists in the repository root
- [ ] Baseline is generated from the current codebase
- [ ] `detect-secrets scan` runs without errors
- [ ] Pre-commit `detect-secrets` hook passes
- [ ] `.secrets.baseline` is committed to the repository

### Implementation Steps

1. Generate baseline: `detect-secrets scan > .secrets.baseline`
2. Audit: `detect-secrets audit .secrets.baseline`
3. Mark any known false positives as safe
4. Run hook to verify: `pre-commit run detect-secrets --all-files`

### Test Expectations

No pytest tests. Verification:
- `pre-commit run detect-secrets --all-files` exits with code 0

### Files to Create/Modify

- Create: `.secrets.baseline`

### Commit Message

```
chore: create detect-secrets baseline

- Generate initial secrets baseline from clean codebase
- Audit and mark false positives
- Enable secret detection in pre-commit pipeline
```

### Notes

- `.secrets.baseline` IS committed (it is not PII, it is a hash manifest)
- Audit carefully — do not mark real secrets as false positives

---

## P0-T03: Setup Project & Test Directory Structure

**Description**: Create the complete `src/argent/` source package layout and the `tests/` directory structure with `unit/`, `integration/`, and `fixtures/` subdirectories.

**Status**: Complete

### User Story

As a developer, I need a well-organized project layout so that code has predictable locations, tests are easy to find and run selectively, and the package installs cleanly.

### Acceptance Criteria

- [ ] `src/argent/__init__.py` exists with version string
- [ ] `src/argent/pipeline/` directory exists (for Epic 1)
- [ ] `src/argent/ingress/` directory exists (for Epic 2)
- [ ] `src/argent/budget/` directory exists (for Epic 3)
- [ ] `src/argent/trimmer/` directory exists (for Epic 4)
- [ ] `src/argent/security/` directory exists (for Epic 5)
- [ ] `tests/unit/` directory exists with `__init__.py`
- [ ] `tests/integration/` directory exists with `__init__.py`
- [ ] `tests/fixtures/` directory exists with sample payloads
- [ ] `pytest tests/ --collect-only` runs without import errors
- [ ] `poetry run mypy src/` passes (stubs are acceptable)

### Implementation Steps

1. Create source package skeleton:
   ```
   src/argent/
   ├── __init__.py
   ├── pipeline/
   │   └── __init__.py
   ├── ingress/
   │   └── __init__.py
   ├── budget/
   │   └── __init__.py
   ├── trimmer/
   │   └── __init__.py
   └── security/
       └── __init__.py
   ```
2. Create test directory structure:
   ```
   tests/
   ├── __init__.py
   ├── conftest.py
   ├── unit/
   │   └── __init__.py
   ├── integration/
   │   └── __init__.py
   └── fixtures/
       ├── payloads/       (JSON, YAML, XML, plaintext samples)
       └── responses/      (Mocked tool output samples)
   ```
3. Add minimal fixture files (valid JSON, oversized JSON, malformed JSON, valid YAML, plaintext)
4. Verify with `pytest tests/ --collect-only` and `poetry run mypy src/`

### Test Expectations

Run: `pytest tests/ --collect-only`
- No import errors
- Collection succeeds (even if 0 tests found at this stage)

### Files to Create/Modify

- Create: All `__init__.py` stubs listed above
- Create: `tests/conftest.py`
- Create: `tests/fixtures/payloads/valid.json`, `oversized.json`, `malformed.json`, `valid.yaml`, `plain.txt`

### Commit Message

```
chore: setup project and test directory structure

- Create src/argent package skeleton with subpackage stubs
- Create tests/unit, tests/integration, tests/fixtures directories
- Add sample payload fixtures (valid, oversized, malformed)
- Verify pytest collection and mypy pass
```

---

## P0-T04: Verify CI Pipeline

**Description**: Run the full CI quality gate suite locally and ensure all checks exit clean. Fix any issues introduced during project scaffolding.

**Status**: Complete

### User Story

As a developer, I need the entire CI pipeline to pass on the scaffolded project so that the quality gate truly gates — and future feature work begins from a provably clean baseline.

### Acceptance Criteria

- [ ] `poetry run ruff check src/ tests/` passes
- [ ] `poetry run ruff format --check src/ tests/` passes
- [ ] `poetry run mypy src/` passes (stubs acceptable)
- [ ] `poetry run pytest tests/ -v` exits 0 (0 failures; 0 tests collected is acceptable here)
- [ ] `poetry run bandit -c pyproject.toml -r src/` passes
- [ ] `poetry run vulture src/` passes (or reports 0 items)
- [ ] `poetry run pre-commit run --all-files` passes

### Implementation Steps

1. Run the full quality gate suite:
   ```bash
   poetry run ruff check src/ tests/
   poetry run ruff format --check src/ tests/
   poetry run mypy src/
   poetry run pytest tests/ -v
   poetry run bandit -c pyproject.toml -r src/
   poetry run vulture src/
   poetry run pre-commit run --all-files
   ```
2. Fix any reported issues
3. Commit a clean baseline

### Test Expectations

All commands exit with code 0. The `pytest` command should exit 0 even with no tests collected (adjust `addopts` if needed).

### Files to Create/Modify

- Fix whatever source or config files produce tool failures

### Commit Message

```
chore: verify CI pipeline passes all quality gates

- Fix any linting or type errors in scaffolding
- Confirm all pre-commit hooks pass
- Establish a provably clean baseline before feature work begins
```

---

## Phase 0 Completion Checklist

Before moving to Phase 1, verify:

```bash
# Pre-commit hooks pass
poetry run pre-commit run --all-files

# Linting
poetry run ruff check src/ tests/
poetry run ruff format --check src/ tests/

# Type checking
poetry run mypy src/

# Tests (zero failures expected)
poetry run pytest tests/ -v

# Security
poetry run bandit -c pyproject.toml -r src/

# Secrets
gitleaks detect --verbose
```
