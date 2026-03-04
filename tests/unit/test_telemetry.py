"""Tests for the Telemetry/Observability hooks.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/pipeline/telemetry.py exists.
"""

from __future__ import annotations

import json
import sys
from io import StringIO

from argent.pipeline.context import AgentContext
from argent.pipeline.pipeline import Pipeline
from argent.pipeline.telemetry import Telemetry


class TestTelemetryInstantiation:
    """Tests for Telemetry construction."""

    def test_telemetry_is_constructable(self) -> None:
        """Telemetry can be instantiated with no arguments."""
        tel = Telemetry()
        assert tel is not None

    def test_telemetry_has_register_handler(self) -> None:
        """Telemetry exposes register_handler()."""
        tel = Telemetry()
        assert callable(tel.register_handler)


class TestTelemetryEventShape:
    """Tests that emitted events have the required fields."""

    def test_event_contains_stage(self) -> None:
        """Each event dict contains a 'stage' key."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.register_handler(events.append)

        pipeline = Pipeline(ingress=[lambda c: None], telemetry=tel)
        pipeline.run(AgentContext(raw_payload=b"data"))

        assert all("stage" in e for e in events)

    def test_event_contains_timestamp_ms(self) -> None:
        """Each event dict contains a 'timestamp_ms' key."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.register_handler(events.append)

        pipeline = Pipeline(ingress=[lambda c: None], telemetry=tel)
        pipeline.run(AgentContext(raw_payload=b"data"))

        assert all("timestamp_ms" in e for e in events)

    def test_event_contains_duration_ms(self) -> None:
        """End events contain a 'duration_ms' key."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.register_handler(events.append)

        pipeline = Pipeline(ingress=[lambda c: None], telemetry=tel)
        pipeline.run(AgentContext(raw_payload=b"data"))

        end_events = [e for e in events if e.get("event") == "stage_end"]
        assert all("duration_ms" in e for e in end_events)

    def test_event_contains_context_state(self) -> None:
        """Each event includes a 'context_state' snapshot."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.register_handler(events.append)

        pipeline = Pipeline(ingress=[lambda c: None], telemetry=tel)
        pipeline.run(AgentContext(raw_payload=b"data"))

        assert all("context_state" in e for e in events)

    def test_event_types_are_stage_start_and_stage_end(self) -> None:
        """Events are labelled 'stage_start' and 'stage_end'."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.register_handler(events.append)

        pipeline = Pipeline(ingress=[lambda c: None], telemetry=tel)
        pipeline.run(AgentContext(raw_payload=b"data"))

        event_types = {e.get("event") for e in events}
        assert event_types == {"stage_start", "stage_end"}


class TestTelemetryEventCount:
    """Tests that the correct number of events are emitted."""

    def test_four_stages_emit_eight_events(self) -> None:
        """Four non-empty stages produce 8 events (start+end per stage)."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.register_handler(events.append)

        pipeline = Pipeline(
            ingress=[lambda c: None],
            pre_execution=[lambda c: None],
            execution=[lambda c: None],
            egress=[lambda c: None],
            telemetry=tel,
        )
        pipeline.run(AgentContext(raw_payload=b"data"))
        assert len(events) == 8

    def test_empty_stages_still_emit_events(self) -> None:
        """Empty pipeline stages still emit start+end events (pipeline ran)."""
        events: list[dict[str, object]] = []
        tel = Telemetry()
        tel.register_handler(events.append)

        pipeline = Pipeline(telemetry=tel)
        pipeline.run(AgentContext(raw_payload=b"data"))
        # 4 stages x 2 events each
        assert len(events) == 8


class TestTelemetryHandlers:
    """Tests for custom handler registration and default behaviour."""

    def test_custom_handler_receives_events(self) -> None:
        """A registered custom handler is called for every event."""
        received: list[dict[str, object]] = []
        tel = Telemetry()
        tel.register_handler(received.append)

        pipeline = Pipeline(ingress=[lambda c: None], telemetry=tel)
        pipeline.run(AgentContext(raw_payload=b"data"))

        assert len(received) > 0

    def test_multiple_handlers_all_called(self) -> None:
        """All registered handlers receive every event."""
        received_a: list[dict[str, object]] = []
        received_b: list[dict[str, object]] = []

        tel = Telemetry()
        tel.register_handler(received_a.append)
        tel.register_handler(received_b.append)

        pipeline = Pipeline(ingress=[lambda c: None], telemetry=tel)
        pipeline.run(AgentContext(raw_payload=b"data"))

        assert received_a == received_b

    def test_default_handler_writes_json_to_stderr(self) -> None:
        """Default handler writes valid JSON lines to stderr."""
        tel = Telemetry()
        pipeline = Pipeline(ingress=[lambda c: None], telemetry=tel)

        buf = StringIO()
        old_stderr = sys.stderr
        sys.stderr = buf
        try:
            pipeline.run(AgentContext(raw_payload=b"data"))
        finally:
            sys.stderr = old_stderr

        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        assert len(lines) > 0
        for line in lines:
            parsed = json.loads(line)  # must not raise
            assert isinstance(parsed, dict)

    def test_telemetry_does_not_crash_on_handler_error(self) -> None:
        """If a custom handler raises, the pipeline still completes."""

        def bad_handler(event: dict[str, object]) -> None:
            raise RuntimeError("handler exploded")

        tel = Telemetry()
        tel.register_handler(bad_handler)

        pipeline = Pipeline(ingress=[lambda c: None], telemetry=tel)
        ctx = AgentContext(raw_payload=b"data")
        # Must not raise; telemetry errors are non-fatal
        result = pipeline.run(ctx)
        assert result is ctx

    def test_pipeline_without_telemetry_still_works(self) -> None:
        """Pipeline constructed without a Telemetry instance runs normally."""
        ctx = AgentContext(raw_payload=b"data")
        pipeline = Pipeline(ingress=[lambda c: None])
        result = pipeline.run(ctx)
        assert result is ctx
