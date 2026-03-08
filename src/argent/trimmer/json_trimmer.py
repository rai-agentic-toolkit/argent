"""Format-aware truncators for JSON arrays and objects.

BR-02 (No Blind Truncation): truncation always produces valid JSON.

- ``JsonArrayTrimmer``: drops elements from the tail, appending a tombstone
  string as the last element to signal how many items were removed.
- ``JsonDictTrimmer``: drops keys whose values have the largest serialised
  size first, ensuring the result fits while retaining the most concise
  keys.  At least one key is always retained.
"""

from __future__ import annotations

import json
import logging
from typing import Any

_logger = logging.getLogger("argent.trimmer")


class JsonArrayTrimmer:
    """Trim a JSON array by dropping tail elements and appending a tombstone.

    Args:
        max_chars: Maximum character budget for the JSON output string.
    """

    def __init__(self, max_chars: int) -> None:
        self._max_chars = max_chars

    def trim(self, content: str) -> str:
        """Return *content* trimmed to ``max_chars`` JSON characters.

        Drops items from the tail of the array.  The last element of the
        returned array is a tombstone string ``"... [N items truncated]"``
        when any items were removed.  Non-JSON or non-array content is
        returned unchanged.

        Args:
            content: A JSON array string.

        Returns:
            A valid JSON array string within the character budget, or the
            original string if it already fits or is not a JSON array.
        """
        if len(content) <= self._max_chars:
            return content

        try:
            parsed: Any = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return content

        if not isinstance(parsed, list):
            return content

        items = list(parsed)
        original_len = len(items)

        while items:
            dropped = original_len - len(items)
            tombstone = f"... [{dropped} items truncated]"
            candidate_items = [*items, tombstone]
            candidate = json.dumps(candidate_items)
            if len(candidate) <= self._max_chars:
                _logger.info(
                    "%s: chars_dropped=%d max_chars=%d",
                    self.__class__.__name__,
                    len(content) - len(candidate),
                    self._max_chars,
                )
                return candidate
            items.pop()

        # Even a single-element tombstone array
        tombstone = f"... [{original_len} items truncated]"
        result = json.dumps([tombstone])
        _logger.info(
            "%s: chars_dropped=%d max_chars=%d",
            self.__class__.__name__,
            len(content) - len(result),
            self._max_chars,
        )
        return result


class JsonDictTrimmer:
    """Trim a JSON object by dropping keys with the largest serialised values.

    At least one key is always retained regardless of the budget.

    Args:
        max_chars: Maximum character budget for the JSON output string.
    """

    def __init__(self, max_chars: int) -> None:
        self._max_chars = max_chars

    def trim(self, content: str) -> str:
        """Return *content* trimmed to ``max_chars`` JSON characters.

        Keys are dropped in descending order of their serialised value
        size (largest first) until the result fits within the budget.
        At least one key is always kept.  Non-JSON or non-object content
        is returned unchanged.

        Args:
            content: A JSON object string.

        Returns:
            A valid JSON object string within the character budget, or the
            original string if it already fits or is not a JSON object.
        """
        if len(content) <= self._max_chars:
            return content

        try:
            parsed: Any = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return content

        if not isinstance(parsed, dict):
            return content

        # Sort keys by serialised value length, largest first (drop these first)
        keys_by_size = sorted(parsed.keys(), key=lambda k: len(json.dumps(parsed[k])), reverse=True)
        remaining = dict(parsed)

        for key in keys_by_size:
            if len(remaining) <= 1:
                break  # always keep at least one key
            del remaining[key]
            candidate = json.dumps(remaining)
            if len(candidate) <= self._max_chars:
                _logger.info(
                    "%s: chars_dropped=%d max_chars=%d",
                    self.__class__.__name__,
                    len(content) - len(candidate),
                    self._max_chars,
                )
                return candidate

        # Reached when break fires (len(remaining) == 1): return the single remaining key.
        result = json.dumps(remaining)
        _logger.info(
            "%s: chars_dropped=%d max_chars=%d",
            self.__class__.__name__,
            len(content) - len(result),
            self._max_chars,
        )
        return result
