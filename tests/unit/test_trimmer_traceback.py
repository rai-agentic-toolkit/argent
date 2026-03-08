"""Tests for PythonTracebackTrimmer.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/trimmer/traceback.py exists.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from argent.trimmer.base import Trimmer
from argent.trimmer.traceback import PythonTracebackTrimmer

SAMPLE_TRACEBACK = """\
Traceback (most recent call last):
  File "agent.py", line 10, in run
    result = tool()
  File "tool.py", line 5, in tool
    raise ValueError("bad input")
ValueError: bad input"""


class TestTrimmerProtocol:
    """Trimmer is a runtime-checkable Protocol satisfied by all concrete classes."""

    def test_traceback_trimmer_satisfies_protocol(self) -> None:
        """PythonTracebackTrimmer is an instance of Trimmer."""
        assert isinstance(PythonTracebackTrimmer(max_chars=100), Trimmer)


class TestPythonTracebackTrimmerIdempotence:
    """Content within max_chars is returned unchanged."""

    def test_short_content_returned_unchanged(self) -> None:
        """Content shorter than max_chars is returned as-is."""
        trimmer = PythonTracebackTrimmer(max_chars=1000)
        assert trimmer.trim(SAMPLE_TRACEBACK) == SAMPLE_TRACEBACK

    def test_exact_limit_returned_unchanged(self) -> None:
        """Content exactly at max_chars is returned unchanged."""
        content = "x" * 100
        trimmer = PythonTracebackTrimmer(max_chars=100)
        assert trimmer.trim(content) == content

    def test_empty_string_returned_unchanged(self) -> None:
        """Empty string is returned as-is."""
        assert PythonTracebackTrimmer(max_chars=100).trim("") == ""


class TestPythonTracebackTrimmerTruncation:
    """Oversized content is truncated, preserving the tail."""

    def test_tail_is_preserved(self) -> None:
        """The last max_chars characters of the traceback are kept."""
        trimmer = PythonTracebackTrimmer(max_chars=50)
        result = trimmer.trim(SAMPLE_TRACEBACK)
        assert result.endswith(SAMPLE_TRACEBACK[-50:])

    def test_truncation_marker_prepended(self) -> None:
        """A truncation marker is prepended when content is cut."""
        trimmer = PythonTracebackTrimmer(max_chars=50)
        result = trimmer.trim(SAMPLE_TRACEBACK)
        assert result.startswith("[")

    def test_result_within_max_chars_plus_marker(self) -> None:
        """The trimmed result payload (tail portion) is at most max_chars chars."""
        trimmer = PythonTracebackTrimmer(max_chars=50)
        result = trimmer.trim(SAMPLE_TRACEBACK)
        # Tail portion must be exactly max_chars; marker is extra
        assert result.endswith(SAMPLE_TRACEBACK[-50:])
        assert len(result) > 50  # marker adds characters

    def test_last_line_preserved(self) -> None:
        """The final exception line is always present in the trimmed output."""
        trimmer = PythonTracebackTrimmer(max_chars=30)
        result = trimmer.trim(SAMPLE_TRACEBACK)
        assert "ValueError: bad input" in result

    def test_trim_does_not_modify_content_within_budget(self) -> None:
        """Content already within max_chars is returned unchanged on any call."""
        # Use a budget large enough that the once-trimmed result fits
        trimmer = PythonTracebackTrimmer(max_chars=1000)
        once = trimmer.trim(SAMPLE_TRACEBACK)
        # once == SAMPLE_TRACEBACK (fits); a second trim should also leave it unchanged
        assert trimmer.trim(once) == once


# ---------------------------------------------------------------------------
# P7-T01 RED: Trimmer structured logging
# ---------------------------------------------------------------------------


class TestPythonTracebackTrimmerLogging:
    """P7-T01: PythonTracebackTrimmer emits INFO log to argent.trimmer on truncation.

    CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL until
    traceback.py emits logging.getLogger("argent.trimmer").info(...) on the
    truncation path.
    """

    def test_emits_info_log_when_content_cut(self, caplog: pytest.LogCaptureFixture) -> None:
        """An INFO record is emitted to argent.trimmer when the traceback is truncated."""
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            PythonTracebackTrimmer(max_chars=50).trim(SAMPLE_TRACEBACK)
        assert any(r.levelno == logging.INFO for r in caplog.records)

    def test_log_record_includes_chars_dropped_and_max_chars(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The INFO log message includes both chars_dropped and max_chars."""
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            PythonTracebackTrimmer(max_chars=50).trim(SAMPLE_TRACEBACK)
        messages = [r.message for r in caplog.records]
        assert any("chars_dropped" in m for m in messages)
        assert any("max_chars" in m for m in messages)

    def test_no_log_when_content_fits(self, caplog: pytest.LogCaptureFixture) -> None:
        """No log is emitted when the traceback fits within the budget."""
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            PythonTracebackTrimmer(max_chars=10_000).trim(SAMPLE_TRACEBACK)
        assert not caplog.records
