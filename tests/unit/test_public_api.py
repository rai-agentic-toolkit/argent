"""Tests for the public API surface of the argent package.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/__init__.py is updated with public re-exports.
"""

import argent
from argent import (
    AgentContext,
    BudgetExhaustedError,
    ByteSizeValidator,
    ContextBudgetCalculator,
    DepthLimitValidator,
    ExecutionState,
    JsonArrayTrimmer,
    JsonDictTrimmer,
    MarkdownTableTrimmer,
    NestingDepthError,
    PayloadTooLargeError,
    Pipeline,
    PythonTracebackTrimmer,
    RequestBudget,
    SecurityValidator,
    SecurityViolationError,
    SinglePassParser,
    SqlAstValidator,
    ToolExecutor,
    ToolRecursionError,
    ToolTimeoutError,
    Trimmer,
)


class TestCoreTypesPublicAPI:
    """Core pipeline types are importable from argent directly."""

    def test_pipeline_importable(self) -> None:
        """Pipeline is importable from argent."""
        assert Pipeline is not None

    def test_agent_context_importable(self) -> None:
        """AgentContext is importable from argent."""
        assert AgentContext is not None

    def test_execution_state_importable(self) -> None:
        """ExecutionState is importable from argent."""
        assert ExecutionState is not None


class TestBudgetTypesPublicAPI:
    """Budget and executor types are importable from argent directly."""

    def test_request_budget_importable(self) -> None:
        assert RequestBudget is not None

    def test_tool_executor_importable(self) -> None:
        assert ToolExecutor is not None

    def test_budget_exhausted_error_importable(self) -> None:
        assert BudgetExhaustedError is not None

    def test_tool_timeout_error_importable(self) -> None:
        assert ToolTimeoutError is not None

    def test_tool_recursion_error_importable(self) -> None:
        assert ToolRecursionError is not None


class TestIngressTypesPublicAPI:
    """Ingress validators and parser are importable from argent directly."""

    def test_byte_size_validator_importable(self) -> None:
        assert ByteSizeValidator is not None

    def test_depth_limit_validator_importable(self) -> None:
        assert DepthLimitValidator is not None

    def test_single_pass_parser_importable(self) -> None:
        assert SinglePassParser is not None

    def test_payload_too_large_error_importable(self) -> None:
        assert PayloadTooLargeError is not None

    def test_nesting_depth_error_importable(self) -> None:
        assert NestingDepthError is not None


class TestTrimmerTypesPublicAPI:
    """Trimmer protocol and concrete implementations are importable from argent."""

    def test_trimmer_protocol_importable(self) -> None:
        assert Trimmer is not None

    def test_python_traceback_trimmer_importable(self) -> None:
        assert PythonTracebackTrimmer is not None

    def test_markdown_table_trimmer_importable(self) -> None:
        assert MarkdownTableTrimmer is not None

    def test_json_array_trimmer_importable(self) -> None:
        assert JsonArrayTrimmer is not None

    def test_json_dict_trimmer_importable(self) -> None:
        assert JsonDictTrimmer is not None

    def test_context_budget_calculator_importable(self) -> None:
        assert ContextBudgetCalculator is not None


class TestSecurityTypesPublicAPI:
    """Security types are importable from argent directly."""

    def test_security_validator_importable(self) -> None:
        assert SecurityValidator is not None

    def test_security_violation_error_importable(self) -> None:
        assert SecurityViolationError is not None

    def test_sql_ast_validator_importable(self) -> None:
        assert SqlAstValidator is not None


class TestAllDefined:
    """__all__ is defined and contains key public types."""

    def test_all_is_defined(self) -> None:
        """argent.__all__ exists and is a list."""
        assert hasattr(argent, "__all__")
        assert isinstance(argent.__all__, list)

    def test_all_contains_core_types(self) -> None:
        """__all__ includes the fundamental pipeline types."""
        for name in ("Pipeline", "AgentContext", "ExecutionState"):
            assert name in argent.__all__, f"{name!r} missing from argent.__all__"

    def test_all_contains_security_types(self) -> None:
        """__all__ includes the security types added in Phase 5."""
        for name in ("SecurityValidator", "SecurityViolationError", "SqlAstValidator"):
            assert name in argent.__all__, f"{name!r} missing from argent.__all__"
