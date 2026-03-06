"""Tests for the Telemetry/Observability hooks.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/pipeline/telemetry.py exists.
"""

from __future__ import annotations

import json
import sys
from io import StringIO

import pytest

from argent.pipeline.context import AgentContext
from argent.pipeline.pipeline import Pipeline
from argent.pipeline.telemetry import Telemetry


async def _noop(ctx: AgentContext) -> None:
    """Async no-op middleware for use in tests that only need a placeholder."""


class TestTelemetryInstantiation:
    """Tests for Telemetry construction."""

    def test_telemetry_is_constructable(self) -> None:
        """Telemetry can be instantiated with no arguments."""
        tel = Telemetry()
        assert isinstance(tel, Telemetry)

    def test_telemetry_has_replace_handlers(self) -> None:
        """Telemetry exposes replace_handlers()."""
        tel = Telemetry()
        assert callable(tel.replace_handlers)

    def test_telemetry_has_add_handler(self) -> None:
        """Telemetry exposes add_handler()."""
        tel = Telemetry()
        assert callable(tel.add_handler)


class TestTelemetryEventShape:
    """Tests that emitted events have the required fields."""

    async def test_event_contains_stage(self) -> None:
        """Each event dict contains a 'stage' key."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.replace_handlers(events.append)

        pipeline = Pipeline(ingress=[_noop], telemetry=tel)
        await pipeline.run(AgentContext(raw_payload=b"data"))

        assert all("stage" in e for e in events)

    async def test_event_contains_timestamp_ms(self) -> None:
        """Each event dict contains a 'timestamp_ms' key."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.replace_handlers(events.append)

        pipeline = Pipeline(ingress=[_noop], telemetry=tel)
        await pipeline.run(AgentContext(raw_payload=b"data"))

        assert all("timestamp_ms" in e for e in events)

    async def test_event_contains_duration_ms(self) -> None:
        """End events contain a 'duration_ms' key."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.replace_handlers(events.append)

        pipeline = Pipeline(ingress=[_noop], telemetry=tel)
        await pipeline.run(AgentContext(raw_payload=b"data"))

        end_events = [e for e in events if e.get("event") == "stage_end"]
        assert all("duration_ms" in e for e in end_events)

    async def test_event_contains_context_state(self) -> None:
        """Each event includes a 'context_state' snapshot."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.replace_handlers(events.append)

        pipeline = Pipeline(ingress=[_noop], telemetry=tel)
        await pipeline.run(AgentContext(raw_payload=b"data"))

        assert all("context_state" in e for e in events)

    async def test_event_types_are_stage_start_and_stage_end(self) -> None:
        """Events are labelled 'stage_start' and 'stage_end'."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.replace_handlers(events.append)

        pipeline = Pipeline(ingress=[_noop], telemetry=tel)
        await pipeline.run(AgentContext(raw_payload=b"data"))

        event_types = {e.get("event") for e in events}
        assert event_types == {"stage_start", "stage_end"}


class TestTelemetryEventCount:
    """Tests that the correct number of events are emitted."""

    async def test_four_stages_emit_eight_events(self) -> None:
        """Four non-empty stages produce 8 events (start+end per stage)."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.replace_handlers(events.append)

        pipeline = Pipeline(
            ingress=[_noop],
            pre_execution=[_noop],
            execution=[_noop],
            egress=[_noop],
            telemetry=tel,
        )
        await pipeline.run(AgentContext(raw_payload=b"data"))
        assert len(events) == 8

    async def test_empty_stages_still_emit_events(self) -> None:
        """Empty pipeline stages still emit start+end events (pipeline ran)."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.replace_handlers(events.append)

        pipeline = Pipeline(telemetry=tel)
        await pipeline.run(AgentContext(raw_payload=b"data"))
        # 4 stages x 2 events each
        assert len(events) == 8

    async def test_single_stage_emits_two_events(self) -> None:
        """One active stage with telemetry produces exactly 2 events (start+end)."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.replace_handlers(events.append)

        pipeline = Pipeline(ingress=[_noop], telemetry=tel)
        await pipeline.run(AgentContext(raw_payload=b"data"))
        ingress_events = [e for e in events if e.get("stage") == "ingress"]
        assert len(ingress_events) == 2


class TestTelemetryHandlers:
    """Tests for custom handler registration and default behaviour."""

    async def test_replace_handlers_replaces_default(self) -> None:
        """replace_handlers() replaces the built-in stderr handler."""
        received: list[dict[str, object]] = []
        tel = Telemetry()
        tel.replace_handlers(received.append)

        pipeline = Pipeline(ingress=[_noop], telemetry=tel)
        await pipeline.run(AgentContext(raw_payload=b"data"))

        # 4 stages x 2 events each (pipeline always iterates all 4 stages)
        assert len(received) == 8

    async def test_add_handler_keeps_existing_handlers(self) -> None:
        """add_handler() appends without removing existing handlers."""
        received_a: list[dict[str, object]] = []
        received_b: list[dict[str, object]] = []

        tel = Telemetry()
        tel.replace_handlers(received_a.append)
        tel.add_handler(received_b.append)

        pipeline = Pipeline(ingress=[_noop], telemetry=tel)
        await pipeline.run(AgentContext(raw_payload=b"data"))

        assert received_a == received_b
        # 4 stages x 2 events each (pipeline always iterates all 4 stages)
        assert len(received_a) == 8

    async def test_default_handler_writes_json_to_stderr(self) -> None:
        """Default handler writes valid JSON lines to stderr."""
        tel = Telemetry()
        pipeline = Pipeline(ingress=[_noop], telemetry=tel)

        buf = StringIO()
        old_stderr = sys.stderr
        sys.stderr = buf
        try:
            await pipeline.run(AgentContext(raw_payload=b"data"))
        finally:
            sys.stderr = old_stderr

        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        # 4 stages x 2 events each (pipeline always iterates all 4 stages)
        assert len(lines) == 8
        for line in lines:
            parsed = json.loads(line)  # must not raise
            assert isinstance(parsed, dict)

    async def test_telemetry_does_not_crash_on_handler_error(self) -> None:
        """If a custom handler raises, the pipeline still completes."""

        def bad_handler(event: dict[str, object]) -> None:
            raise RuntimeError("handler exploded")

        tel = Telemetry()
        tel.replace_handlers(bad_handler)

        pipeline = Pipeline(ingress=[_noop], telemetry=tel)
        ctx = AgentContext(raw_payload=b"data")
        # Must not raise; telemetry errors are non-fatal
        result = await pipeline.run(ctx)
        assert result is ctx

    async def test_handler_error_produces_diagnostic_on_stderr(self) -> None:
        """When a handler raises, a diagnostic line is written to stderr."""

        def bad_handler(event: dict[str, object]) -> None:
            raise RuntimeError("handler exploded")

        tel = Telemetry()
        tel.replace_handlers(bad_handler)

        pipeline = Pipeline(ingress=[_noop], telemetry=tel)

        buf = StringIO()
        old_stderr = sys.stderr
        sys.stderr = buf
        try:
            await pipeline.run(AgentContext(raw_payload=b"data"))
        finally:
            sys.stderr = old_stderr

        diagnostic = buf.getvalue()
        assert "[argent.telemetry]" in diagnostic
        assert "handler exploded" in diagnostic

    async def test_pipeline_without_telemetry_still_works(self) -> None:
        """Pipeline constructed without a Telemetry instance runs normally."""
        ctx = AgentContext(raw_payload=b"data")
        pipeline = Pipeline(ingress=[_noop])
        result = await pipeline.run(ctx)
        assert result is ctx

    async def test_telemetry_emits_end_event_even_when_middleware_raises(self) -> None:
        """stage_end is always emitted even if middleware raises (try/finally guarantee)."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.replace_handlers(events.append)

        async def exploding(ctx: AgentContext) -> None:
            raise RuntimeError("middleware failure")

        pipeline = Pipeline(ingress=[exploding], telemetry=tel)
        with pytest.raises(RuntimeError):
            await pipeline.run(AgentContext(raw_payload=b"data"))

        ingress_events = [e for e in events if e.get("stage") == "ingress"]
        event_types = {e.get("event") for e in ingress_events}
        assert "stage_start" in event_types
        assert "stage_end" in event_types
