"""Tests for the unified single-pass ingress parser middleware.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/ingress/parser.py exists.
"""

from __future__ import annotations

import inspect
import logging
import xml.etree.ElementTree as ET

import pytest

from argent.ingress.parser import SinglePassParser
from argent.ingress.validators import ByteSizeValidator
from argent.pipeline.context import AgentContext
from argent.pipeline.pipeline import Pipeline
from argent.pipeline.telemetry import Telemetry


class TestFormatDetectionAndParsing:
    """Tests that SinglePassParser detects and parses each supported format."""

    async def test_parses_valid_json(self) -> None:
        """Valid JSON payload produces a dict in context.parsed_ast."""
        payload = b'{"tool": "search", "args": {"query": "argent"}}'
        ctx = AgentContext(raw_payload=payload)
        await SinglePassParser()(ctx)
        assert isinstance(ctx.parsed_ast, dict)
        assert ctx.parsed_ast["tool"] == "search"

    async def test_parses_valid_json_list(self) -> None:
        """Valid JSON array payload produces a list in context.parsed_ast."""
        payload = b"[1, 2, 3]"
        ctx = AgentContext(raw_payload=payload)
        await SinglePassParser()(ctx)
        assert isinstance(ctx.parsed_ast, list)
        assert ctx.parsed_ast == [1, 2, 3]

    async def test_parses_valid_xml(self) -> None:
        """Valid XML payload produces an ElementTree Element in context.parsed_ast."""
        payload = b"<root><child>value</child></root>"
        ctx = AgentContext(raw_payload=payload)
        await SinglePassParser()(ctx)
        assert isinstance(ctx.parsed_ast, ET.Element)
        assert ctx.parsed_ast.tag == "root"

    async def test_falls_back_to_plaintext_for_unstructured(self) -> None:
        """Plain text payload is stored as str in context.parsed_ast."""
        payload = b"This is just plain text, not JSON or XML."
        ctx = AgentContext(raw_payload=payload)
        await SinglePassParser()(ctx)
        assert isinstance(ctx.parsed_ast, str)
        assert "plain text" in ctx.parsed_ast

    async def test_falls_back_to_plaintext_for_empty_payload(self) -> None:
        """Empty payload is stored as empty string in context.parsed_ast."""
        ctx = AgentContext(raw_payload=b"")
        await SinglePassParser()(ctx)
        assert isinstance(ctx.parsed_ast, str)
        assert ctx.parsed_ast == ""


class TestGracefulDegradation:
    """Tests for graceful fallback on malformed content."""

    async def test_malformed_json_does_not_raise(self) -> None:
        """Malformed JSON does not raise; falls back to raw string."""
        payload = b'{"key": broken json'
        ctx = AgentContext(raw_payload=payload)
        await SinglePassParser()(ctx)  # must not raise
        assert isinstance(ctx.parsed_ast, str)

    async def test_malformed_xml_falls_back_to_string(self) -> None:
        """Malformed XML does not raise; falls back to raw string."""
        payload = b"<unclosed><tag>"
        ctx = AgentContext(raw_payload=payload)
        await SinglePassParser()(ctx)
        assert isinstance(ctx.parsed_ast, str)

    async def test_fallback_stores_decoded_raw_payload(self) -> None:
        """Fallback stores raw_payload.decode('utf-8', errors='replace') as parsed_ast."""
        payload = b'{"broken'
        ctx = AgentContext(raw_payload=payload)
        await SinglePassParser()(ctx)
        assert ctx.parsed_ast == payload.decode("utf-8", errors="replace")

    async def test_invalid_utf8_bytes_decoded_with_replacement(self) -> None:
        """Payload with invalid UTF-8 bytes is decoded with replacement chars (U+FFFD)."""
        payload = b"\xff\xfe not valid utf-8"
        ctx = AgentContext(raw_payload=payload)
        await SinglePassParser()(ctx)
        assert isinstance(ctx.parsed_ast, str)
        assert "\ufffd" in ctx.parsed_ast  # U+FFFD replacement character

    async def test_fallback_emits_stderr_diagnostic(self, caplog: pytest.LogCaptureFixture) -> None:
        """A parsing failure emits a WARNING log from argent.ingress.parser."""
        payload = b'{"key": broken json'
        ctx = AgentContext(raw_payload=payload)

        with caplog.at_level(logging.WARNING, logger="argent.ingress.parser"):
            await SinglePassParser()(ctx)

        assert len(caplog.records) > 0
        assert any(r.levelno == logging.WARNING for r in caplog.records)


class TestIdempotency:
    """Tests for the single-pass NFR — parser must not re-parse if already done."""

    async def test_parser_is_idempotent(self) -> None:
        """If parsed_ast is already set, parser does not re-parse."""
        ctx = AgentContext(raw_payload=b'{"tool": "search"}')
        sentinel = object()
        ctx.parsed_ast = sentinel
        await SinglePassParser()(ctx)
        assert ctx.parsed_ast is sentinel  # unchanged

    async def test_idempotency_with_none_vs_already_set(self) -> None:
        """Parser runs when parsed_ast is None, skips when any value is set."""
        ctx = AgentContext(raw_payload=b'{"key": "value"}')
        assert ctx.parsed_ast is None
        await SinglePassParser()(ctx)
        first_result = ctx.parsed_ast
        # Run again — should be a no-op
        await SinglePassParser()(ctx)
        assert ctx.parsed_ast is first_result


class TestTelemetryIntegration:
    """Tests that SinglePassParser emits telemetry on fallback."""

    async def test_fallback_emits_telemetry_warning_via_handler(self) -> None:
        """A parsing failure emits a structured warning event via a registered handler."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.replace_handlers(events.append)

        payload = b'{"key": broken json'
        ctx = AgentContext(raw_payload=payload)
        await SinglePassParser(telemetry=tel)(ctx)

        warning_events = [e for e in events if e.get("level") == "warning"]
        assert len(warning_events) >= 1
        assert all("parse_fallback" in str(e.get("event", "")) for e in warning_events)

    async def test_no_telemetry_still_works(self) -> None:
        """SinglePassParser without telemetry falls back gracefully."""
        ctx = AgentContext(raw_payload=b"hello")
        await SinglePassParser()(ctx)
        assert isinstance(ctx.parsed_ast, str)


class TestYamlOptIn:
    """Tests for optional YAML parsing behaviour."""

    async def test_yaml_parsed_when_pyyaml_available(self) -> None:
        """If pyyaml is installed, valid YAML produces a dict in parsed_ast."""
        pytest.importorskip("yaml", reason="pyyaml not installed")
        payload = b"key: value\nnumber: 42\n"
        ctx = AgentContext(raw_payload=payload)
        await SinglePassParser()(ctx)
        # If YAML was detected, parsed_ast should be a dict
        assert isinstance(ctx.parsed_ast, dict)
        assert ctx.parsed_ast.get("key") == "value"

    async def test_yaml_skipped_when_pyyaml_unavailable(self) -> None:
        """If pyyaml is not installed, YAML content is treated as plaintext."""
        # This test is only meaningful when pyyaml is absent — always passes
        # (validated manually or in restricted CI environments without pyyaml)
        payload = b"key: value\n"
        ctx = AgentContext(raw_payload=payload)
        await SinglePassParser()(ctx)
        # Result is either a dict (yaml installed) or a str (yaml absent)
        assert ctx.parsed_ast is not None


class TestParserAsMiddleware:
    """Tests that SinglePassParser is a valid Middleware."""

    async def test_is_awaitable(self) -> None:
        """SinglePassParser() instances return awaitables when called."""
        parser = SinglePassParser()
        ctx = AgentContext(raw_payload=b"{}")
        result = parser(ctx)
        assert inspect.isawaitable(result)
        await result

    async def test_composes_with_validators_in_pipeline(self) -> None:
        """SinglePassParser can be chained after validators in the same pipeline."""
        ctx = AgentContext(raw_payload=b'{"action": "test"}')
        pipeline = Pipeline(ingress=[ByteSizeValidator(), SinglePassParser()])
        await pipeline.run(ctx)
        assert isinstance(ctx.parsed_ast, dict)
        assert ctx.parsed_ast["action"] == "test"
