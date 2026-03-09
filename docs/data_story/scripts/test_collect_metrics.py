"""Tests for collect_metrics.py — data story analysis script.

CONSTITUTION Priority 3: TDD RED Phase. All tests import symbols that do not
yet exist in collect_metrics.py; this file must fail on import until GREEN.

Tests are isolated from the real repo: they use synthetic git-log strings and
temporary directories so the suite passes regardless of local working-tree state.
"""

from __future__ import annotations

import textwrap
from pathlib import Path  # noqa: TC003 — runtime fixture type, not annotation-only

import pytest
from collect_metrics import (
    advisory_lifecycle,
    commit_type_counts,
    loc_by_epic,
    review_verdicts,
)

# ---------------------------------------------------------------------------
# Fixtures — synthetic data
# ---------------------------------------------------------------------------

SAMPLE_LOG = textwrap.dedent(
    """\
    abc1234 feat: implement pipeline core (P1-T01 GREEN)
    abc1235 test: add failing tests for pipeline (P1-T01 RED)
    abc1236 fix: narrow exception in parser
    abc1237 review(qa): P1-T01 — PASS
    abc1238 review(ui-ux): P1-T01 — SKIP
    abc1239 review(devops): P1-T01 — FINDING (fixed)
    abc1240 review(arch): P1-T01 — PASS
    abc1241 docs: update RETRO_LOG for P1-T01
    abc1242 chore: update pre-commit config
    abc1243 feat: implement ingress validators (P2-T01 GREEN)
    abc1244 test: add failing tests for ingress validators (P2-T01 RED)
    abc1245 review(qa): P2-T01 — FINDING (fixed)
    abc1246 review(ui-ux): P2-T01 — SKIP
    abc1247 review(devops): P2-T01 — PASS
    abc1248 review(arch): P2-T01 — FINDING (fixed)
    abc1249 docs: update RETRO_LOG for P2-T01
    """
)

SAMPLE_RETRO = textwrap.dedent(
    """\
    # Retrospective Log

    ## Open Advisory Items

    | ID | Advisory | Target Task | Source |
    |----|----------|-------------|--------|
    | ADV-001 | Some open advisory | P3-T01 | qa |
    | *(no open items)* | | | |

    ---

    ## [2026-03-08] P1-T01 — Core Pipeline

    ### QA
    PASS — 89 tests at 98.0% coverage.

    ### DevOps
    PASS — gitleaks clean.

    ---

    ## [2026-03-07] P2-T01 — Ingress Validators

    ### QA
    FINDING (fixed) — narrow except clause. 130 tests at 99.1% coverage.
    """
)


# ---------------------------------------------------------------------------
# commit_type_counts
# ---------------------------------------------------------------------------


class TestCommitTypeCounts:
    """Tests for commit_type_counts() — parses conventional commit types."""

    def test_counts_feat_commits(self) -> None:
        """feat: commits are counted under 'feat'."""
        counts = commit_type_counts(SAMPLE_LOG)
        assert counts["feat"] == 2

    def test_counts_test_commits(self) -> None:
        """test: commits are counted under 'test'."""
        counts = commit_type_counts(SAMPLE_LOG)
        assert counts["test"] == 2

    def test_counts_fix_commits(self) -> None:
        """fix: commits are counted under 'fix'."""
        counts = commit_type_counts(SAMPLE_LOG)
        assert counts["fix"] == 1

    def test_counts_review_commits(self) -> None:
        """review(qa/ui-ux/devops/arch) commits are counted under 'review'."""
        counts = commit_type_counts(SAMPLE_LOG)
        assert counts["review"] == 8

    def test_counts_docs_commits(self) -> None:
        """docs: commits are counted under 'docs'."""
        counts = commit_type_counts(SAMPLE_LOG)
        assert counts["docs"] == 2

    def test_counts_chore_commits(self) -> None:
        """chore: commits are counted under 'chore'."""
        counts = commit_type_counts(SAMPLE_LOG)
        assert counts["chore"] == 1

    def test_total_sums_to_log_length(self) -> None:
        """Total commit count equals the number of log lines."""
        counts = commit_type_counts(SAMPLE_LOG)
        line_count = len([ln for ln in SAMPLE_LOG.strip().splitlines() if ln])
        assert sum(counts.values()) == line_count

    def test_empty_log_returns_empty_counts(self) -> None:
        """Empty log string returns empty dict."""
        counts = commit_type_counts("")
        assert counts == {}


# ---------------------------------------------------------------------------
# review_verdicts
# ---------------------------------------------------------------------------


class TestReviewVerdicts:
    """Tests for review_verdicts() — categorises review commits by persona and verdict."""

    def test_qa_verdicts(self) -> None:
        """QA review verdicts are categorised correctly."""
        by_persona = review_verdicts(SAMPLE_LOG)
        assert by_persona["qa"]["PASS"] == 1
        assert by_persona["qa"]["FINDING"] == 1

    def test_ui_ux_verdicts(self) -> None:
        """ui-ux review verdicts are categorised correctly."""
        by_persona = review_verdicts(SAMPLE_LOG)
        assert by_persona["ui-ux"]["SKIP"] == 2

    def test_devops_verdicts(self) -> None:
        """devops review verdicts are categorised correctly."""
        by_persona = review_verdicts(SAMPLE_LOG)
        assert by_persona["devops"]["FINDING"] == 1
        assert by_persona["devops"]["PASS"] == 1

    def test_arch_verdicts(self) -> None:
        """arch review verdicts are categorised correctly (FINDING fixed counted as FINDING)."""
        by_persona = review_verdicts(SAMPLE_LOG)
        assert by_persona["arch"]["PASS"] == 1
        assert by_persona["arch"]["FINDING"] == 1

    def test_finding_fixed_normalised_to_finding(self) -> None:
        """'FINDING (fixed)' is normalised to 'FINDING' in the verdict counts."""
        log = "abc1 review(qa): P1-T01 — FINDING (fixed)\n"
        verdicts = review_verdicts(log)
        assert verdicts["qa"]["FINDING"] == 1
        assert "FINDING (fixed)" not in verdicts["qa"]

    def test_no_review_commits_returns_empty(self) -> None:
        """Log with no review: commits returns empty verdict dict."""
        log = "abc1 feat: implement something\n"
        assert review_verdicts(log) == {}


# ---------------------------------------------------------------------------
# loc_by_epic
# ---------------------------------------------------------------------------


class TestLocByEpic:
    """Tests for loc_by_epic() — counts lines of code per Epic subpackage."""

    def test_counts_src_loc(self, tmp_path: Path) -> None:
        """Counts non-blank, non-comment source lines in src/argent/<epic>/."""
        epic_dir = tmp_path / "src" / "argent" / "pipeline"
        epic_dir.mkdir(parents=True)
        (epic_dir / "context.py").write_text("class Foo:\n    pass\n\n")
        result = loc_by_epic(tmp_path)
        assert result["pipeline"]["src"] == 2

    def test_counts_test_loc(self, tmp_path: Path) -> None:
        """Counts test lines in tests/unit/test_<epic>*.py."""
        test_dir = tmp_path / "tests" / "unit"
        test_dir.mkdir(parents=True)
        (test_dir / "test_pipeline.py").write_text("def test_foo():\n    pass\n")
        # Need src too or function may error; create stub
        (tmp_path / "src" / "argent" / "pipeline").mkdir(parents=True)
        result = loc_by_epic(tmp_path)
        assert result["pipeline"]["test"] == 2

    def test_blank_lines_excluded(self, tmp_path: Path) -> None:
        """Blank lines are not counted as LOC."""
        epic_dir = tmp_path / "src" / "argent" / "pipeline"
        epic_dir.mkdir(parents=True)
        (epic_dir / "context.py").write_text("class Foo:\n\n    pass\n\n")
        result = loc_by_epic(tmp_path)
        assert result["pipeline"]["src"] == 2

    def test_multiple_epics_counted_independently(self, tmp_path: Path) -> None:
        """Each Epic subdirectory is reported separately."""
        for epic in ("pipeline", "ingress"):
            d = tmp_path / "src" / "argent" / epic
            d.mkdir(parents=True)
            (d / "mod.py").write_text("x = 1\n")
        result = loc_by_epic(tmp_path)
        assert "pipeline" in result
        assert "ingress" in result

    def test_ratio_computed(self, tmp_path: Path) -> None:
        """test_to_src_ratio is present in each Epic's metrics."""
        epic_dir = tmp_path / "src" / "argent" / "pipeline"
        epic_dir.mkdir(parents=True)
        (epic_dir / "mod.py").write_text("x = 1\ny = 2\n")
        test_dir = tmp_path / "tests" / "unit"
        test_dir.mkdir(parents=True)
        (test_dir / "test_pipeline.py").write_text("a = 1\nb = 2\nc = 3\nd = 4\n")
        result = loc_by_epic(tmp_path)
        assert result["pipeline"]["test_to_src_ratio"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# advisory_lifecycle
# ---------------------------------------------------------------------------


class TestAdvisoryLifecycle:
    """Tests for advisory_lifecycle() — extracts ADV-NNN open/close events from RETRO_LOG."""

    def test_detects_open_advisories(self) -> None:
        """Advisories present in the Open Advisory Items table are reported as open."""
        lifecycle = advisory_lifecycle(SAMPLE_RETRO)
        open_ids = [a["id"] for a in lifecycle if a["status"] == "open"]
        assert "ADV-001" in open_ids

    def test_placeholder_row_ignored(self) -> None:
        """The '*(no open items)*' placeholder row is not parsed as an advisory."""
        lifecycle = advisory_lifecycle(SAMPLE_RETRO)
        ids = [a["id"] for a in lifecycle]
        assert "*(no open items)*" not in ids
        assert None not in ids

    def test_returns_list_of_dicts(self) -> None:
        """Return type is a list of dicts with 'id' and 'status' keys."""
        lifecycle = advisory_lifecycle(SAMPLE_RETRO)
        for item in lifecycle:
            assert "id" in item
            assert "status" in item

    def test_empty_retro_returns_empty_list(self) -> None:
        """Empty RETRO_LOG string returns empty list."""
        assert advisory_lifecycle("") == []
