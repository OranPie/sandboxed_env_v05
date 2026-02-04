from __future__ import annotations
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .policy import Policy, DeterminismConfig, OSSandboxConfig
from .capabilities import CapabilitySpec, BudgetSpec
from .roots import RootSpec

def _listify(x: Optional[set]) -> List[Any]:
    return sorted(list(x or []))

def policy_to_dict(p: Policy) -> Dict[str, Any]:
    d = dict(p.__dict__)
    d["builtin_allowlist"] = _listify(p.builtin_allowlist)
    d["call_name_allowlist"] = _listify(p.call_name_allowlist)
    d["attr_allowlist"] = {k: _listify(v) for k, v in (p.attr_allowlist or {}).items()}
    d["loop_iter_allowlist"] = _listify(p.loop_iter_allowlist)
    d["allow_dunder_names"] = _listify(p.allow_dunder_names)
    if p.determinism:
        d["determinism"] = asdict(p.determinism)
    else:
        d["determinism"] = None
    d["input_schema"] = p.input_schema
    d["output_schema"] = p.output_schema
    d["os_sandbox"] = asdict(p.os_sandbox) if p.os_sandbox else None
    return d

def policy_from_dict(d: Dict[str, Any]) -> Policy:
    det = d.get("determinism")
    det_obj = DeterminismConfig(**det) if det else None
    osb = d.get("os_sandbox")
    osb_obj = OSSandboxConfig(**osb) if osb else None
    return Policy(
        builtin_allowlist=set(d.get("builtin_allowlist") or []),
        call_name_allowlist=set(d.get("call_name_allowlist") or []),
        attr_allowlist={k: set(v) for k, v in (d.get("attr_allowlist") or {}).items()},
        allow_def=bool(d.get("allow_def", False)),
        allow_lambda=bool(d.get("allow_lambda", False)),
        allow_class=bool(d.get("allow_class", False)),
        allow_try=bool(d.get("allow_try", False)),
        allow_with=bool(d.get("allow_with", False)),
        allow_loops=bool(d.get("allow_loops", True)),
        allow_comprehension=bool(d.get("allow_comprehension", True)),
        allow_subscript=bool(d.get("allow_subscript", True)),
        allow_dunder_names=set(d.get("allow_dunder_names") or ["__result__", "__events__", "__stats__"]),
        restrict_loop_iterables=bool(d.get("restrict_loop_iterables", True)),
        loop_iter_allowlist=set(d.get("loop_iter_allowlist") or ["range", "list", "tuple"]),
        allow_loop_iter_literals=bool(d.get("allow_loop_iter_literals", True)),
        allow_loop_iter_names=bool(d.get("allow_loop_iter_names", True)),
        max_ast_nodes=int(d.get("max_ast_nodes", 7000)),
        max_loop_nesting=int(d.get("max_loop_nesting", 3)),
        max_comp_nesting=int(d.get("max_comp_nesting", 3)),
        max_literal_elems=int(d.get("max_literal_elems", 100_000)),
        max_const_alloc_elems=int(d.get("max_const_alloc_elems", 1_000_000)),
        timeout_ms=int(d.get("timeout_ms", 800)),
        max_steps=int(d.get("max_steps", 120_000)),
        max_stdout_bytes=int(d.get("max_stdout_bytes", 32_000)),
        max_stderr_bytes=int(d.get("max_stderr_bytes", 32_000)),
        max_memory_mb=int(d.get("max_memory_mb", 256)),
        max_cpu_seconds=int(d.get("max_cpu_seconds", 1)),
        max_open_files=int(d.get("max_open_files", 32)),
        max_recursion=int(d.get("max_recursion", 300)),
        determinism=det_obj,
        input_schema=d.get("input_schema"),
        output_schema=d.get("output_schema"),
        os_sandbox=osb_obj,
    )

def cap_specs_to_list(specs: List[CapabilitySpec]) -> List[Dict[str, Any]]:
    return [asdict(s) for s in specs]

def cap_specs_from_list(items: List[Dict[str, Any]]) -> List[CapabilitySpec]:
    out: List[CapabilitySpec] = []
    for d in items:
        bd = d.get("budget")
        if bd is not None and not isinstance(bd, BudgetSpec):
            d = {**d, "budget": BudgetSpec(**bd)}
        out.append(CapabilitySpec(**d))
    return out

def root_specs_to_list(specs: List[RootSpec]) -> List[Dict[str, Any]]:
    return [asdict(s) for s in specs]

def root_specs_from_list(items: List[Dict[str, Any]]) -> List[RootSpec]:
    return [RootSpec(**d) for d in items]
