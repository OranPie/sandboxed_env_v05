from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List

from ..capabilities import CapabilitySpec, BudgetSpec
from ..plugin_system import PluginContext


def np_sum(values: Iterable[float]) -> float:
    import numpy as np
    return float(np.sum(np.array(list(values), dtype=float)))


def np_mean(values: Iterable[float]) -> float:
    import numpy as np
    return float(np.mean(np.array(list(values), dtype=float)))


def np_dot(a: Iterable[float], b: Iterable[float]) -> float:
    import numpy as np
    a_arr = np.array(list(a), dtype=float)
    b_arr = np.array(list(b), dtype=float)
    return float(np.dot(a_arr, b_arr))


def np_linspace(start: float, stop: float, num: int) -> List[float]:
    import numpy as np
    return np.linspace(float(start), float(stop), int(num)).tolist()


@dataclass
class NumpyCapsPlugin:
    """Register basic numpy capabilities: sum, mean, dot, linspace."""
    name: str = "numpy_caps"
    max_calls: int = 100

    def setup(self, ctx: PluginContext) -> None:
        budget = BudgetSpec(max_calls=self.max_calls)
        ctx.cap_specs.extend([
            CapabilitySpec(name="np_sum", func_path="sandboxed_env.plugins.numpy_caps:np_sum", budget=budget),
            CapabilitySpec(name="np_mean", func_path="sandboxed_env.plugins.numpy_caps:np_mean", budget=budget),
            CapabilitySpec(name="np_dot", func_path="sandboxed_env.plugins.numpy_caps:np_dot", budget=budget),
            CapabilitySpec(name="np_linspace", func_path="sandboxed_env.plugins.numpy_caps:np_linspace", budget=budget),
        ])
