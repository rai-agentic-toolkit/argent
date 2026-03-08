"""Tests for JsonArrayTrimmer and JsonDictTrimmer.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/trimmer/json_trimmer.py exists.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from argent.trimmer.json_trimmer import JsonArrayTrimmer, JsonDictTrimmer


class TestJsonArrayTrimmerEdgeCases:
    """Edge paths: non-list JSON, extreme budget forcing fallback tombstone."""

    def test_json_object_passed_to_array_trimmer_returned_unchanged(self) -> None:
        """A JSON object (not an array) is returned unchanged by JsonArrayTrimmer."""
        content = json.dumps({"key": "value"})
        assert JsonArrayTrimmer(max_chars=5).trim(content) == content

    def test_extreme_budget_returns_tombstone_only_array(self) -> None:
        """When max_chars is tiny, all items are dropped and a tombstone array is returned."""
        items = ["a" * 50, "b" * 50]
        content = json.dumps(items)
        trimmer = JsonArrayTrimmer(max_chars=5)
        result = trimmer.trim(content)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert "truncated" in parsed[0]


class TestJsonArrayTrimmerIdempotence:
    """Short arrays pass through unchanged."""

    def test_short_array_returned_unchanged(self) -> None:
        """A JSON array within max_chars is returned as-is."""
        content = json.dumps(["a", "b", "c"])
        trimmer = JsonArrayTrimmer(max_chars=10_000)
        assert trimmer.trim(content) == content

    def test_empty_array_returned_unchanged(self) -> None:
        """An empty JSON array is returned unchanged."""
        assert JsonArrayTrimmer(max_chars=10).trim("[]") == "[]"

    def test_non_json_content_returned_unchanged(self) -> None:
        """Content that is not a JSON array is returned unchanged."""
        content = "not json"
        assert JsonArrayTrimmer(max_chars=5).trim(content) == content


class TestJsonArrayTrimmerTruncation:
    """Items are dropped from the tail; a tombstone is appended."""

    def test_output_is_valid_json(self) -> None:
        """Trimmed output is always valid JSON."""
        items = [f"item-{i}" for i in range(50)]
        content = json.dumps(items)
        trimmer = JsonArrayTrimmer(max_chars=100)
        result = trimmer.trim(content)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_tombstone_appended_on_truncation(self) -> None:
        """A tombstone string indicating truncation is the last element."""
        items = list(range(100))
        content = json.dumps(items)
        trimmer = JsonArrayTrimmer(max_chars=50)
        result = trimmer.trim(content)
        parsed = json.loads(result)
        assert isinstance(parsed[-1], str)
        assert "truncated" in parsed[-1]

    def test_tombstone_includes_count(self) -> None:
        """The tombstone string includes the number of truncated items."""
        items = list(range(100))
        content = json.dumps(items)
        trimmer = JsonArrayTrimmer(max_chars=50)
        result = trimmer.trim(content)
        parsed = json.loads(result)
        # tombstone contains a digit indicating count
        assert any(ch.isdigit() for ch in parsed[-1])

    def test_early_items_retained(self) -> None:
        """Items at the head of the array survive truncation."""
        items = [f"item-{i}" for i in range(100)]
        content = json.dumps(items)
        trimmer = JsonArrayTrimmer(max_chars=100)
        result = trimmer.trim(content)
        parsed = json.loads(result)
        assert parsed[0] == "item-0"

    def test_result_within_max_chars(self) -> None:
        """Trimmed JSON string is at most max_chars characters."""
        items = list(range(1000))
        content = json.dumps(items)
        trimmer = JsonArrayTrimmer(max_chars=100)
        result = trimmer.trim(content)
        assert len(result) <= 100


class TestJsonDictTrimmerEdgeCases:
    """Edge paths: non-dict JSON passed to DictTrimmer."""

    def test_json_array_passed_to_dict_trimmer_returned_unchanged(self) -> None:
        """A JSON array (not an object) is returned unchanged by JsonDictTrimmer."""
        content = json.dumps([1, 2, 3])
        assert JsonDictTrimmer(max_chars=5).trim(content) == content


class TestJsonDictTrimmerIdempotence:
    """Short dicts pass through unchanged."""

    def test_short_dict_returned_unchanged(self) -> None:
        """A JSON dict within max_chars is returned as-is."""
        content = json.dumps({"a": 1, "b": 2})
        trimmer = JsonDictTrimmer(max_chars=10_000)
        assert trimmer.trim(content) == content

    def test_empty_dict_returned_unchanged(self) -> None:
        """An empty JSON dict is returned unchanged."""
        assert JsonDictTrimmer(max_chars=10).trim("{}") == "{}"

    def test_non_json_content_returned_unchanged(self) -> None:
        """Content that is not a JSON object is returned unchanged."""
        content = "not json at all"
        assert JsonDictTrimmer(max_chars=5).trim(content) == content


class TestJsonDictTrimmerTruncation:
    """Large-value keys are dropped first; at least one key is always kept."""

    def test_output_is_valid_json(self) -> None:
        """Trimmed output is always valid JSON."""
        d = {f"key_{i}": "x" * 100 for i in range(20)}
        content = json.dumps(d)
        trimmer = JsonDictTrimmer(max_chars=100)
        result = trimmer.trim(content)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_never_returns_empty_dict(self) -> None:
        """At least one key is always retained, even under extreme budget."""
        d = {"only_key": "value" * 100}
        content = json.dumps(d)
        trimmer = JsonDictTrimmer(max_chars=5)
        result = trimmer.trim(content)
        parsed = json.loads(result)
        assert len(parsed) >= 1

    def test_result_within_max_chars(self) -> None:
        """Result is within max_chars when enough keys can be dropped."""
        d = {f"key_{i}": "v" * 50 for i in range(20)}
        content = json.dumps(d)
        trimmer = JsonDictTrimmer(max_chars=100)
        result = trimmer.trim(content)
        assert len(result) <= 100

    def test_large_value_keys_dropped_first(self) -> None:
        """Keys with the largest serialized values are dropped before small ones."""
        d = {"small": "x", "large": "y" * 500}
        content = json.dumps(d)
        trimmer = JsonDictTrimmer(max_chars=50)
        result = trimmer.trim(content)
        parsed = json.loads(result)
        assert "small" in parsed
        assert "large" not in parsed


# ---------------------------------------------------------------------------
# P7-T01 RED: Trimmer structured logging
# ---------------------------------------------------------------------------


class TestJsonArrayTrimmerLogging:
    """P7-T01: JsonArrayTrimmer emits INFO log to argent.trimmer on truncation.

    CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL until
    json_trimmer.py emits logging.getLogger("argent.trimmer").info(...) on
    the truncation path.
    """

    def test_emits_info_log_when_items_dropped(self, caplog: pytest.LogCaptureFixture) -> None:
        """An INFO record is emitted to argent.trimmer when items are dropped."""
        items = list(range(100))
        content = json.dumps(items)
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            JsonArrayTrimmer(max_chars=50).trim(content)
        assert any(r.levelno == logging.INFO for r in caplog.records)

    def test_log_record_includes_chars_dropped(self, caplog: pytest.LogCaptureFixture) -> None:
        """The INFO log message includes chars_dropped."""
        items = list(range(100))
        content = json.dumps(items)
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            JsonArrayTrimmer(max_chars=50).trim(content)
        assert any("chars_dropped" in r.message for r in caplog.records)

    def test_no_log_when_content_fits(self, caplog: pytest.LogCaptureFixture) -> None:
        """No log is emitted when content is within the budget."""
        content = json.dumps([1, 2, 3])
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            JsonArrayTrimmer(max_chars=10_000).trim(content)
        assert not caplog.records

    def test_no_log_for_non_json_content(self, caplog: pytest.LogCaptureFixture) -> None:
        """No log is emitted when content cannot be parsed as JSON."""
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            JsonArrayTrimmer(max_chars=5).trim("not json")
        assert not caplog.records


class TestJsonDictTrimmerLogging:
    """P7-T01: JsonDictTrimmer emits INFO log to argent.trimmer on truncation."""

    def test_emits_info_log_when_keys_dropped(self, caplog: pytest.LogCaptureFixture) -> None:
        """An INFO record is emitted to argent.trimmer when keys are dropped."""
        d = {f"key_{i}": "v" * 100 for i in range(10)}
        content = json.dumps(d)
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            JsonDictTrimmer(max_chars=50).trim(content)
        assert any(r.levelno == logging.INFO for r in caplog.records)

    def test_log_record_includes_max_chars(self, caplog: pytest.LogCaptureFixture) -> None:
        """The INFO log message includes max_chars."""
        d = {f"key_{i}": "v" * 100 for i in range(10)}
        content = json.dumps(d)
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            JsonDictTrimmer(max_chars=50).trim(content)
        assert any("max_chars" in r.message for r in caplog.records)

    def test_no_log_when_content_fits(self, caplog: pytest.LogCaptureFixture) -> None:
        """No log is emitted when content is within the budget."""
        content = json.dumps({"a": 1})
        with caplog.at_level(logging.INFO, logger="argent.trimmer"):
            JsonDictTrimmer(max_chars=10_000).trim(content)
        assert not caplog.records
