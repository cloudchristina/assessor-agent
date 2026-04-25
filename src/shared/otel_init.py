"""Strands-native OpenTelemetry setup for Lambdas that emit Strands spans.

Uses Strands' built-in `StrandsTelemetry` helper instead of hand-rolling the
OTel SDK config. Reference:
  https://strandsagents.com/docs/user-guide/observability-evaluation/traces/

Why this module exists at all:
  Strands' `setup_otlp_exporter()` defaults to a BatchSpanProcessor — which
  loses spans in Lambda because the runtime freezes between invocations.
  We use Strands' provider + propagator setup but swap in SimpleSpanProcessor
  for synchronous export, plus expose `flush_otel()` as defensive insurance.

Usage:
  Import this module BEFORE importing strands so the global TracerProvider
  is set before Strands' `get_tracer_provider()` reads it.

      import src.shared.otel_init  # noqa: F401  -- must be first
      from strands import Agent

If the OTLP exporter cannot be imported (e.g. local pytest env without lambda
requirements), this module is a no-op so unit tests still pass.

Env vars honoured:
  OTEL_SERVICE_NAME            (read by Strands' get_otel_resource)
  OTEL_EXPORTER_OTLP_ENDPOINT  (read by OTLPSpanExporter)
"""
from __future__ import annotations
import logging

_log = logging.getLogger("otel_init")
_log.setLevel(logging.INFO)
_provider = None  # exposed for flush_otel()

try:
    from strands.telemetry import StrandsTelemetry
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    _import_error: str | None = None
except ImportError as exc:
    StrandsTelemetry = None  # type: ignore[assignment]
    _import_error = str(exc)


def _init() -> None:
    global _provider
    if StrandsTelemetry is None:
        _log.warning("OTEL_INIT_SKIPPED: import failed: %s", _import_error)
        return

    # StrandsTelemetry() creates the global TracerProvider with a proper
    # Resource (service.name, service.version, etc.) and W3C / TraceContext
    # propagators. We then attach a SimpleSpanProcessor + OTLPSpanExporter
    # ourselves rather than calling .setup_otlp_exporter() (which uses Batch).
    telemetry = StrandsTelemetry()
    telemetry.tracer_provider.add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter())
    )
    _provider = telemetry.tracer_provider
    _log.info("OTEL_INIT_OK: provider=StrandsTelemetry exporter=OTLPSpanExporter")


def flush_otel() -> None:
    """Best-effort flush. SimpleSpanProcessor exports synchronously so this is
    usually a no-op, but `force_flush` is cheap insurance and matters if a
    BatchSpanProcessor is ever swapped in. Call before Lambda handler returns."""
    if _provider is not None and hasattr(_provider, "force_flush"):
        try:
            _provider.force_flush(timeout_millis=5000)
        except Exception:  # pragma: no cover - defensive
            pass


_init()
