from __future__ import annotations
from dataclasses import dataclass

from ..capabilities import CapabilitySpec, BudgetSpec
from ..plugin_system import PluginContext


def upper(text: str) -> str:
    return str(text).upper()


def lower(text: str) -> str:
    return str(text).lower()


def count_words(text: str) -> int:
    return len(str(text).split())


@dataclass
class TextCapsPlugin:
    """Register basic text capabilities: upper, lower, count_words."""
    name: str = "text_caps"
    max_calls: int = 100

    def setup(self, ctx: PluginContext) -> None:
        budget = BudgetSpec(max_calls=self.max_calls)
        ctx.cap_specs.extend([
            CapabilitySpec(name="upper", func_path="sandboxed_env.plugins.text_caps:upper", budget=budget),
            CapabilitySpec(name="lower", func_path="sandboxed_env.plugins.text_caps:lower", budget=budget),
            CapabilitySpec(name="count_words", func_path="sandboxed_env.plugins.text_caps:count_words", budget=budget),
        ])
