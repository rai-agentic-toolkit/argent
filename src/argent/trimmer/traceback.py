"""Format-aware truncator for Python tracebacks.

Tail preservation strategy: the most actionable information in a Python
traceback is the final frame and the exception line, which appear at the
end.  Truncation keeps the tail and prepends a marker.
"""

from __future__ import annotations


class PythonTracebackTrimmer:
    """Truncate Python tracebacks by keeping the tail (final frames).

    Args:
        max_chars: Maximum number of characters from the tail of the
            traceback to preserve.  Content already within this limit
            is returned unchanged.
    """

    def __init__(self, max_chars: int) -> None:
        self._max_chars = max_chars

    def trim(self, content: str) -> str:
        """Return *content* truncated to the last ``max_chars`` characters.

        If the content fits within the budget, it is returned as-is.
        Otherwise a ``[... N chars truncated ...]`` marker is prepended
        to the preserved tail so callers know output was cut.

        Args:
            content: A Python traceback string (or any string).

        Returns:
            The (possibly truncated) string with the tail preserved.
        """
        if len(content) <= self._max_chars:
            return content
        tail = content[-self._max_chars :]
        dropped = len(content) - self._max_chars
        marker = f"[... {dropped} chars truncated ...]\n"
        return marker + tail
