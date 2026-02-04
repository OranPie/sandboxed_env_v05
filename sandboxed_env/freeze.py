from __future__ import annotations
from typing import Any

class FrozenDict(dict):
    def _ro(self, *a, **k):
        raise TypeError("FrozenDict is read-only")
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _ro

def deep_freeze(x: Any, *, max_depth: int = 30, _d: int = 0) -> Any:
    """Make inputs deeply immutable (best-effort), preventing external side effects."""
    if _d > max_depth:
        return "<frozen:depth_limit>"
    if x is None or isinstance(x, (bool, int, float, str)):
        return x
    if isinstance(x, bytes):
        return x.decode("utf-8", errors="replace")
    if isinstance(x, dict):
        return FrozenDict({deep_freeze(k, _d=_d+1): deep_freeze(v, _d=_d+1) for k, v in x.items()})
    if isinstance(x, (list, tuple)):
        return tuple(deep_freeze(i, _d=_d+1) for i in x)
    if isinstance(x, set):
        return frozenset(deep_freeze(i, _d=_d+1) for i in x)
    return f"<frozen:{type(x).__name__}>"
