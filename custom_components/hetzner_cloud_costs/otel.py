"""OpenTelemetry tracing: spans exported as JSONL to a local file for live debugging.

No collector/network exporter - ponytail: this integration runs on one HA
instance, a file you can `tail -f` is enough. Upgrade to OTLP export if a
real collector shows up.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from .const import DOMAIN

tracer = trace.get_tracer(DOMAIN)

_initialized = False


def ensure_tracer_provider(traces_path: str) -> None:
    """Set the global tracer provider once, writing spans to `traces_path` as JSONL."""
    global _initialized
    if _initialized:
        return
    resource = Resource.create({"service.name": DOMAIN})
    provider = TracerProvider(resource=resource)
    exporter = ConsoleSpanExporter(
        out=open(traces_path, "a", encoding="utf-8"),
        formatter=lambda span: span.to_json(indent=None) + "\n",
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _initialized = True


def span_id_hex(span: trace.Span) -> str:
    return format(span.get_span_context().span_id, "016x")
