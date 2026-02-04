from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List

from .policy import Policy, default_policy_v14
from .roots import RootSpec

@dataclass(frozen=True)
class PolicyPreset:
    name: str
    policy: Policy
    root_specs: List[RootSpec] = field(default_factory=list)
    description: str = ""

def policy_presets() -> Dict[str, PolicyPreset]:
    base = default_policy_v14()

    pure = PolicyPreset(
        name="pure_compute",
        policy=base,
        description="Pure computation with builtins only.",
    )

    import math
    math_allow = {
        "sin","cos","tan","asin","acos","atan","atan2",
        "sinh","cosh","tanh","asinh","acosh","atanh",
        "exp","log","log10","log2","sqrt","pow",
        "floor","ceil","trunc","fabs","factorial",
        "fmod","modf","frexp","ldexp","hypot",
        "degrees","radians",
        "gamma","lgamma","erf","erfc",
        "pi","e","tau","inf","nan",
        "isfinite","isinf","isnan","copysign",
        "prod","comb","perm",
    }
    math_allow = {k for k in math_allow if hasattr(math, k)}
    consts = {"pi", "e", "tau", "inf", "nan"}
    math_allow_tree = {k: ({"value": True} if k in consts else True) for k in math_allow}
    math_policy = Policy(**{**base.__dict__, "attr_allowlist": {"math": set(math_allow)}})
    math_root = RootSpec(name="math", target="math", allow_tree=math_allow_tree)
    compute_plus_math = PolicyPreset(
        name="compute_plus_math",
        policy=math_policy,
        root_specs=[math_root],
        description="Computation plus a safe math module proxy.",
    )

    json_allow = {"loads", "dumps"}
    json_allow_tree = {k: True for k in json_allow}
    http_policy = Policy(**{**base.__dict__, "attr_allowlist": {"json": set(json_allow)}})
    http_root = RootSpec(name="json", target="json", allow_tree=json_allow_tree)
    compute_plus_http = PolicyPreset(
        name="compute_plus_http",
        policy=http_policy,
        root_specs=[http_root],
        description="Computation plus JSON helpers; intended for HTTP capabilities.",
    )

    return {
        pure.name: pure,
        compute_plus_math.name: compute_plus_math,
        compute_plus_http.name: compute_plus_http,
    }

def get_policy_preset(name: str) -> PolicyPreset:
    presets = policy_presets()
    if name not in presets:
        raise KeyError(f"unknown policy preset: {name}")
    return presets[name]
