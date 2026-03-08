"""Tests for SqlAstValidator.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/security/sql_validator.py exists.
"""

import logging
import sys

import pytest
import sqlglot

from argent.pipeline.context import AgentContext
from argent.security.exceptions import SecurityViolationError
from argent.security.sql_validator import (
    _BLOCKED_STMT_TYPES,
    _STMT_TYPE_TO_KEYWORD,
    SqlAstValidator,
)


class TestSqlAstValidatorConstruction:
    """Tests for SqlAstValidator instantiation."""

    def test_constructs_when_sqlglot_available(self) -> None:
        """SqlAstValidator constructs successfully when sqlglot is installed."""
        validator = SqlAstValidator()
        assert isinstance(validator, SqlAstValidator)

    def test_raises_import_error_when_sqlglot_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SqlAstValidator raises ImportError (not SecurityViolationError) when sqlglot absent."""
        monkeypatch.setitem(sys.modules, "sqlglot", None)
        with pytest.raises(ImportError, match="sqlglot"):
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


class TestSqlAstValidatorEdgeCases:
    """Tests for edge-case inputs to SqlAstValidator."""

    def test_passes_empty_string_sql(self) -> None:
        """Empty string parsed_ast produces no blocking statements."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = ""
        SqlAstValidator().validate(ctx)  # must not raise

    def test_handles_sqlglot_parse_exception_gracefully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When sqlglot.parse raises ParseError, the validator returns without error."""
        monkeypatch.setattr(
            sqlglot, "parse", lambda _: (_ for _ in ()).throw(sqlglot.errors.ParseError("boom"))
        )
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "some sql"
        SqlAstValidator().validate(ctx)  # must not raise

    def test_handles_unexpected_sqlglot_error_with_warning_log(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When sqlglot.parse raises an unexpected error, validator returns and logs a WARNING."""
        monkeypatch.setattr(
            sqlglot, "parse", lambda _: (_ for _ in ()).throw(RuntimeError("unexpected"))
        )
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "some sql"
        with caplog.at_level(logging.WARNING, logger="argent.security"):
            SqlAstValidator().validate(ctx)  # must not raise
        assert any("SqlAstValidator" in r.message for r in caplog.records)


class TestSqlAstValidatorBlockingCases:
    """Tests for queries that SqlAstValidator must block."""

    def test_blocks_drop_table(self) -> None:
        """DROP TABLE raises SecurityViolationError with policy_name=SqlAstValidator."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "DROP TABLE users"
        with pytest.raises(SecurityViolationError) as exc_info:
            SqlAstValidator().validate(ctx)
        assert exc_info.value.policy_name == "SqlAstValidator"
        assert "DROP" in exc_info.value.reason

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


# ---------------------------------------------------------------------------
# P7-T02 RED: Security validator structured logging
# ---------------------------------------------------------------------------


class TestSqlAstValidatorLogging:
    """P7-T02: SqlAstValidator emits to Python logging, not sys.stderr.

    CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL until
    sql_validator.py replaces sys.stderr.write with logger.warning and adds
    logger.info before raising SecurityViolationError.
    """

    def test_blocked_statement_emits_warning_log(self, caplog: pytest.LogCaptureFixture) -> None:
        """A WARNING record is emitted to argent.security when a statement is blocked."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "DROP TABLE users"
        with (
            caplog.at_level(logging.WARNING, logger="argent.security"),
            pytest.raises(SecurityViolationError),
        ):
            SqlAstValidator().validate(ctx)
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_blocked_statement_log_includes_keyword(self, caplog: pytest.LogCaptureFixture) -> None:
        """The WARNING log message includes the blocked SQL keyword."""
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "DROP TABLE users"
        with (
            caplog.at_level(logging.WARNING, logger="argent.security"),
            pytest.raises(SecurityViolationError),
        ):
            SqlAstValidator().validate(ctx)
        assert any("DROP" in r.message for r in caplog.records)

    def test_unexpected_error_emits_warning_log_not_stderr(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Unexpected sqlglot error emits WARNING to argent.security (not stderr)."""
        monkeypatch.setattr(
            sqlglot, "parse", lambda _: (_ for _ in ()).throw(RuntimeError("unexpected"))
        )
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "some sql"
        with caplog.at_level(logging.WARNING, logger="argent.security"):
            SqlAstValidator().validate(ctx)
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_unexpected_error_no_longer_writes_to_stderr(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Unexpected sqlglot error must NOT write to stderr after P7-T02 GREEN."""
        monkeypatch.setattr(
            sqlglot, "parse", lambda _: (_ for _ in ()).throw(RuntimeError("unexpected"))
        )
        ctx = AgentContext(raw_payload=b"sql")
        ctx.parsed_ast = "some sql"
        SqlAstValidator().validate(ctx)
        captured = capsys.readouterr()
        assert captured.err == ""


# ---------------------------------------------------------------------------
# P7-T03 RED: sqlglot version contract
# ---------------------------------------------------------------------------


class TestSqlglotVersionContract:
    """P7-T03: sqlglot AST class names used in _BLOCKED_STMT_TYPES must exist.

    CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL if
    the sqlglot upper bound is not set or the class names are renamed in
    a future sqlglot release.

    The tests are skipped (not failed) when sqlglot is not installed.
    """

    def test_blocked_stmt_type_class_names_exist_in_sqlglot_expressions(self) -> None:
        """Every class name in _BLOCKED_STMT_TYPES exists as an attribute on sqlglot.expressions."""
        sqlglot_expressions = pytest.importorskip("sqlglot.expressions")
        for class_name in _BLOCKED_STMT_TYPES:
            assert hasattr(sqlglot_expressions, class_name), (
                f"sqlglot.expressions.{class_name} not found — sqlglot may have "
                f"renamed this AST node. Update _BLOCKED_STMT_TYPES in sql_validator.py."
            )

    def test_stmt_type_to_keyword_keys_exist_in_sqlglot_expressions(self) -> None:
        """Every key in _STMT_TYPE_TO_KEYWORD corresponds to a class in sqlglot.expressions."""
        sqlglot_expressions = pytest.importorskip("sqlglot.expressions")
        for class_name in _STMT_TYPE_TO_KEYWORD:
            assert hasattr(sqlglot_expressions, class_name), (
                f"sqlglot.expressions.{class_name} not found — sqlglot may have "
                f"renamed this AST node. Update _STMT_TYPE_TO_KEYWORD in sql_validator.py."
            )

    def test_blocked_stmt_type_names_are_actual_expression_classes(self) -> None:
        """Each name in _BLOCKED_STMT_TYPES maps to an actual class, not just an attribute."""
        sqlglot_expressions = pytest.importorskip("sqlglot.expressions")
        for class_name in _BLOCKED_STMT_TYPES:
            obj = getattr(sqlglot_expressions, class_name, None)
            assert isinstance(obj, type), (
                f"sqlglot.expressions.{class_name} exists but is not a class "
                f"(got {type(obj).__name__})."
            )
