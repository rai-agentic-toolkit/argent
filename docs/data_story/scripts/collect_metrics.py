"""collect_metrics.py — Data story analysis script for the argent repository.

Reads git history, filesystem structure, running pytest-cov, and RETRO_LOG.md
to produce a JSON metrics snapshot. Output is written to metrics.json in the
same directory as this script.

Usage::

    poetry run python docs/data_story/scripts/collect_metrics.py

No network access. No dependencies beyond the project's existing [dev] extras.
All functions are pure with respect to their arguments so they can be unit-tested
against synthetic data without touching the real repository.
"""

from __future__ import annotations

import json
import re
import subprocess  # nosec B404 — analysis script; subprocess used only for git and python -m pytest
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RETRO_LOG = _REPO_ROOT / "docs" / "RETRO_LOG.md"
_METRICS_OUT = Path(__file__).resolve().parent / "metrics.json"


#: Pattern to match a conventional commit subject line (with hash prefix from git log).
_COMMIT_RE = re.compile(
    r"^[0-9a-f]+ (?P<type>feat|fix|test|refactor|docs|chore|build|ci|style|perf|revert|bump|review)"
    r"(?:\([^)]+\))?[!:]?"
)

#: Pattern to match a review commit and extract persona and verdict.
_REVIEW_RE = re.compile(
    r"^[0-9a-f]+ review\((?P<persona>[^)]+)\):\s+.+?—\s+(?P<verdict>PASS|FINDING|SKIP)"
)

#: Pattern to match advisory rows in the Open Advisory Items table.
_ADV_OPEN_RE = re.compile(r"^\|\s*(ADV-\d+)\s*\|")


# ---------------------------------------------------------------------------
# Public API — tested in test_collect_metrics.py
# ---------------------------------------------------------------------------


def commit_type_counts(log: str) -> dict[str, int]:
    """Count commits by conventional commit type from a git log string.

    Parses lines of the form ``<hash> <type>[(<scope>)]: <description>`` and
    tallies each type.  ``review(qa|ui-ux|devops|arch)`` commits are all counted
    under the single ``"review"`` bucket.

    Args:
        log: Output of ``git log --format="%H %s"`` (one line per commit).

    Returns:
        Dict mapping type name to count.  Empty if *log* is blank.
    """
    counts: dict[str, int] = defaultdict(int)
    for raw_line in log.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _COMMIT_RE.match(line)
        if m:
            counts[m.group("type")] += 1
    return dict(counts)


def review_verdicts(log: str) -> dict[str, dict[str, int]]:
    """Extract review verdicts per reviewer persona from a git log string.

    Parses ``review(<persona>): <task> — <verdict>`` commit subjects and returns
    nested counts.  ``"FINDING (fixed)"`` is normalised to ``"FINDING"``.

    Args:
        log: Output of ``git log --format="%H %s"`` (one line per commit).

    Returns:
        Nested dict ``{persona: {verdict: count}}``.  Empty if no review commits.
    """
    by_persona: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for raw_line in log.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _REVIEW_RE.match(line)
        if m:
            persona = m.group("persona")
            verdict = m.group("verdict")  # already PASS | FINDING | SKIP
            by_persona[persona][verdict] += 1
    # Convert defaultdicts to plain dicts for JSON serialisability.
    return {p: dict(v) for p, v in by_persona.items()}


def loc_by_epic(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Count non-blank lines of code per Epic subpackage.

    Scans ``<repo_root>/src/argent/<epic>/`` for production code and
    ``<repo_root>/tests/unit/test_<epic>*.py`` for test code.  Blank lines are
    excluded.  Returns a ``test_to_src_ratio`` field as a float.

    Args:
        repo_root: Absolute path to the root of the repository.

    Returns:
        Dict keyed by epic name; each value has ``src``, ``test``, and
        ``test_to_src_ratio`` keys.
    """

    def _count_lines(paths: list[Path]) -> int:
        total = 0
        for p in paths:
            if not p.exists():
                continue
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        total += 1
            except OSError:
                pass
        return total

    result: dict[str, dict[str, Any]] = {}
    src_base = repo_root / "src" / "argent"
    test_base = repo_root / "tests" / "unit"

    # Discover epics from directories present under src/argent/
    epic_dirs: list[Path] = []
    if src_base.exists():
        epic_dirs = [d for d in src_base.iterdir() if d.is_dir() and not d.name.startswith("_")]

    for epic_dir in epic_dirs:
        epic = epic_dir.name
        src_files = list(epic_dir.rglob("*.py"))
        test_files = list(test_base.glob(f"test_{epic}*.py")) if test_base.exists() else []

        src_loc = _count_lines(src_files)
        test_loc = _count_lines(test_files)
        ratio = round(test_loc / src_loc, 2) if src_loc else 0.0

        result[epic] = {"src": src_loc, "test": test_loc, "test_to_src_ratio": ratio}

    return result


def advisory_lifecycle(retro_log: str) -> list[dict[str, str]]:
    """Extract advisory item lifecycle from a RETRO_LOG.md string.

    Scans the ``## Open Advisory Items`` table for ADV-NNN rows.  Each
    advisory found in the table is reported with ``status: "open"``.
    The placeholder row ``*(no open items)*`` is excluded.

    Args:
        retro_log: Full text content of docs/RETRO_LOG.md.

    Returns:
        List of dicts with ``"id"`` and ``"status"`` keys.
    """
    advisories: list[dict[str, str]] = []
    in_table = False
    for line in retro_log.splitlines():
        if "## Open Advisory Items" in line:
            in_table = True
            continue
        if in_table:
            # Stop at the next section header or horizontal rule.
            if line.startswith("##") or line.startswith("---"):
                break
            m = _ADV_OPEN_RE.match(line)
            if m:
                advisories.append({"id": m.group(1), "status": "open"})
    return advisories


# ---------------------------------------------------------------------------
# Coverage runner — calls pytest-cov as a subprocess
# ---------------------------------------------------------------------------


def _run_coverage(repo_root: Path) -> dict[str, Any]:
    """Run pytest-cov and return a dict with total line and branch coverage.

    Args:
        repo_root: Root of the repository (cwd for the subprocess).

    Returns:
        Dict with ``"line_pct"`` and ``"test_count"`` keys, or error info.
    """
    result = subprocess.run(  # nosec B603 — input is sys.executable + hardcoded pytest args, not user input
        [
            sys.executable,
            "-m",
            "pytest",
            f"--cov={repo_root / 'src' / 'argent'}",
            "--cov-report=json",
            "-q",
            "--tb=no",
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )
    cov_json_path = repo_root / "coverage.json"
    line_pct: float = 0.0
    test_count = 0
    if cov_json_path.exists():
        data = json.loads(cov_json_path.read_text())
        line_pct = data.get("totals", {}).get("percent_covered", 0.0)

    # Parse test count from pytest output line like "283 passed in 4.20s"
    for line in result.stdout.splitlines():
        m = re.search(r"(\d+) passed", line)
        if m:
            test_count = int(m.group(1))
            break

    return {"line_pct": round(line_pct, 2), "test_count": test_count}


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git_log(repo_root: Path) -> str:
    """Return ``git log --format="%H %s"`` output for main branch."""
    result = subprocess.run(  # nosec B603 B607 — git binary resolved by OS PATH; args are hardcoded constants
        ["git", "log", "main", "--format=%H %s"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )
    return result.stdout


def _git_commit_count(repo_root: Path) -> int:
    """Return the total number of commits on main."""
    result = subprocess.run(  # nosec B603 B607 — git binary resolved by OS PATH; args are hardcoded constants
        ["git", "rev-list", "--count", "main"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )
    return int(result.stdout.strip())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Collect all repository metrics and write metrics.json."""
    print(f"Collecting metrics for repository at: {_REPO_ROOT}")

    log = _git_log(_REPO_ROOT)
    retro_text = _RETRO_LOG.read_text(encoding="utf-8") if _RETRO_LOG.exists() else ""

    commit_counts = commit_type_counts(log)
    verdicts = review_verdicts(log)
    loc = loc_by_epic(_REPO_ROOT)
    advisories = advisory_lifecycle(retro_text)
    total_commits = _git_commit_count(_REPO_ROOT)

    print("Running pytest-cov (this may take ~30s)…")
    coverage = _run_coverage(_REPO_ROOT)

    # Aggregate LOC totals
    total_src_loc = sum(v["src"] for v in loc.values())
    total_test_loc = sum(v["test"] for v in loc.values())
    overall_ratio = round(total_test_loc / total_src_loc, 2) if total_src_loc else 0.0

    metrics: dict[str, Any] = {
        "meta": {
            "generated_at": "2026-03-09",
            "repo_root": "(local — run collect_metrics.py to regenerate)",
            "branch": "main",
        },
        "commits": {
            "total": total_commits,
            "by_type": commit_counts,
        },
        "review": {
            "by_persona": verdicts,
        },
        "loc": {
            "by_epic": loc,
            "total_src": total_src_loc,
            "total_test": total_test_loc,
            "overall_ratio": overall_ratio,
        },
        "coverage": coverage,
        "advisories": advisories,
    }

    _METRICS_OUT.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Wrote metrics to: {_METRICS_OUT}")
    print(
        f"  {total_commits} commits · "
        f"{coverage['test_count']} tests · "
        f"{coverage['line_pct']:.1f}% coverage · "
        f"{total_src_loc} src LOC / {total_test_loc} test LOC"
    )


if __name__ == "__main__":
    main()
