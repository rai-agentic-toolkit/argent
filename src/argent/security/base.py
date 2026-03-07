"""Public re-export of the SecurityValidator protocol for Epic 5 consumers.

The ``SecurityValidator`` protocol is defined in ``pipeline/pipeline.py``
(alongside ``Middleware``) because it is a pipeline extensibility point, not
a security-specific implementation.  This module re-exports it from its
canonical location so that consumers can use the ergonomic import path:

    from argent.security.base import SecurityValidator

This is a downward dependency (Epic 5 → Epic 1) guarded at runtime by the
fact that ``pipeline`` is always available as a hard dependency.  Per
ADR-0004 Decision 4, cross-epic imports that go downward are permitted.
"""

from argent.pipeline.pipeline import SecurityValidator

__all__ = ["SecurityValidator"]
