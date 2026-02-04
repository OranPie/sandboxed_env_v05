from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Set, Optional
import importlib

from .proxies import SafeModuleProxy

@dataclass(frozen=True)
class RootSpec:
    """Specification for a root object injected into sandbox globals.

    This is especially useful for spawn mode, where worker must recreate roots.
    - name: variable name inside sandbox, e.g. "math"
    - target: module name ("math") or dotted path ("pkg.mod:obj")
    - allow_tree: allowlist for SafeModuleProxy
    """
    name: str
    target: str
    allow_tree: Dict[str, Any]

    def attr_allow(self) -> Set[str]:
        return set(self.allow_tree.keys())

def load_root_target(target: str) -> Any:
    if ":" in target:
        mod, _, attr = target.partition(":")
        m = importlib.import_module(mod)
        return getattr(m, attr)
    # module name
    return importlib.import_module(target)

def build_roots_from_specs(specs: list[RootSpec]) -> tuple[Dict[str, Any], Dict[str, Set[str]]]:
    """Return (roots_dict, attr_allowlist_for_policy)."""
    roots: Dict[str, Any] = {}
    attr_allowlist: Dict[str, Set[str]] = {}
    for s in specs:
        tgt = load_root_target(s.target)
        roots[s.name] = SafeModuleProxy(tgt, s.allow_tree, name=s.name)
        attr_allowlist[s.name] = s.attr_allow()
    return roots, attr_allowlist
