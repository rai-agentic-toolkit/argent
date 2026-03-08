"""Semantic SQL validator — The Guard's first concrete security policy.

Uses ``sqlglot`` (optional extra ``argent[sql]``) to parse SQL payloads
via an AST and block destructive DML operations.

Business Rule BR-03 (Semantic Over Syntactic Security): validation is
performed on the parsed AST, not on raw string substring matching.  This
ensures that obfuscated queries (unusual whitespace, multi-statement batches,
SQL comments) cannot bypass the policy.

Blocked statement types: ``DROP``, ``DELETE``, ``TRUNCATE``, ``ALTER``.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from argent.security.exceptions import SecurityViolationError

if TYPE_CHECKING:
    from argent.pipeline.context import AgentContext

# sqlglot AST class names (verified against sqlglot >= 20.0.0) for the four
# destructive DML operations blocked by this policy.
_BLOCKED_STMT_TYPES: frozenset[str] = frozenset({"Drop", "Delete", "TruncateTable", "Alter"})

# Maps sqlglot AST class names to their SQL keyword equivalents for
# operator-facing error messages (verified against sqlglot >= 20.0.0).
_STMT_TYPE_TO_KEYWORD: dict[str, str] = {
    "Drop": "DROP",
    "Delete": "DELETE",
    "TruncateTable": "TRUNCATE",
    "Alter": "ALTER",
}

_POLICY_NAME = "SqlAstValidator"


class SqlAstValidator:
    """Semantic SQL security validator using sqlglot AST parsing.

    Inspects ``context.parsed_ast`` when it is a string, parses it with
    ``sqlglot``, and raises :class:`~argent.security.exceptions.SecurityViolationError`
    if the AST contains any destructive statement (``DROP``, ``DELETE``,
    ``TRUNCATE``, or ``ALTER``).

    Non-string values of ``parsed_ast`` (dicts, lists, ``ET.Element``,
    ``None``) are skipped silently — the validator only activates for
    SQL payloads.

    Raises:
        ImportError: At construction time if ``sqlglot`` is not installed.
            Install the ``sql`` optional extra to enable:
            ``pip install argent[sql]``
        SecurityViolationError: From :meth:`validate` when a destructive
            SQL statement is detected in ``context.parsed_ast``.
    """

    def __init__(self) -> None:
        try:
            import sqlglot  # noqa: F401 PLC0415
        except ImportError:
            raise ImportError(
                "sqlglot is not installed; SQL validation is unavailable. "
                "Install the 'sql' optional extra: pip install argent[sql]"
            ) from None

    def validate(self, context: AgentContext) -> None:
        """Parse and inspect *context.parsed_ast* for destructive SQL.

        Args:
            context: The shared agent execution context.

        Raises:
            SecurityViolationError: If the SQL AST contains a blocked
                statement (``DROP``, ``DELETE``, ``TRUNCATE``, ``ALTER``).
        """
        if not isinstance(context.parsed_ast, str):
            return

        import sqlglot  # noqa: PLC0415

        try:
            statements = sqlglot.parse(context.parsed_ast)
        except sqlglot.errors.ParseError:
            # Malformed SQL is rejected at the database layer, not the security layer.
            return
        except Exception as exc:
            # Unexpected sqlglot error — emit a diagnostic and allow the payload through.
            # The database layer is the final authority on malformed or unusual input.
            sys.stderr.write(
                f"[argent.security] SqlAstValidator: unexpected error from sqlglot.parse: "
                f"{type(exc).__name__}: {exc}\n"
            )
            return

        for stmt in statements:
            if stmt is None:
                continue
            stmt_type = type(stmt).__name__
            if stmt_type in _BLOCKED_STMT_TYPES:
                keyword = _STMT_TYPE_TO_KEYWORD.get(stmt_type, stmt_type)
                raise SecurityViolationError(
                    policy_name=_POLICY_NAME,
                    reason=f"Destructive SQL statement blocked: {keyword}",
                )
