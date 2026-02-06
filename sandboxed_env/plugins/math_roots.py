from __future__ import annotations
from dataclasses import dataclass

from ..plugin_system import PluginContext
from ..roots import RootSpec

@dataclass
class MathRootsPlugin:
    """Expose a safe math root with configurable allow-list."""
    name: str = "math_roots"
    allow_sin: bool = True
    allow_cos: bool = True
    allow_pi: bool = True

    def setup(self, ctx: PluginContext) -> None:
        allow: dict[str, object] = {}
        if self.allow_sin:
            allow["sin"] = True
        if self.allow_cos:
            allow["cos"] = True
        if self.allow_pi:
            allow["pi"] = {"value": True}
        if not allow:
            return
        ctx.root_specs.append(RootSpec(name="math", target="math", allow_tree=allow))
