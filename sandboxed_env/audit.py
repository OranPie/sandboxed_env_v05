from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List
import json
import sys
import urllib.request

from .result import Event

class AuditSink:
    def emit(self, event: Event) -> None:
        raise NotImplementedError

class InMemoryAuditSink(AuditSink):
    def __init__(self):
        self.events: List[Event] = []

    def emit(self, event: Event) -> None:
        self.events.append(event)

class StdoutAuditSink(AuditSink):
    def emit(self, event: Event) -> None:
        sys.__stdout__.write(json.dumps(event.__dict__, ensure_ascii=True) + "\n")
        sys.__stdout__.flush()

class FileAuditSink(AuditSink):
    def __init__(self, path: str):
        self.path = path

    def emit(self, event: Event) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.__dict__, ensure_ascii=True) + "\n")

class WebhookAuditSink(AuditSink):
    def __init__(self, url: str, *, timeout_s: float = 1.0):
        self.url = url
        self.timeout_s = timeout_s

    def emit(self, event: Event) -> None:
        data = json.dumps(event.__dict__, ensure_ascii=True).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=self.timeout_s):
            return None

class OpenTelemetryAuditSink(AuditSink):
    def __init__(self, service_name: str = "sandboxed_env"):
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        except Exception as e:
            raise RuntimeError("opentelemetry is not available") from e
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)
        self.tracer = trace.get_tracer(__name__)

    def emit(self, event: Event) -> None:
        with self.tracer.start_as_current_span("sandbox.event") as span:
            span.set_attribute("event.type", event.type)
            span.set_attribute("event.ts_ms", event.ts_ms)
            for k, v in event.data.items():
                span.set_attribute(f"event.data.{k}", str(v))

@dataclass(frozen=True)
class AuditSinkSpec:
    kind: str
    options: Dict[str, Any]

def audit_sink_specs_to_list(specs: List[AuditSinkSpec]) -> List[Dict[str, Any]]:
    return [asdict(s) for s in specs]

def audit_sink_specs_from_list(items: List[Dict[str, Any]]) -> List[AuditSinkSpec]:
    return [AuditSinkSpec(**d) for d in items]

def build_audit_sinks(specs: List[AuditSinkSpec]) -> List[AuditSink]:
    sinks: List[AuditSink] = []
    for s in specs:
        kind = s.kind
        opts = s.options or {}
        if kind == "memory":
            sinks.append(InMemoryAuditSink())
        elif kind == "stdout":
            sinks.append(StdoutAuditSink())
        elif kind == "file":
            path = opts.get("path")
            if not path:
                raise ValueError("file sink requires path")
            sinks.append(FileAuditSink(path))
        elif kind == "webhook":
            url = opts.get("url")
            if not url:
                raise ValueError("webhook sink requires url")
            sinks.append(WebhookAuditSink(url, timeout_s=float(opts.get("timeout_s", 1.0))))
        elif kind == "otel":
            sinks.append(OpenTelemetryAuditSink(service_name=str(opts.get("service_name", "sandboxed_env"))))
        else:
            raise ValueError(f"unknown audit sink kind: {kind}")
    return sinks

class AuditStream:
    def __init__(self, events: List[Event], sinks: List[AuditSink]):
        self.events = events
        self.sinks = sinks

    def emit(self, event: Event) -> None:
        self.events.append(event)
        for s in self.sinks:
            try:
                s.emit(event)
            except Exception:
                pass
