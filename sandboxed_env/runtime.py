from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
import io, time, traceback, random

from .errors import StepLimitError, SandboxError, CapabilityBudgetError
from .result import Event, Metrics, ErrorInfo
from .policy import Policy, DeterminismConfig
from .serialize import approx_bytes
from .capabilities import CapabilitySpec, CapabilityCost, ScopeBundle, TokenScope, Capability, load_dotted
from .audit import AuditStream

_REAL_TIME = time.time
_REAL_PERF = time.perf_counter

def real_time() -> float:
    return _REAL_TIME()

def real_perf() -> float:
    return _REAL_PERF()

class EventWriter(io.TextIOBase):
    def __init__(self, limit: int, audit: AuditStream, typ: str, t0: float, now_fn: Callable[[], float]):
        self.limit = limit
        self.audit = audit
        self.typ = typ
        self.t0 = t0
        self.now_fn = now_fn
        self.buf = io.StringIO()

    def write(self, s: str):
        if not s:
            return 0
        cur = self.buf.tell()
        rem = self.limit - cur
        if rem <= 0:
            return len(s)
        chunk = s[:rem]
        self.buf.write(chunk)
        self.audit.emit(Event(
            ts_ms=int((self.now_fn() - self.t0) * 1000),
            type=self.typ,
            data={"text": chunk},
        ))
        return len(s)

    def getvalue(self) -> str:
        return self.buf.getvalue()

def make_safe_print(stdout: EventWriter):
    def _p(*args, **kwargs):
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        stdout.write(sep.join(str(a) for a in args) + end)
    return _p

def safe_builtins(p: Policy, stdout: EventWriter) -> Dict[str, Any]:
    base = {
        "None": None, "True": True, "False": False,
        "abs": abs, "all": all, "any": any, "bool": bool,
        "dict": dict, "enumerate": enumerate, "float": float, "int": int,
        "len": len, "list": list, "max": max, "min": min,
        "range": range, "reversed": reversed, "round": round,
        "set": set, "sorted": sorted, "str": str, "sum": sum,
        "tuple": tuple, "zip": zip,
        "print": make_safe_print(stdout),
    }
    return {k: v for k, v in base.items() if k in p.builtin_allowlist}

def make_step_limiter(max_steps: int):
    steps = {"n": 0}
    def tracer(frame, event, arg):
        if event in ("line", "call"):
            steps["n"] += 1
            if steps["n"] > max_steps:
                raise StepLimitError(f"step limit exceeded: {max_steps}")
        return tracer
    return tracer, steps

def apply_linux_rlimits(p: Policy) -> None:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (p.max_cpu_seconds, p.max_cpu_seconds))
        mem = p.max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_NOFILE, (p.max_open_files, p.max_open_files))
    except Exception:
        pass

def runtime_location(tb) -> Optional[int]:
    frames = traceback.extract_tb(tb)
    for fr in reversed(frames):
        if fr.filename == "<sandbox>":
            return fr.lineno
    return None

def _code_excerpt(code: Optional[str], lineno: Optional[int], col: Optional[int]) -> tuple[Optional[str], Optional[str]]:
    if not code or not lineno:
        return None, None
    lines = code.splitlines()
    if lineno < 1 or lineno > len(lines):
        return None, None
    line = lines[lineno - 1].rstrip("\n")
    if not col:
        return line, None
    caret = (" " * max(col - 1, 0)) + "^"
    return line, caret

def errinfo(
    stage: str,
    e: Exception,
    *,
    tb_text: Optional[str] = None,
    code: Optional[str] = None,
    lineno: Optional[int] = None,
    col: Optional[int] = None,
) -> ErrorInfo:
    if lineno is None:
        lineno = getattr(e, "lineno", None)
    if col is None:
        col = getattr(e, "col", None)
    if col is None:
        col = getattr(e, "offset", None)
    if col is not None and col < 1:
        col = 1
    if col is None and lineno and code:
        col = 1
    excerpt, caret = _code_excerpt(code, lineno, col)
    return ErrorInfo(
        stage=stage,
        type=type(e).__name__,
        message=str(e),
        lineno=lineno,
        col=col,
        excerpt=excerpt,
        caret=caret,
        tb=tb_text,
    )

def apply_determinism(det: Optional[DeterminismConfig]) -> None:
    if not det:
        return
    seed = det.seed
    rng = random.Random(seed)

    _orig_random_class = random.Random
    class _DeterministicRandom(_orig_random_class):
        def __init__(self, *args, **kwargs):
            if args or kwargs:
                super().__init__(*args, **kwargs)
            else:
                super().__init__(seed)

    random.random = rng.random
    random.randrange = rng.randrange
    random.randint = rng.randint
    random.choice = rng.choice
    random.shuffle = rng.shuffle
    random.sample = rng.sample
    random.uniform = rng.uniform
    random.triangular = rng.triangular
    random.gauss = rng.gauss
    random.normalvariate = rng.normalvariate
    random.expovariate = rng.expovariate
    random.betavariate = rng.betavariate
    random.gammavariate = rng.gammavariate
    random.lognormvariate = rng.lognormvariate
    random.vonmisesvariate = rng.vonmisesvariate
    random.paretovariate = rng.paretovariate
    random.weibullvariate = rng.weibullvariate
    random.getrandbits = rng.getrandbits
    random.getstate = rng.getstate
    random.setstate = lambda _state=None: None
    random.seed = lambda *_a, **_k: None
    random.Random = _DeterministicRandom

    if det.fake_time is not None:
        start = float(det.fake_time)
        step = float(det.time_step)
        counter = {"n": 0}

        def _fake_time() -> float:
            n = counter["n"]
            counter["n"] = n + 1
            return start + (n * step)

        time.time = _fake_time
        time.perf_counter = _fake_time

class BudgetManager:
    def __init__(
        self,
        spec: BudgetSpec,
        scope: ScopeBundle,
        *,
        now_fn: Callable[[], float],
        perf_fn: Callable[[], float],
    ):
        self.spec = spec
        self.scope = scope
        self.now_fn = now_fn
        self.perf_fn = perf_fn
        self.calls = 0
        self.ms = 0
        self.bytes_out = 0
        self.bytes_in = 0
        self.start = self.perf_fn()

    def charge(self, cost: CapabilityCost) -> None:
        if cost.calls <= 0:
            return
        if self.spec.max_call_ms is not None and cost.ms > self.spec.max_call_ms:
            raise CapabilityBudgetError(f"cap max_call_ms exceeded ({self.spec.max_call_ms}ms)")
        if self.spec.max_ret_bytes is not None and cost.bytes_out > self.spec.max_ret_bytes:
            raise CapabilityBudgetError(f"cap max_ret_bytes exceeded ({self.spec.max_ret_bytes} bytes)")

        self.calls += cost.calls
        self.ms += cost.ms
        self.bytes_out += cost.bytes_out
        self.bytes_in += cost.bytes_in

        if self.spec.max_calls is not None and self.calls > self.spec.max_calls:
            raise CapabilityBudgetError(f"cap max_calls exceeded ({self.spec.max_calls})")
        if self.spec.max_total_ms is not None and self.ms > self.spec.max_total_ms:
            raise CapabilityBudgetError(f"cap max_total_ms exceeded ({self.spec.max_total_ms}ms)")
        if self.spec.max_total_bytes is not None and self.bytes_out > self.spec.max_total_bytes:
            raise CapabilityBudgetError(f"cap max_total_bytes exceeded ({self.spec.max_total_bytes} bytes)")

        elapsed = max(self.perf_fn() - self.start, 1e-6)
        if self.spec.max_qps is not None and (self.calls / elapsed) > self.spec.max_qps:
            raise CapabilityBudgetError(f"cap max_qps exceeded ({self.spec.max_qps})")
        if self.spec.max_bandwidth is not None and (self.bytes_out / elapsed) > self.spec.max_bandwidth:
            raise CapabilityBudgetError(f"cap max_bandwidth exceeded ({self.spec.max_bandwidth} bytes/sec)")

        if self.spec.max_tokens is not None and self.scope.exec_scope.total is None:
            self.scope.exec_scope.total = self.spec.max_tokens
            self.scope.exec_scope.remaining = self.spec.max_tokens

        if cost.tokens > 0:
            try:
                self.scope.consume(cost.tokens)
            except Exception as e:
                raise CapabilityBudgetError(str(e))

class WrappedCapability(Capability):
    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        *,
        cap_obj: Optional[Capability] = None,
        validator: Optional[Callable[[tuple[Any, ...], dict[str, Any]], None]] = None,
        serializer: Optional[Callable[[Any], Any]] = None,
        budget_mgr: BudgetManager,
        tokens_per_call: int,
        tokens_per_byte: float,
        arg_repr_limit: int,
        metrics: Metrics,
        audit: AuditStream,
        now_fn: Callable[[], float],
        perf_fn: Callable[[], float],
        t0_events: float,
    ):
        self.name = name
        self.func = func
        self.cap_obj = cap_obj
        self.validator = validator
        self.serializer_fn = serializer
        self.budget_mgr = budget_mgr
        self.tokens_per_call = tokens_per_call
        self.tokens_per_byte = tokens_per_byte
        self.arg_repr_limit = arg_repr_limit
        self.metrics = metrics
        self.audit = audit
        self.now_fn = now_fn
        self.perf_fn = perf_fn
        self.t0_events = t0_events

    def validate(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        if self.cap_obj:
            self.cap_obj.validate(args, kwargs)
        if self.validator:
            self.validator(args, kwargs)

    def budget(self, cost: CapabilityCost) -> None:
        self.budget_mgr.charge(cost)
        if self.cap_obj:
            self.cap_obj.budget(cost)

    def serialize(self, ret: Any) -> Any:
        out = self.cap_obj.serialize(ret) if self.cap_obj else ret
        return self.serializer_fn(out) if self.serializer_fn else out

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.validate(args, kwargs)
        bytes_in = approx_bytes(args) + approx_bytes(kwargs)

        start = self.perf_fn()
        ok = False
        err = None
        ret = None
        ser = None
        try:
            ret = self.func(*args, **kwargs)
            ser = self.serialize(ret)
            ok = True
            return ser
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            raise
        finally:
            ms = int((self.perf_fn() - start) * 1000)
            out_val = ser if ser is not None else ret
            bytes_out = approx_bytes(out_val)
            tokens = int(self.tokens_per_call + (self.tokens_per_byte * max(bytes_out, 0)))
            cost = CapabilityCost(calls=1, ms=ms, bytes_in=bytes_in, bytes_out=bytes_out, tokens=tokens)
            self.budget(cost)
            self.metrics.cap_calls[self.name] = self.budget_mgr.calls
            self.metrics.cap_ms[self.name] = self.budget_mgr.ms
            self.metrics.cap_bytes_out[self.name] = self.budget_mgr.bytes_out
            self.metrics.cap_bytes_in[self.name] = self.budget_mgr.bytes_in

            rec = {"name": self.name, "ok": ok, "ms": ms, "bytes_out": bytes_out, "bytes_in": bytes_in}
            try:
                rec["args"] = repr(args)[:self.arg_repr_limit]
                rec["kwargs"] = repr(kwargs)[:self.arg_repr_limit]
            except Exception:
                rec["args"] = "<unrepr>"
                rec["kwargs"] = "<unrepr>"
            if err:
                rec["error"] = err
            self.audit.emit(Event(
                ts_ms=int((self.now_fn()-self.t0_events)*1000),
                type="cap",
                data=rec,
            ))

def build_caps_in_worker(
    specs: List[CapabilitySpec],
    *,
    mode: str,
    registry: Optional[Dict[str, Callable[..., Any]]],
    metrics: Metrics,
    audit: AuditStream,
    scope: ScopeBundle,
    t0_events: float,
    now_fn: Callable[[], float],
    perf_fn: Callable[[], float],
) -> tuple[Dict[str, Callable[..., Any]], List[Callable[[], None]]]:
    out: Dict[str, Callable[..., Any]] = {}
    closers: List[Callable[[], None]] = []

    for spec in specs:
        cap_obj: Optional[Capability] = None
        func: Optional[Callable[..., Any]] = None
        def _as_cap(obj: Any) -> Optional[Capability]:
            if obj is None:
                return None
            if all(hasattr(obj, m) for m in ("validate", "budget", "serialize")):
                return obj  # type: ignore[return-value]
            return None

        if spec.cap_path:
            loaded = load_dotted(spec.cap_path)
            cap_obj = _as_cap(loaded)
            func = loaded
        elif mode == "fork":
            if not registry or spec.name not in registry:
                raise SandboxError(f"cap '{spec.name}' not in registry (fork mode)")
            func = registry[spec.name]
            cap_obj = _as_cap(func)
        else:
            if not spec.func_path:
                raise SandboxError(f"cap '{spec.name}' missing func_path (spawn mode)")
            func = load_dotted(spec.func_path)

        if func is None:
            raise SandboxError(f"cap '{spec.name}' missing callable")

        init_fn = load_dotted(spec.init_path) if spec.init_path else None
        close_fn = load_dotted(spec.close_path) if spec.close_path else None
        init_state = None
        if init_fn:
            init_state = init_fn()
        if close_fn:
            def _make_close(fn=close_fn, state=init_state):
                return lambda: fn(state)
            closers.append(_make_close())

        validator = load_dotted(spec.validator_path) if spec.validator_path else None
        serializer = load_dotted(spec.serializer_path) if spec.serializer_path else None
        budget_mgr = BudgetManager(spec.budget, scope, now_fn=now_fn, perf_fn=perf_fn)

        wrapped = WrappedCapability(
            spec.name,
            func,
            cap_obj=cap_obj,
            validator=validator,
            serializer=serializer,
            budget_mgr=budget_mgr,
            tokens_per_call=spec.tokens_per_call,
            tokens_per_byte=spec.tokens_per_byte,
            arg_repr_limit=spec.arg_repr_limit,
            metrics=metrics,
            audit=audit,
            now_fn=now_fn,
            perf_fn=perf_fn,
            t0_events=t0_events,
        )
        out[spec.name] = wrapped

    return out, closers
