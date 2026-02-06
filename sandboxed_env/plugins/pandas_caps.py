from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List
import io

from ..capabilities import CapabilitySpec, BudgetSpec
from ..plugin_system import PluginContext


def _to_py(value: Any) -> Any:
    try:
        import numpy as np
        if isinstance(value, np.generic):
            return value.item()
    except Exception:
        pass
    if isinstance(value, float) and (value != value):
        return None
    if isinstance(value, dict):
        return {str(k): _to_py(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_py(v) for v in value]
    return value


def pd_csv_to_records(csv_text: str, *, limit: int = 200) -> List[Dict[str, Any]]:
    import pandas as pd
    df = pd.read_csv(io.StringIO(str(csv_text)))
    if limit is not None:
        df = df.head(int(limit))
    records = df.to_dict(orient="records")
    return _to_py(records)


def pd_describe_from_records(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    import pandas as pd
    df = pd.DataFrame(records)
    desc = df.describe(include="all")
    return _to_py(desc.to_dict())


@dataclass
class PandasCapsPlugin:
    """Register pandas capabilities for CSV parsing and describing records."""
    name: str = "pandas_caps"
    max_calls: int = 50

    def setup(self, ctx: PluginContext) -> None:
        budget = BudgetSpec(max_calls=self.max_calls)
        ctx.cap_specs.extend([
            CapabilitySpec(name="pd_csv_to_records", func_path="sandboxed_env.plugins.pandas_caps:pd_csv_to_records", budget=budget),
            CapabilitySpec(name="pd_describe_from_records", func_path="sandboxed_env.plugins.pandas_caps:pd_describe_from_records", budget=budget),
        ])
