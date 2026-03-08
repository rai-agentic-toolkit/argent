"""Format-aware truncator for Markdown tables.

Header preservation strategy: the header row and separator row always
survive.  Body rows are dropped from the bottom until the serialised
table fits within the character budget (BR-02).
"""

from __future__ import annotations

import logging

_logger = logging.getLogger("argent.trimmer")


def _is_separator(line: str) -> bool:
    """Return True if *line* is a Markdown table separator row."""
    stripped = line.strip()
    return (
        bool(stripped)
        and all(ch in "|-: " for ch in stripped)
        and "|" in stripped
        and "-" in stripped
    )


class MarkdownTableTrimmer:
    """Truncate Markdown tables by dropping body rows from the bottom.

    The header row and separator row are always preserved.  If the table
    cannot be identified (no header/separator structure), the content is
    returned unchanged.

    Args:
        max_chars: Maximum character budget for the output string.
    """

    def __init__(self, max_chars: int) -> None:
        self._max_chars = max_chars

    def trim(self, content: str) -> str:
        """Return *content* truncated to ``max_chars`` by dropping tail rows.

        Args:
            content: A Markdown table string.  Non-table content is returned
                unchanged even if it exceeds the budget.

        Returns:
            A Markdown table string within the character budget, or the
            original string if it already fits or is not a table.
        """
        if len(content) <= self._max_chars:
            return content

        lines = content.splitlines()
        if len(lines) < 2:
            return content

        # Locate header and separator (len(lines) >= 2 guaranteed here)
        if not _is_separator(lines[1]):
            return content

        header = lines[0]
        separator = lines[1]
        body_rows = lines[2:]

        # Drop rows from the bottom until it fits
        kept_rows = list(body_rows)
        while kept_rows:
            candidate = "\n".join([header, separator, *kept_rows])
            if len(candidate) <= self._max_chars:
                _logger.info(
                    "%s: chars_dropped=%d max_chars=%d",
                    self.__class__.__name__,
                    len(content) - len(candidate),
                    self._max_chars,
                )
                return candidate
            kept_rows.pop()

        # Only header + separator remain
        result = "\n".join([header, separator])
        _logger.info(
            "%s: chars_dropped=%d max_chars=%d",
            self.__class__.__name__,
            len(content) - len(result),
            self._max_chars,
        )
        return result
