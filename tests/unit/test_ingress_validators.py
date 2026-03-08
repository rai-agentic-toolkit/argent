"""Tests for ingress byte-size and depth-limit validators.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/ingress/validators.py and exceptions.py exist.
"""

from __future__ import annotations

import inspect

import pytest

from argent.ingress.exceptions import NestingDepthError, PayloadTooLargeError
from argent.ingress.validators import ByteSizeValidator, DepthLimitValidator
from argent.pipeline.context import AgentContext, ExecutionState
from argent.pipeline.pipeline import Pipeline


class TestByteSizeValidator:
    """Tests for ByteSizeValidator middleware."""

    async def test_small_payload_passes_without_mutation(self) -> None:
        """A payload within the size limit passes with no state change."""
        ctx = AgentContext(raw_payload=b"hello world")
        validator = ByteSizeValidator()
        await validator(ctx)
        assert ctx.execution_state is ExecutionState.PENDING

    async def test_raises_on_oversized_payload(self) -> None:
        """A payload exceeding max_bytes raises PayloadTooLargeError."""
        ctx = AgentContext(raw_payload=b"x" * 1_048_577)  # 1 byte over 1MB default
        validator = ByteSizeValidator()
        with pytest.raises(PayloadTooLargeError):
            await validator(ctx)

    async def test_halts_context_on_violation(self) -> None:
        """Context execution_state is set to HALTED before raising."""
        ctx = AgentContext(raw_payload=b"x" * 1_048_577)
        validator = ByteSizeValidator()
        with pytest.raises(PayloadTooLargeError):
            await validator(ctx)
        assert ctx.execution_state is ExecutionState.HALTED

    async def test_configurable_max_bytes(self) -> None:
        """ByteSizeValidator(max_bytes=100) rejects a 101-byte payload."""
        ctx = AgentContext(raw_payload=b"x" * 101)
        validator = ByteSizeValidator(max_bytes=100)
        with pytest.raises(PayloadTooLargeError):
            await validator(ctx)

    async def test_exactly_at_limit_passes(self) -> None:
        """A payload exactly at max_bytes passes without error."""
        ctx = AgentContext(raw_payload=b"x" * 100)
        validator = ByteSizeValidator(max_bytes=100)
        await validator(ctx)
        assert ctx.execution_state is ExecutionState.PENDING

    async def test_empty_payload_passes(self) -> None:
        """An empty payload is always within the size limit."""
        ctx = AgentContext(raw_payload=b"")
        await ByteSizeValidator()(ctx)
        assert ctx.execution_state is ExecutionState.PENDING

    async def test_error_includes_actual_and_limit(self) -> None:
        """PayloadTooLargeError message includes the actual size and limit."""
        ctx = AgentContext(raw_payload=b"x" * 200)
        validator = ByteSizeValidator(max_bytes=100)
        with pytest.raises(PayloadTooLargeError) as exc_info:
            await validator(ctx)
        msg = str(exc_info.value)
        assert "200" in msg
        assert "100" in msg

    async def test_default_limit_is_one_megabyte(self) -> None:
        """Default ByteSizeValidator allows exactly 1MB (1_048_576 bytes)."""
        ctx = AgentContext(raw_payload=b"x" * 1_048_576)
        await ByteSizeValidator()(ctx)
        assert ctx.execution_state is ExecutionState.PENDING


class TestDepthLimitValidator:
    """Tests for DepthLimitValidator middleware."""

    async def test_shallow_payload_passes(self) -> None:
        """A flat payload within the nesting depth limit passes."""
        payload = b'{"key": "value", "another": 1}'
        ctx = AgentContext(raw_payload=payload)
        validator = DepthLimitValidator()
        await validator(ctx)
        assert ctx.execution_state is ExecutionState.PENDING

    async def test_raises_on_deeply_nested_payload(self) -> None:
        """A payload exceeding max_depth raises NestingDepthError."""
        # 21 levels of nesting exceeds default max_depth=20
        deep = b"{" * 21 + b"}" * 21
        ctx = AgentContext(raw_payload=deep)
        validator = DepthLimitValidator()
        with pytest.raises(NestingDepthError):
            await validator(ctx)

    async def test_halts_context_on_depth_violation(self) -> None:
        """Context execution_state is set to HALTED before raising NestingDepthError."""
        deep = b"[" * 25 + b"]" * 25
        ctx = AgentContext(raw_payload=deep)
        validator = DepthLimitValidator()
        with pytest.raises(NestingDepthError):
            await validator(ctx)
        assert ctx.execution_state is ExecutionState.HALTED

    async def test_configurable_max_depth(self) -> None:
        """DepthLimitValidator(max_depth=5) rejects a 6-level payload."""
        deep = b"{" * 6 + b"}" * 6
        ctx = AgentContext(raw_payload=deep)
        validator = DepthLimitValidator(max_depth=5)
        with pytest.raises(NestingDepthError):
            await validator(ctx)

    async def test_exactly_at_depth_limit_passes(self) -> None:
        """A payload at exactly max_depth levels passes."""
        at_limit = b"{" * 5 + b"}" * 5
        ctx = AgentContext(raw_payload=at_limit)
        validator = DepthLimitValidator(max_depth=5)
        await validator(ctx)
        assert ctx.execution_state is ExecutionState.PENDING

    async def test_plaintext_payload_passes(self) -> None:
        """A plain text payload with no brackets passes depth check."""
        ctx = AgentContext(raw_payload=b"hello world, no brackets here")
        await DepthLimitValidator()(ctx)
        assert ctx.execution_state is ExecutionState.PENDING

    async def test_mixed_brackets_count_together(self) -> None:
        """Both { and [ brackets contribute to depth estimate."""
        # 11 levels: 6 { + 5 [ exceeds max_depth=10
        mixed = b"{" * 6 + b"[" * 5 + b"]" * 5 + b"}" * 6
        ctx = AgentContext(raw_payload=mixed)
        validator = DepthLimitValidator(max_depth=10)
        with pytest.raises(NestingDepthError):
            await validator(ctx)

    async def test_empty_bytes_passes(self) -> None:
        """An empty payload has estimated depth 0 — always below any limit."""
        ctx = AgentContext(raw_payload=b"")
        await DepthLimitValidator()(ctx)
        assert ctx.execution_state is ExecutionState.PENDING


class TestDepthLimitValidatorQuoteAwareness:
    """Tests for P6-T03: quote-aware bracket counting in _estimate_depth.

    CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
    until _estimate_depth is updated to skip brackets inside string literals.
    """

    def test_brackets_inside_string_value_score_depth_one(self) -> None:
        """Brackets inside a quoted string don't increment structural depth."""
        payload = b'{"key": "value with {braces} and [brackets]"}'
        assert DepthLimitValidator._estimate_depth(payload) == 1

    def test_escaped_quote_does_not_end_string_tracking(self) -> None:
        """Escaped quote inside a string doesn't prematurely end string mode."""
        payload = b'{"key": "say \\"hello {world}\\""}'
        assert DepthLimitValidator._estimate_depth(payload) == 1

    def test_legitimate_nesting_depth_unchanged(self) -> None:
        """Real structural nesting still computes the correct depth."""
        payload = b'{"a": {"b": [1, 2]}}'
        assert DepthLimitValidator._estimate_depth(payload) == 3

    def test_string_with_bracket_and_outer_nesting(self) -> None:
        """Template string in one key does not pollute depth of real nesting."""
        payload = b'{"template": "use {var}", "data": {"nested": true}}'
        # Structural brackets: outer { at depth 1, inner { at depth 2
        assert DepthLimitValidator._estimate_depth(payload) == 2

    async def test_deeply_nested_with_string_brackets_passes(self) -> None:
        """Structural depth 3 with string brackets is not incorrectly rejected."""
        ctx = AgentContext(raw_payload=b'{"a": {"b": {"msg": "no {nesting} here"}}}')
        # Structural depth is 3 (three real { levels); string {nesting} must not count
        validator = DepthLimitValidator(max_depth=3)
        await validator(ctx)  # must not raise — depth == limit == 3


class TestValidatorsAsMiddleware:
    """Tests confirming validators plug into the async Pipeline."""

    async def test_byte_size_validator_is_awaitable(self) -> None:
        """ByteSizeValidator instances are async callables (Middleware-compatible)."""
        validator = ByteSizeValidator()
        ctx = AgentContext(raw_payload=b"data")
        result = validator(ctx)
        assert inspect.isawaitable(result)
        await result

    async def test_depth_limit_validator_is_awaitable(self) -> None:
        """DepthLimitValidator instances are async callables (Middleware-compatible)."""
        validator = DepthLimitValidator()
        ctx = AgentContext(raw_payload=b"data")
        result = validator(ctx)
        assert inspect.isawaitable(result)
        await result

    async def test_validators_compose_in_pipeline(self) -> None:
        """Both validators can be chained in the Pipeline ingress stage."""
        ctx = AgentContext(raw_payload=b'{"key": "value"}')
        pipeline = Pipeline(
            ingress=[ByteSizeValidator(max_bytes=1024), DepthLimitValidator(max_depth=5)]
        )
        result = await pipeline.run(ctx)
        assert result is ctx
        assert ctx.execution_state is ExecutionState.COMPLETE
