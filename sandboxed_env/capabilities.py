from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
import importlib
from .errors import CapabilityBudgetError

@dataclass
class CapabilityCost:
    calls: int = 1
    ms: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    tokens: int = 0

@dataclass
class BudgetSpec:
    max_calls: Optional[int] = 100                # per-run
    max_total_ms: Optional[int] = 200             # per-run
    max_qps: Optional[float] = None     # rate limit
    max_bandwidth: Optional[int] = None # bytes/sec (based on bytes_out)
    max_ret_bytes: Optional[int] = 200_000        # size per-call
    max_call_ms: Optional[int] = None   # per-call
    max_total_bytes: Optional[int] = None  # per-run
    max_tokens: Optional[int] = None    # per-exec scope

class TokenScope:
    def __init__(self, tokens: Optional[int] = None):
        self.total = tokens
        self.remaining = tokens

    def consume(self, n: int) -> None:
        if self.remaining is None:
            return
        if n > self.remaining:
            raise CapabilityBudgetError(f"token budget exceeded: need {n}, remaining {self.remaining}")
        self.remaining -= n

@dataclass
class ScopeBundle:
    exec_scope: TokenScope
    session_scope: TokenScope
    tenant_scope: TokenScope

    def consume(self, n: int) -> None:
        if n <= 0:
            return
        scopes = (self.exec_scope, self.session_scope, self.tenant_scope)
        for scope in scopes:
            if scope.remaining is None:
                continue
            if scope.remaining >= n:
                scope.consume(n)
                return
        if all(scope.remaining is None for scope in scopes):
            return
        raise CapabilityBudgetError("token budget exceeded across scopes")

class Capability:
    def validate(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        return None

    def budget(self, cost: CapabilityCost) -> None:
        return None

    def serialize(self, ret: Any) -> Any:
        return ret

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

@dataclass(frozen=True)
class CapabilitySpec:
    """Capability definition with built-in budget config."""
    name: str
    func_path: Optional[str] = None       # spawn mode: "pkg.mod:func"
    cap_path: Optional[str] = None        # optional: "pkg.mod:cap" with validate/budget/serialize
    init_path: Optional[str] = None       # optional: "pkg.mod:init"
    close_path: Optional[str] = None      # optional: "pkg.mod:close"
    validator_path: Optional[str] = None  # optional: "pkg.mod:validator"
    serializer_path: Optional[str] = None # optional: "pkg.mod:serializer"
    budget: BudgetSpec = field(default_factory=BudgetSpec)
    tokens_per_call: int = 0
    tokens_per_byte: float = 0.0
    arg_repr_limit: int = 400

def load_dotted(path: str) -> Callable[..., object]:
    mod, _, attr = path.partition(":")
    if not mod or not attr:
        raise ValueError(f"Invalid dotted path: {path}")
    m = importlib.import_module(mod)
    return getattr(m, attr)
