"""Trimmer protocol for format-aware output truncators.

All trimmer implementations must satisfy this protocol so they compose
uniformly in the egress stage of the middleware pipeline.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Trimmer(Protocol):
    """Protocol for format-aware output truncators.

    A Trimmer receives a string payload and returns a (possibly shorter)
    string that preserves structural integrity of the original format
    (BR-02: No Blind Truncation).

    Implementations must be idempotent: if ``content`` is already within
    the configured budget, it must be returned unchanged.
    """

    def trim(self, content: str) -> str:  # pragma: no cover
        """Truncate *content* to fit within the configured character budget.

        Args:
            content: The string to trim.  May be any format the trimmer
                understands; unrecognised content is returned unchanged.

        Returns:
            A string of length ≤ original length.  Structural integrity
            is preserved per the trimmer's format rules.
        """
        ...
