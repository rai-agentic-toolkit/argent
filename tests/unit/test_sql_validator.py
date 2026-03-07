"""Tests for SqlAstValidator.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/security/sql_validator.py exists.
"""

import sys

import pytest

from argent.pipeline.context import AgentContext
from argent.security.exceptions import SecurityViolationError
from argent.security.sql_validator import SqlAstValidator


class TestSqlAstValidatorConstruction:
    """Tests for SqlAstValidator instantiation."""

    def test_constructs_when_sqlglot_available(self) -> None:
        """SqlAstValidator constructs successfully when sqlglot is installed."""
        validator = SqlAstValidator()
        assert isinstance(validator, SqlAstValidator)

    def test_raises_security_violation_when_sqlglot_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SqlAstValidator raises SecurityViolationError (not ImportError) when sqlglot absent."""
        monkeypatch.setitem(sys.modules, "sqlglot", None)
        with pytest.raises(SecurityViolationError, match="sqlglot"):
            SqlAstValidator()


class TestSqlAstValidatorPassingCases:
    """Tests for queries that SqlAstValidator should allow through."""

    def test_passes_safe_select(self) -> None:
        """SELECT statement is not blocked."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "SELECT id, name FROM users WHERE active = 1"
        SqlAstValidator().validate(ctx)  # must not raise

    def test_passes_insert(self) -> None:
        """INSERT statement is not blocked."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "INSERT INTO logs (msg) VALUES ('hello')"
        SqlAstValidator().validate(ctx)

    def test_passes_update(self) -> None:
        """UPDATE statement is not blocked."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "UPDATE users SET name = 'Alice' WHERE id = 1"
        SqlAstValidator().validate(ctx)

    def test_skips_non_string_parsed_ast(self) -> None:
        """Validator skips validation when parsed_ast is a dict (non-SQL context)."""
        ctx = AgentContext(raw_payload=b"data")
        ctx.parsed_ast = {"key": "value"}
        SqlAstValidator().validate(ctx)  # must not raise

    def test_skips_none_parsed_ast(self) -> None:
        """Validator skips validation when parsed_ast is None (default)."""
        ctx = AgentContext(raw_payload=b"data")
        SqlAstValidator().validate(ctx)  # parsed_ast defaults to None

    def test_skips_list_parsed_ast(self) -> None:
        """Validator skips validation when parsed_ast is a list."""
        ctx = AgentContext(raw_payload=b"data")
        ctx.parsed_ast = ["item1", "item2"]
        SqlAstValidator().validate(ctx)


class TestSqlAstValidatorBlockingCases:
    """Tests for queries that SqlAstValidator must block."""

    def test_blocks_drop_table(self) -> None:
        """DROP TABLE raises SecurityViolationError with policy_name=SqlAstValidator."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "DROP TABLE users"
        with pytest.raises(SecurityViolationError) as exc_info:
            SqlAstValidator().validate(ctx)
        assert exc_info.value.policy_name == "SqlAstValidator"
        assert "DROP" in exc_info.value.reason.upper() or "drop" in exc_info.value.reason.lower()

    def test_blocks_delete(self) -> None:
        """DELETE FROM raises SecurityViolationError."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "DELETE FROM users WHERE id = 1"
        with pytest.raises(SecurityViolationError):
            SqlAstValidator().validate(ctx)

    def test_blocks_truncate(self) -> None:
        """TRUNCATE TABLE raises SecurityViolationError."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "TRUNCATE TABLE audit_log"
        with pytest.raises(SecurityViolationError):
            SqlAstValidator().validate(ctx)

    def test_blocks_alter_table(self) -> None:
        """ALTER TABLE raises SecurityViolationError."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "ALTER TABLE users ADD COLUMN age INT"
        with pytest.raises(SecurityViolationError):
            SqlAstValidator().validate(ctx)

    def test_blocks_drop_in_multistatement(self) -> None:
        """DROP embedded in a multi-statement query is blocked."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "SELECT 1; DROP TABLE users"
        with pytest.raises(SecurityViolationError):
            SqlAstValidator().validate(ctx)

    def test_blocks_drop_with_extra_whitespace(self) -> None:
        """AST-level parsing blocks DROP even with unusual whitespace (BR-03: semantic check)."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "DROP  \t\n  TABLE users"
        with pytest.raises(SecurityViolationError):
            SqlAstValidator().validate(ctx)
