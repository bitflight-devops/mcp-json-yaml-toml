"""Tests for OpenTelemetry integration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from mcp_json_yaml_toml.backends.base import FormatType
from mcp_json_yaml_toml.telemetry import _TRACER_NAME, get_tracer

if TYPE_CHECKING:
    from pathlib import Path


def _make_test_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Create a TracerProvider with an InMemorySpanExporter for testing."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


class TestGetTracer:
    """Tests for the get_tracer helper."""

    def test_get_tracer_when_called_then_returns_tracer_object(self) -> None:
        """get_tracer returns a tracer instance (no-op when no SDK configured)."""
        tracer = get_tracer()
        assert tracer is not None
        # Should be a proxy tracer or real tracer -- either way it has start_as_current_span
        assert hasattr(tracer, "start_as_current_span")

    def test_get_tracer_when_sdk_configured_then_records_spans(self) -> None:
        """When SDK is configured, get_tracer returns a tracer that records spans."""
        provider, exporter = _make_test_provider()
        tracer = provider.get_tracer(_TRACER_NAME)

        with tracer.start_as_current_span("test.span") as span:
            span.set_attribute("test.key", "test_value")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test.span"
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs["test.key"] == "test_value"
        exporter.clear()


class TestYqExecuteSpan:
    """Tests for custom yq.execute span emission."""

    @pytest.fixture
    def otel_capture(self) -> tuple[TracerProvider, InMemorySpanExporter]:
        """Create a test provider and monkeypatch get_tracer to use it."""
        return _make_test_provider()

    def test_execute_yq_when_json_query_then_emits_span(
        self, otel_capture: tuple[TracerProvider, InMemorySpanExporter], tmp_path: Path
    ) -> None:
        """execute_yq emits a 'yq.execute' span with expected attributes."""
        from mcp_json_yaml_toml.backends.yq import execute_yq

        provider, exporter = otel_capture
        test_tracer = provider.get_tracer(_TRACER_NAME)

        # Create a simple JSON input file
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps({"name": "test", "value": 42}))

        # Monkeypatch get_tracer in the backends.yq module
        with patch(
            "mcp_json_yaml_toml.backends.yq.get_tracer", return_value=test_tracer
        ):
            result = execute_yq(
                expression=".",
                input_file=str(test_file),
                input_format=FormatType.JSON,
                output_format=FormatType.JSON,
            )
        assert result.returncode == 0

        # Verify span was emitted
        spans = exporter.get_finished_spans()
        yq_spans = [s for s in spans if s.name == "yq.execute"]
        assert len(yq_spans) == 1

        span = yq_spans[0]
        attrs = span.attributes
        assert attrs is not None
        assert attrs["yq.expression"] == "."
        assert attrs["yq.input_format"] == "json"
        assert attrs["yq.output_format"] == "json"
        assert attrs["yq.returncode"] == 0
        exporter.clear()

    def test_execute_yq_when_yaml_input_then_records_correct_format(
        self, otel_capture: tuple[TracerProvider, InMemorySpanExporter], tmp_path: Path
    ) -> None:
        """execute_yq records correct format attributes for YAML input."""
        from mcp_json_yaml_toml.backends.yq import execute_yq

        provider, exporter = otel_capture
        test_tracer = provider.get_tracer(_TRACER_NAME)

        test_file = tmp_path / "test.yaml"
        test_file.write_text("name: hello\ncount: 5\n")

        with patch(
            "mcp_json_yaml_toml.backends.yq.get_tracer", return_value=test_tracer
        ):
            result = execute_yq(
                expression=".name",
                input_file=str(test_file),
                input_format=FormatType.YAML,
                output_format=FormatType.JSON,
            )
        assert result.returncode == 0

        spans = exporter.get_finished_spans()
        yq_spans = [s for s in spans if s.name == "yq.execute"]
        assert len(yq_spans) == 1
        attrs = yq_spans[0].attributes
        assert attrs is not None
        assert attrs["yq.input_format"] == "yaml"
        exporter.clear()

    def test_execute_yq_when_error_then_still_emits_span(
        self, otel_capture: tuple[TracerProvider, InMemorySpanExporter], tmp_path: Path
    ) -> None:
        """execute_yq still emits span even when yq returns an error."""
        from mcp_json_yaml_toml.backends.base import YQExecutionError
        from mcp_json_yaml_toml.backends.yq import execute_yq

        provider, exporter = otel_capture
        test_tracer = provider.get_tracer(_TRACER_NAME)

        # Create an invalid file for the format
        test_file = tmp_path / "bad.json"
        test_file.write_text("not valid json {{{")

        with (
            patch(
                "mcp_json_yaml_toml.backends.yq.get_tracer", return_value=test_tracer
            ),
            pytest.raises(YQExecutionError),
        ):
            execute_yq(
                expression=".missing",
                input_file=str(test_file),
                input_format=FormatType.JSON,
                output_format=FormatType.JSON,
            )

        # Span should still be recorded (returncode set before error raise)
        spans = exporter.get_finished_spans()
        yq_spans = [s for s in spans if s.name == "yq.execute"]
        assert len(yq_spans) == 1
        attrs = yq_spans[0].attributes
        assert attrs is not None
        assert attrs["yq.expression"] == ".missing"
        exporter.clear()
