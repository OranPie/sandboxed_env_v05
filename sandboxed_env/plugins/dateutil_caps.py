from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from ..capabilities import CapabilitySpec, BudgetSpec
from ..plugin_system import PluginContext


def parse_datetime(text: str, *, default_tz: Optional[str] = None) -> str:
    from dateutil import parser
    dt = parser.parse(str(text))
    if default_tz and dt.tzinfo is None:
        from dateutil import tz
        dt = dt.replace(tzinfo=tz.gettz(default_tz))
    return dt.isoformat()


def parse_date(text: str) -> str:
    from dateutil import parser
    dt = parser.parse(str(text))
    return dt.date().isoformat()


@dataclass
class DateutilCapsPlugin:
    """Register dateutil parsing capabilities."""
    name: str = "dateutil_caps"
    max_calls: int = 100

    def setup(self, ctx: PluginContext) -> None:
        budget = BudgetSpec(max_calls=self.max_calls)
        ctx.cap_specs.extend([
            CapabilitySpec(name="parse_datetime", func_path="sandboxed_env.plugins.dateutil_caps:parse_datetime", budget=budget),
            CapabilitySpec(name="parse_date", func_path="sandboxed_env.plugins.dateutil_caps:parse_date", budget=budget),
        ])
