from __future__ import annotations
from dataclasses import dataclass

from ..audit import AuditSinkSpec
from ..plugin_system import PluginContext

@dataclass
class AuditFilePlugin:
    """Write audit events to a JSONL file via AuditSinkSpec."""
    path: str
    name: str = "audit_file"

    def setup(self, ctx: PluginContext) -> None:
        ctx.audit_sink_specs.append(AuditSinkSpec(kind="file", options={"path": self.path}))
