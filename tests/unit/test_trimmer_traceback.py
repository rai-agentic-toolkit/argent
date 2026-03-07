"""Tests for PythonTracebackTrimmer.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/trimmer/traceback.py exists.
"""

from __future__ import annotations

from argent.trimmer.traceback import PythonTracebackTrimmer

SAMPLE_TRACEBACK = """\
Traceback (most recent call last):
  File "agent.py", line 10, in run
    result = tool()
  File "tool.py", line 5, in tool
    raise ValueError("bad input")
ValueError: bad input"""


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

    def test_trim_is_idempotent_on_already_trimmed(self) -> None:
        """Trimming an already-trimmed traceback does not further shorten it."""
        trimmer = PythonTracebackTrimmer(max_chars=50)
        once = trimmer.trim(SAMPLE_TRACEBACK)
        twice = trimmer.trim(once)
        assert twice == once
