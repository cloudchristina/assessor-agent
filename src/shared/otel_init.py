"""Manual OpenTelemetry SDK initialisation for Lambdas that emit Strands spans.

**Why manual instead of ADOT auto-instrumentation:** the AWS_LAMBDA_EXEC_WRAPPER
approach (`/opt/otel-instrument`) fails at init time because the Lambda zip
ships opentelemetry-sdk 1.41 (transitive dep from `strands-agents`) while the
ADOT layer ships 1.32. The version mismatch breaks the wrapper's exporter
loader. Workaround: skip the wrapper, configure the SDK ourselves using the
zip's newer in-process OTel libraries, and send spans via OTLP HTTP to the
ADOT collector sidecar (still attached via the layer, still listening on
localhost:4318).

**Usage:** import this module BEFORE importing `strands` so the global
TracerProvider is set before Strands' `get_tracer_provider()` reads it.

    import src.shared.otel_init  # noqa: F401  -- must be first
    from strands import Agent
    ...

If the OTLP exporter cannot be imported (e.g. running locally without the
extra wheel), this module is a no-op so unit tests don't break.
"""
from __future__ import annotations
import os

try:
    from opentelemetry import trace as _trace_api
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
except ImportError:
    # OTLP exporter not installed (e.g. local pytest env without lambda
    # requirements). Strands' get_tracer_provider() will return the no-op
    # default, which is fine for unit tests.
    _trace_api = None  # type: ignore[assignment]


_provider = None  # module-level so flush_otel() can reach it


def _init() -> None:
    global _provider
    if _trace_api is None:
        return
    # Idempotency guard — Lambda may import the handler module multiple times
    # in some warm-start paths.
    existing = _trace_api.get_tracer_provider()
    if isinstance(existing, TracerProvider):
        _provider = existing
        return

    endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://localhost:4318/v1/traces",
    )
    service_name = (
        os.environ.get("OTEL_SERVICE_NAME")
        or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        or "agent"
    )

    resource = Resource.create({
        "service.name": service_name,
        "service.namespace": "assessor-agent",
        "deployment.environment": os.environ.get("ENVIRONMENT", "dev"),
    })
    # SimpleSpanProcessor (NOT Batch) — Lambda freezes the runtime between
    # invocations, so async batching loses spans. Simple is synchronous and
    # works correctly with Lambda's lifecycle.
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    _trace_api.set_tracer_provider(provider)
    _provider = provider


def flush_otel() -> None:
    """Best-effort flush. SimpleSpanProcessor exports synchronously so this is
    usually a no-op, but force_flush is cheap insurance and matters if a
    BatchSpanProcessor is ever swapped in. Call before Lambda handler returns."""
    if _provider is not None and hasattr(_provider, "force_flush"):
        try:
            _provider.force_flush(timeout_millis=5000)
        except Exception:  # pragma: no cover - defensive
            pass


_init()
