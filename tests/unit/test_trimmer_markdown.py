"""Tests for MarkdownTableTrimmer.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/trimmer/markdown.py exists.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from argent.trimmer.markdown import MarkdownTableTrimmer

SAMPLE_TABLE = """\
| Name   | Score | Grade |
|--------|-------|-------|
| Alice  | 95    | A     |
| Bob    | 82    | B     |
| Carol  | 71    | C     |
| Dave   | 60    | D     |"""


class TestMarkdownTableTrimmerIdempotence:
    """Content within max_chars is returned unchanged."""

    def test_short_table_returned_unchanged(self) -> None:
        """A table within max_chars is returned as-is."""
        trimmer = MarkdownTableTrimmer(max_chars=10_000)
        assert trimmer.trim(SAMPLE_TABLE) == SAMPLE_TABLE

    def test_empty_string_returned_unchanged(self) -> None:
        """Empty string is returned unchanged."""
        assert MarkdownTableTrimmer(max_chars=100).trim("") == ""

    def test_non_table_content_returned_unchanged(self) -> None:
        """Plain text without table structure is returned unchanged."""
        content = "just some text with no pipes"
        assert MarkdownTableTrimmer(max_chars=10).trim(content) == content

    def test_multiline_non_table_returned_unchanged(self) -> None:
        """Multi-line content without a separator row is returned unchanged."""
        content = "line one\nline two without separator\nline three"
        assert MarkdownTableTrimmer(max_chars=10).trim(content) == content


class TestMarkdownTableTrimmerTruncation:
    """Header row is always preserved; body rows are dropped from the bottom."""

    def test_header_row_always_present(self) -> None:
        """The first (header) row is always preserved."""
        trimmer = MarkdownTableTrimmer(max_chars=50)
        result = trimmer.trim(SAMPLE_TABLE)
        assert "| Name" in result

    def test_separator_row_always_present(self) -> None:
        """The separator row (|----|) is always preserved."""
        trimmer = MarkdownTableTrimmer(max_chars=50)
        result = trimmer.trim(SAMPLE_TABLE)
        assert "|--------|" in result

    def test_bottom_rows_dropped_first(self) -> None:
        """Body rows are dropped from the bottom when the table must be trimmed."""
        # max_chars small enough to force dropping Dave and Carol
        trimmer = MarkdownTableTrimmer(max_chars=100)
        result = trimmer.trim(SAMPLE_TABLE)
        assert "Dave" not in result

    def test_top_body_rows_retained_before_bottom(self) -> None:
        """Earlier body rows survive longer than later rows under tight budgets."""
        trimmer = MarkdownTableTrimmer(max_chars=120)
        result = trimmer.trim(SAMPLE_TABLE)
        assert "Alice" in result

    def test_result_within_max_chars(self) -> None:
        """Trimmed result is within max_chars."""
        trimmer = MarkdownTableTrimmer(max_chars=80)
        result = trimmer.trim(SAMPLE_TABLE)
        assert len(result) <= 80

    def test_header_only_if_no_rows_fit(self) -> None:
        """If no body rows fit, only the header and separator are returned."""
        trimmer = MarkdownTableTrimmer(max_chars=60)
        result = trimmer.trim(SAMPLE_TABLE)
        lines = [ln for ln in result.splitlines() if ln.strip()]
        # header + separator at minimum
        assert len(lines) >= 2
        assert "Name" in lines[0]


# ---------------------------------------------------------------------------
# P7-T01 RED: Trimmer structured logging
# ---------------------------------------------------------------------------


class TestMarkdownTableTrimmerLogging:
    """P7-T01: MarkdownTableTrimmer emits INFO log to argent.trimmer on truncation.

    CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL until
    markdown.py emits logging.getLogger("argent.trimmer").info(...) on the
    truncation path.
    """

    def test_emits_info_log_when_rows_dropped(self, caplog: pytest.LogCaptureFixture) -> None:
        """An INFO record is emitted to argent.trimmer when body rows are dropped."""
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            MarkdownTableTrimmer(max_chars=80).trim(SAMPLE_TABLE)
        assert any(r.levelno == logging.INFO for r in caplog.records)

    def test_log_record_includes_chars_dropped(self, caplog: pytest.LogCaptureFixture) -> None:
        """The INFO log message includes chars_dropped."""
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            MarkdownTableTrimmer(max_chars=80).trim(SAMPLE_TABLE)
        assert any("chars_dropped" in r.message for r in caplog.records)

    def test_no_log_when_content_fits(self, caplog: pytest.LogCaptureFixture) -> None:
        """No log is emitted when the table fits within the budget."""
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            MarkdownTableTrimmer(max_chars=10_000).trim(SAMPLE_TABLE)
        assert not caplog.records

    def test_no_log_for_non_table_content(self, caplog: pytest.LogCaptureFixture) -> None:
        """No log is emitted for non-table content that cannot be trimmed."""
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            MarkdownTableTrimmer(max_chars=5).trim("plain text no table structure here")
        assert not caplog.records
