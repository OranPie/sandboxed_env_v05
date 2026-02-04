from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

@dataclass(frozen=True)
class DeterminismConfig:
    seed: int = 0
    fake_time: Optional[float] = None
    time_step: float = 0.0
    float_format: Optional[str] = None

@dataclass(frozen=True)
class OSSandboxConfig:
    seccomp_profile: Optional[str] = None
    seccomp_enforce: bool = False
    no_network: bool = True
    fs_mode: str = "tmp"  # none|tmp|ro
    fs_enforce: bool = False
    fs_chroot: bool = False
    tmp_dir: Optional[str] = None

@dataclass(frozen=True)
class Policy:
    # Builtins exposed inside sandbox globals["__builtins__"]
    builtin_allowlist: Set[str]

    # Direct callable names allowed for Name(...) calls
    call_name_allowlist: Set[str]

    # AST allowlist for root.attr access / calls, e.g. {"math": {"sin","pi"}}
    attr_allowlist: Dict[str, Set[str]] = field(default_factory=dict)

    # Syntax switches
    allow_def: bool = False
    allow_lambda: bool = False
    allow_class: bool = False
    allow_try: bool = False
    allow_with: bool = False
    allow_loops: bool = True
    allow_comprehension: bool = True
    allow_subscript: bool = True

    # Dunder allowlist (for result contract)
    allow_dunder_names: Set[str] = field(default_factory=lambda: {"__result__", "__events__", "__stats__"})

    # Loop iterables
    restrict_loop_iterables: bool = True
    loop_iter_allowlist: Set[str] = field(default_factory=lambda: {"range", "list", "tuple"})
    allow_loop_iter_literals: bool = True
    allow_loop_iter_names: bool = True

    # Complexity limits
    max_ast_nodes: int = 7000
    max_loop_nesting: int = 3
    max_comp_nesting: int = 3
    max_literal_elems: int = 100_000
    max_const_alloc_elems: int = 1_000_000

    # Runtime limits
    timeout_ms: int = 800
    max_steps: int = 120_000

    # Output limits
    max_stdout_bytes: int = 32_000
    max_stderr_bytes: int = 32_000

    # Best-effort OS limits (Linux)
    max_memory_mb: int = 256
    max_cpu_seconds: int = 1
    max_open_files: int = 32
    max_recursion: int = 300

    # Determinism options
    determinism: Optional[DeterminismConfig] = None

    # Type shaping (JSON-schema-like)
    input_schema: Optional[Any] = None
    output_schema: Optional[Any] = None

    # OS sandbox options
    os_sandbox: Optional[OSSandboxConfig] = None

def default_policy_v05() -> Policy:
    safe_builtins = {
        "None","True","False",
        "abs","all","any","bool",
        "dict","enumerate","float","int","len","list",
        "max","min","range","reversed","round","set","sorted",
        "str","sum","tuple","zip",
        "print",
    }
    return Policy(
        builtin_allowlist=safe_builtins,
        call_name_allowlist=set(safe_builtins),
        attr_allowlist={},
    )

def default_policy_v06() -> Policy:
    return default_policy_v05()

def default_policy_v07() -> Policy:
    return default_policy_v06()

def default_policy_v08() -> Policy:
    return default_policy_v07()

def default_policy_v09() -> Policy:
    return default_policy_v08()

def default_policy_v10() -> Policy:
    p = default_policy_v09()
    return Policy(**{**p.__dict__, "os_sandbox": OSSandboxConfig()})

def default_policy_v11() -> Policy:
    return default_policy_v10()

def default_policy_v12() -> Policy:
    return default_policy_v11()

def default_policy_v13() -> Policy:
    return default_policy_v12()

def default_policy_v14() -> Policy:
    return default_policy_v13()
