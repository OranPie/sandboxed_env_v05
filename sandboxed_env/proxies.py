from __future__ import annotations
from typing import Any, Dict
from .freeze import deep_freeze

class SafeModuleProxy:
    """Read-only proxy that only exposes allowlisted attributes.

    allow-tree example:
      {"sin": True, "cos": True, "sub": {"x": True}, "pi": {"value": True}}
    """
    def __init__(self, target: Any, allow: Dict[str, Any], name: str = "root"):
        self._t = target
        self._allow = allow
        self._name = name

    def __getattr__(self, item: str) -> Any:
        if item not in self._allow:
            raise AttributeError(f"{self._name}.{item} is not allowed")
        spec = self._allow[item]
        v = getattr(self._t, item)
        if isinstance(spec, dict):
            if spec.get("value"):
                return deep_freeze(v)
            return SafeModuleProxy(v, spec, name=f"{self._name}.{item}")
        if not callable(v):
            raise AttributeError(f"{self._name}.{item} is not callable")
        def _wrapped(*args, **kwargs):
            return deep_freeze(v(*args, **kwargs))
        return _wrapped
