from __future__ import annotations
from typing import Any, Dict, List, Optional, Set
import itertools
import math

def to_safe_json(
    x: Any,
    *,
    max_depth: int = 10,
    max_items: int = 2000,
    max_str: int = 10000,
    max_bytes: Optional[int] = None,
    float_format: Optional[str] = None,
    _d: int = 0,
    _count: List[int] | None = None,
    _seen: Set[int] | None = None,
    _bytes: List[int] | None = None,
) -> Any:
    """Convert Python objects to JSON-ish safe values with truncation."""
    if _count is None:
        _count = [0]
    if _bytes is None:
        _bytes = [0]
    if _seen is None:
        _seen = set()
    _count[0] += 1
    if _count[0] > max_items:
        return "<truncated:too_many_items>"
    if _d > max_depth:
        return "<truncated:depth_limit>"
    if max_bytes is not None and _bytes[0] > max_bytes:
        return "<truncated:byte_limit>"

    if not isinstance(x, (bool, int, float, str, bytes)) and id(x) in _seen:
        return "<truncated:cycle>"
    if not isinstance(x, (bool, int, float, str, bytes)):
        _seen.add(id(x))

    if x is None or isinstance(x, (bool, int)):
        return x
    if isinstance(x, float):
        if float_format:
            v = 0.0 if (x == 0.0 and math.copysign(1.0, x) < 0.0) else x
            try:
                s = format(v, float_format)
                _bytes[0] += len(s)
                return s
            except Exception:
                return v
        return x
    if isinstance(x, str):
        s = x if len(x) <= max_str else x[:max_str] + "<truncated>"
        _bytes[0] += len(s)
        return s
    if isinstance(x, (list, tuple)):
        return [
            to_safe_json(i, max_depth=max_depth, max_items=max_items, max_str=max_str, max_bytes=max_bytes, float_format=float_format, _d=_d+1, _count=_count, _seen=_seen, _bytes=_bytes)
            for i in x
        ]
    if isinstance(x, dict):
        out: Dict[str, Any] = {}
        for k, v in itertools.islice(x.items(), max_items):
            ks = to_safe_json(k, max_depth=max_depth, max_items=max_items, max_str=max_str, max_bytes=max_bytes, float_format=float_format, _d=_d+1, _count=_count, _seen=_seen, _bytes=_bytes)
            vs = to_safe_json(v, max_depth=max_depth, max_items=max_items, max_str=max_str, max_bytes=max_bytes, float_format=float_format, _d=_d+1, _count=_count, _seen=_seen, _bytes=_bytes)
            out[str(ks)] = vs
        return out
    return f"<opaque:{type(x).__name__}>"

def _safe_size(
    x: Any,
    *,
    max_depth: int = 6,
    max_items: int = 2000,
    max_str: int = 10000,
    _d: int = 0,
    _count: List[int] | None = None,
    _seen: Set[int] | None = None,
) -> int:
    if _count is None:
        _count = [0]
    if _seen is None:
        _seen = set()
    _count[0] += 1
    if _count[0] > max_items:
        return 0
    if _d > max_depth:
        return 0
    if not isinstance(x, (bool, int, float, str, bytes)) and id(x) in _seen:
        return 0
    if not isinstance(x, (bool, int, float, str, bytes)):
        _seen.add(id(x))

    if x is None:
        return 0
    if isinstance(x, (bool, int, float)):
        return 8
    if isinstance(x, str):
        return min(len(x), max_str)
    if isinstance(x, bytes):
        return len(x)
    if isinstance(x, (list, tuple, set, frozenset)):
        return sum(_safe_size(i, max_depth=max_depth, max_items=max_items, max_str=max_str, _d=_d+1, _count=_count, _seen=_seen) for i in itertools.islice(x, max_items))
    if isinstance(x, dict):
        total = 0
        for k, v in itertools.islice(x.items(), max_items):
            total += _safe_size(k, max_depth=max_depth, max_items=max_items, max_str=max_str, _d=_d+1, _count=_count, _seen=_seen)
            total += _safe_size(v, max_depth=max_depth, max_items=max_items, max_str=max_str, _d=_d+1, _count=_count, _seen=_seen)
        return total
    return 256

def approx_bytes(x: Any) -> int:
    """Rough size estimate for capability return budgeting."""
    try:
        return _safe_size(x)
    except Exception:
        return 10_000_000
