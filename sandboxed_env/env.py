from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
import ast
import json
import multiprocessing as mp
import os
import signal
import subprocess
import time
import traceback
import sys

from .policy import Policy, default_policy_v14
from .capabilities import CapabilitySpec
from .roots import RootSpec, build_roots_from_specs
from .ast_checker import PolicyChecker
from .freeze import deep_freeze
from .serialize import to_safe_json
from .result import SandboxResult, ErrorInfo, Event, Metrics
from .runtime import (
    apply_linux_rlimits,
    apply_determinism,
    real_perf,
    safe_builtins,
    make_step_limiter,
    EventWriter,
    errinfo,
    runtime_location,
    build_caps_in_worker,
)
from .runner import RunnerSpec, local_runner
from .wire import policy_to_dict, cap_specs_to_list, root_specs_to_list
from .audit import AuditSink, AuditSinkSpec, AuditStream, build_audit_sinks, audit_sink_specs_to_list
from .capabilities import TokenScope, ScopeBundle
from .schema import validate_schema_cached, SchemaError
from .os_sandbox import apply_os_sandbox
from .i18n import translate_error, timeout_message
from .plugin_system import PluginContext, PluginSpec, apply_plugins

def _maybe_setsid() -> None:
    if os.name != "nt":
        try:
            os.setsid()
        except Exception:
            pass

def _kill_process_group(pid: int, sig: int) -> None:
    if os.name != "nt":
        try:
            os.killpg(pid, sig)
        except Exception:
            pass

def _terminate_process(p: mp.Process, *, timeout_s: float = 0.05) -> None:
    if not p or not getattr(p, "pid", None):
        return
    _kill_process_group(p.pid, signal.SIGTERM)
    try:
        p.terminate()
    except Exception:
        pass
    for _ in range(5):
        try:
            p.join(timeout_s)
        except Exception:
            pass
        if not p.is_alive():
            return
        _kill_process_group(p.pid, signal.SIGKILL)
        try:
            p.kill()
        except Exception:
            pass
    try:
        p.join(timeout_s)
    except Exception:
        pass

def _terminate_popen(p: subprocess.Popen, *, timeout_s: float = 0.05) -> None:
    if not p or not getattr(p, "pid", None):
        return
    _kill_process_group(p.pid, signal.SIGTERM)
    try:
        p.terminate()
    except Exception:
        pass
    for _ in range(5):
        try:
            p.wait(timeout=timeout_s)
            return
        except Exception:
            _kill_process_group(p.pid, signal.SIGKILL)
            try:
                p.kill()
            except Exception:
                pass
    try:
        p.wait(timeout=timeout_s)
    except Exception:
        pass

def _run_worker(
    code: str,
    policy: Policy,
    cap_specs: List[CapabilitySpec],
    roots: Dict[str, Any],
    inputs: Optional[Dict[str, Any]],
    mode: str,
    cap_registry: Optional[Dict[str, Callable[..., Any]]],
    root_specs: Optional[List[RootSpec]] = None,
    tokens: Optional[int] = None,
    session_tokens: Optional[int] = None,
    tenant_tokens: Optional[int] = None,
    audit_sinks: Optional[List[AuditSink]] = None,
    audit_sink_specs: Optional[List[AuditSinkSpec]] = None,
) -> Dict[str, Any]:
    _maybe_setsid()
    t0_wall = real_perf()
    apply_linux_rlimits(policy)
    apply_determinism(policy.determinism)
    try:
        apply_os_sandbox(policy.os_sandbox)
    except Exception as e:
        metrics = Metrics()
        metrics.wall_ms = int((real_perf()-t0_wall)*1000)
        return {
            "ok": False,
            "error": errinfo("worker", e, code=code).__dict__,
            "result": None,
            "locals": {},
            "events": [],
            "metrics": metrics.__dict__,
            "stats": None,
        }
    import sys
    sys.setrecursionlimit(policy.max_recursion)

    events: List[Event] = []
    sinks: List[AuditSink] = []
    if audit_sinks:
        sinks.extend(audit_sinks)
    if audit_sink_specs:
        sinks.extend(build_audit_sinks(audit_sink_specs))
    audit = AuditStream(events, sinks)
    now_fn = time.time  # may be patched by determinism
    t0_events = now_fn()
    stdout = EventWriter(policy.max_stdout_bytes, audit, "stdout", t0_events, now_fn)
    stderr = EventWriter(policy.max_stderr_bytes, audit, "stderr", t0_events, now_fn)
    metrics = Metrics()
    float_format = policy.determinism.float_format if policy.determinism else None
    scope_bundle = ScopeBundle(
        exec_scope=TokenScope(tokens),
        session_scope=TokenScope(session_tokens),
        tenant_scope=TokenScope(tenant_tokens),
    )

    # parse
    try:
        tree = ast.parse(code, mode="exec")
    except Exception as e:
        metrics.wall_ms = int((real_perf()-t0_wall)*1000)
        return {"ok": False, "error": errinfo("parse", e, code=code).__dict__, "result": None, "locals": {}, "events": [ev.__dict__ for ev in events], "metrics": metrics.__dict__, "stats": None}

    # policy check
    try:
        known_iters: set[str] = set()
        if inputs is not None:
            if isinstance(inputs, dict):
                for k, v in inputs.items():
                    if isinstance(v, (list, tuple)):
                        known_iters.add(str(k))
            else:
                if isinstance(inputs, (list, tuple)):
                    known_iters.add("input")
        checker = PolicyChecker(policy, known_iter_names=known_iters)
        checker.visit(tree)
        metrics.ast_nodes = checker.node_count
        compiled = compile(tree, "<sandbox>", "exec")
    except Exception as e:
        metrics.wall_ms = int((real_perf()-t0_wall)*1000)
        return {"ok": False, "error": errinfo("policy", e, code=code).__dict__, "result": None, "locals": {}, "events": [ev.__dict__ for ev in events], "metrics": metrics.__dict__, "stats": None}

    # globals/locals
    if (not roots) and root_specs:
        built_roots, _ = build_roots_from_specs(root_specs)
        roots = built_roots
    g: Dict[str, Any] = {"__builtins__": safe_builtins(policy, stdout)}
    g.update(roots)

    try:
        caps, closers = build_caps_in_worker(cap_specs, mode=mode, registry=cap_registry, metrics=metrics, audit=audit, scope=scope_bundle, t0_events=t0_events, now_fn=now_fn, perf_fn=real_perf)
        g.update(caps)
    except Exception as e:
        metrics.wall_ms = int((real_perf()-t0_wall)*1000)
        return {"ok": False, "error": errinfo("worker", e, code=code).__dict__, "result": None, "locals": {}, "events": [ev.__dict__ for ev in events], "metrics": metrics.__dict__, "stats": None}

    l: Dict[str, Any] = {}
    if inputs:
        fr = deep_freeze(inputs)
        if isinstance(fr, dict):
            l.update(fr)
        else:
            l["input"] = fr

    tracer, steps = make_step_limiter(policy.max_steps)
    old_trace = sys.gettrace()
    old_stderr = sys.stderr
    sys.settrace(tracer)
    sys.stderr = stderr

    ok = True
    err: Optional[ErrorInfo] = None
    try:
        exec(compiled, g, l)
    except Exception as e:
        ok = False
        ln = runtime_location(e.__traceback__)
        tb_text = traceback.format_exc(limit=3)
        err = errinfo("runtime", e, tb_text=tb_text, lineno=ln, code=code)
    finally:
        sys.settrace(old_trace)
        sys.stderr = old_stderr
        try:
            for c in closers:
                c()
        except Exception:
            pass

    metrics.steps = steps["n"]
    metrics.wall_ms = int((real_perf()-t0_wall)*1000)
    metrics.stdout_bytes = len(stdout.getvalue().encode("utf-8", errors="ignore"))
    metrics.stderr_bytes = len(stderr.getvalue().encode("utf-8", errors="ignore"))
    try:
        import resource
        ru = resource.getrusage(resource.RUSAGE_SELF)
        metrics.user_ms = int(ru.ru_utime * 1000)
        metrics.sys_ms = int(ru.ru_stime * 1000)
        metrics.max_rss_kb = int(getattr(ru, "ru_maxrss", 0))
    except Exception:
        pass

    raw_result = l.get("__result__", None)
    raw_events = l.get("__events__", None)
    raw_stats = l.get("__stats__", None)
    safe_locals = to_safe_json({k: v for k, v in l.items() if not k.startswith("__")}, float_format=float_format, max_bytes=policy.max_stdout_bytes)
    safe_result = to_safe_json(raw_result, float_format=float_format, max_bytes=policy.max_stdout_bytes)
    safe_stats = to_safe_json(raw_stats, float_format=float_format, max_bytes=policy.max_stdout_bytes)

    if raw_events is not None:
        if not isinstance(raw_events, list):
            raw_events = [raw_events]
        for ev in raw_events:
            if isinstance(ev, dict):
                ev_type = str(ev.get("type", "user"))
                ev_ts = ev.get("ts_ms")
                ev_data = ev.get("data")
                if ev_data is None:
                    ev_data = {k: v for k, v in ev.items() if k not in ("type", "ts_ms", "data")}
                audit.emit(Event(
                    ts_ms=int(ev_ts) if ev_ts is not None else int((now_fn()-t0_events)*1000),
                    type=ev_type,
                    data=to_safe_json(ev_data, float_format=float_format, max_bytes=policy.max_stdout_bytes),
                ))
            else:
                audit.emit(Event(
                    ts_ms=int((now_fn()-t0_events)*1000),
                    type="user",
                    data={"value": to_safe_json(ev, float_format=float_format, max_bytes=policy.max_stdout_bytes)},
                ))

    return {
        "ok": ok,
        "error": (err.__dict__ if err else None),
        "result": safe_result,
        "locals": safe_locals,
        "events": [ev.__dict__ for ev in events],
        "metrics": metrics.__dict__,
        "stats": {
            "user": safe_stats,
            "token_scopes": {
                "exec": scope_bundle.exec_scope.remaining,
                "session": scope_bundle.session_scope.remaining,
                "tenant": scope_bundle.tenant_scope.remaining,
            },
        },
    }

def _worker(
    code: str,
    policy: Policy,
    cap_specs: List[CapabilitySpec],
    roots: Dict[str, Any],
    inputs: Optional[Dict[str, Any]],
    mode: str,
    cap_registry: Optional[Dict[str, Callable[..., Any]]],
    root_specs: Optional[List[RootSpec]],
    tokens: Optional[int],
    session_tokens: Optional[int],
    tenant_tokens: Optional[int],
    audit_sinks: Optional[List[AuditSink]],
    audit_sink_specs: Optional[List[AuditSinkSpec]],
    q: mp.Queue,
):
    q.put(_run_worker(code, policy, cap_specs, roots, inputs, mode, cap_registry, root_specs, tokens, session_tokens, tenant_tokens, audit_sinks, audit_sink_specs))

class SandboxedEnv:
    """SandboxedEnv v1.4

    mode:
      - 'fork': worker inherits cap_registry callables (best on Unix)
      - 'spawn': worker loads capabilities via dotted paths (portable, default)

    roots:
      - for fork mode: pass 'roots' dict (prefer SafeModuleProxy)
      - for spawn mode: pass root_specs so worker can recreate roots
    """
    def __init__(
        self,
        policy: Optional[Policy] = None,
        *,
        mode: str = "spawn",
        cap_specs: Optional[List[CapabilitySpec]] = None,
        cap_registry: Optional[Dict[str, Callable[..., Any]]] = None,
        roots: Optional[Dict[str, Any]] = None,
        root_specs: Optional[List[RootSpec]] = None,
        runner: Optional[RunnerSpec] = None,
        audit_sinks: Optional[List[AuditSink]] = None,
        audit_sink_specs: Optional[List[AuditSinkSpec]] = None,
        session_tokens: Optional[int] = None,
        tenant_tokens: Optional[int] = None,
        plugins: Optional[List[PluginSpec | Any]] = None,
        locale: str = "en",
    ):
        self.locale = locale or "en"
        self.policy = policy or default_policy_v14()
        self.mode = mode
        self.cap_specs = list(cap_specs or [])
        self.cap_registry = dict(cap_registry or {})
        self.root_specs = list(root_specs or [])
        self.runner = runner or local_runner()
        self.audit_sinks = list(audit_sinks or [])
        self.audit_sink_specs = list(audit_sink_specs or [])
        self.session_tokens = session_tokens
        self.tenant_tokens = tenant_tokens

        if plugins:
            ctx = PluginContext(
                policy=self.policy,
                cap_specs=self.cap_specs,
                cap_registry=self.cap_registry,
                roots=roots or {},
                root_specs=self.root_specs,
                audit_sinks=self.audit_sinks,
                audit_sink_specs=self.audit_sink_specs,
                runner=self.runner,
                locale=self.locale,
            )
            apply_plugins(plugins, ctx)
            self.policy = ctx.policy
            self.cap_specs = ctx.cap_specs
            self.cap_registry = ctx.cap_registry
            self.root_specs = ctx.root_specs
            self.audit_sinks = ctx.audit_sinks
            self.audit_sink_specs = ctx.audit_sink_specs
            self.runner = ctx.runner
            self.locale = ctx.locale
            roots = ctx.roots

        if self.mode == "fork" and os.name == "nt":
            raise ValueError("fork mode is not supported on Windows")
        if self.mode != "fork":
            if self.cap_registry:
                raise ValueError("cap_registry is not supported in spawn-safe modes; use dotted func_path")
            for c in self.cap_specs:
                if not c.func_path and not c.cap_path:
                    raise ValueError(f"cap '{c.name}' missing func_path/cap_path in spawn-safe mode")
            if self.audit_sinks:
                raise ValueError("audit_sinks are not supported in spawn-safe modes; use audit_sink_specs")
            if self.policy.input_schema is not None and not isinstance(self.policy.input_schema, dict):
                raise ValueError("input_schema must be a dict in spawn-safe modes")
            if self.policy.output_schema is not None and not isinstance(self.policy.output_schema, dict):
                raise ValueError("output_schema must be a dict in spawn-safe modes")

        # Build roots
        self.roots = roots or {}
        if self.root_specs:
            if self.mode == "fork":
                built_roots, attr_allow = build_roots_from_specs(self.root_specs)
                self.roots.update(built_roots)
            else:
                attr_allow = {s.name: s.attr_allow() for s in self.root_specs}
            # Merge attr_allowlist into policy
            merged = dict(self.policy.attr_allowlist)
            for k, s in attr_allow.items():
                merged[k] = set(merged.get(k, set())) | set(s)
            self.policy = Policy(**{**self.policy.__dict__, "attr_allowlist": merged})

        # Expand allowed direct calls with capability names
        cap_names = {c.name for c in self.cap_specs}
        expanded = set(self.policy.call_name_allowlist) | cap_names
        self.policy = Policy(**{**self.policy.__dict__, "call_name_allowlist": expanded})

    def execute(self, code: str, inputs: Optional[Dict[str, Any]] = None, *, tokens: Optional[int] = None) -> SandboxResult:
        if self.policy.input_schema is not None:
            try:
                validate_schema_cached(to_safe_json(inputs) if inputs is not None else None, self.policy.input_schema)
            except SchemaError as e:
                err = translate_error(ErrorInfo(stage="schema", type="SchemaError", message=str(e)), self.locale)
                return SandboxResult(ok=False, error=err)
        if self.runner.kind == "command":
            if self.mode != "spawn":
                raise ValueError("command runner requires spawn mode")
            if self.roots and not self.root_specs:
                raise ValueError("command runner requires root_specs (cannot serialize roots)")
            if self.audit_sinks:
                raise ValueError("command runner requires audit_sink_specs (audit_sinks not supported)")
            if any(s.kind == "stdout" for s in self.audit_sink_specs):
                raise ValueError("stdout audit sink is not supported with command runner")

            payload = {
                "code": code,
                "policy": policy_to_dict(self.policy),
                "cap_specs": cap_specs_to_list(self.cap_specs),
                "root_specs": root_specs_to_list(self.root_specs),
                "inputs": to_safe_json(inputs) if inputs is not None else None,
                "mode": self.mode,
                "tokens": tokens,
                "session_tokens": self.session_tokens,
                "tenant_tokens": self.tenant_tokens,
                "audit_sink_specs": audit_sink_specs_to_list(self.audit_sink_specs),
            }
            cmd = self.runner.command or [sys.executable, "-m", "sandboxed_env.worker_entry"]
            try:
                p = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.runner.cwd,
                    env=self.runner.env,
                    start_new_session=True,
                )
            except Exception as e:
                return SandboxResult(ok=False, error=ErrorInfo(stage="worker", type=type(e).__name__, message=str(e)))

            try:
                out, err = p.communicate(json.dumps(payload).encode("utf-8"), timeout=self.policy.timeout_ms / 1000.0)
            except subprocess.TimeoutExpired:
                _terminate_popen(p)
                err = ErrorInfo(stage="timeout", type="TimeoutError", message=timeout_message(self.policy.timeout_ms, self.locale))
                return SandboxResult(ok=False, error=err)

            if not out:
                msg = err.decode("utf-8", errors="ignore") if err else "no payload from worker"
                err = ErrorInfo(stage="worker", type="WorkerError", message=msg)
                return SandboxResult(ok=False, error=translate_error(err, self.locale))

            try:
                payload = json.loads(out.decode("utf-8"))
            except Exception as e:
                msg = err.decode("utf-8", errors="ignore") if err else ""
                err = ErrorInfo(stage="worker", type=type(e).__name__, message=f"invalid payload: {msg}")
                return SandboxResult(ok=False, error=translate_error(err, self.locale))
        else:
            ctx = mp.get_context("fork" if self.mode == "fork" else "spawn")
            q: mp.Queue = ctx.Queue()
            roots_for_worker = self.roots if (self.mode == "fork" or not self.root_specs) else {}
            p = ctx.Process(
                target=_worker,
                args=(code, self.policy, self.cap_specs, roots_for_worker, inputs, self.mode, (self.cap_registry if self.mode == "fork" else None), self.root_specs, tokens, self.session_tokens, self.tenant_tokens, (self.audit_sinks if self.mode == "fork" else None), self.audit_sink_specs, q),
            )
            p.start()
            p.join(self.policy.timeout_ms / 1000.0)

            if p.is_alive():
                _terminate_process(p)
                err = ErrorInfo(stage="timeout", type="TimeoutError", message=timeout_message(self.policy.timeout_ms, self.locale))
                return SandboxResult(ok=False, error=err)

            try:
                payload = q.get_nowait()
            except Exception:
                err = ErrorInfo(stage="worker", type="WorkerError", message="no payload from worker")
                return SandboxResult(ok=False, error=translate_error(err, self.locale))

        metrics = Metrics(**(payload.get("metrics") or {}))
        err = payload.get("error")
        err_obj = translate_error(ErrorInfo(**err), self.locale) if err else None
        events = [Event(**e) for e in (payload.get("events") or [])]
        stats = payload.get("stats") or {}
        scopes = stats.get("token_scopes") or {}
        if "session" in scopes:
            self.session_tokens = scopes.get("session")
        if "tenant" in scopes:
            self.tenant_tokens = scopes.get("tenant")

        if self.policy.output_schema is not None and payload.get("ok"):
            try:
                validate_schema_cached(payload.get("result"), self.policy.output_schema)
            except SchemaError as e:
                return SandboxResult(
                    ok=False,
                    result=payload.get("result"),
                    locals=payload.get("locals") or {},
                    error=translate_error(ErrorInfo(stage="schema", type="SchemaError", message=str(e)), self.locale),
                    events=events,
                    metrics=metrics,
                    stats=payload.get("stats"),
                )

        return SandboxResult(
            ok=bool(payload.get("ok")),
            result=payload.get("result"),
            locals=payload.get("locals") or {},
            error=err_obj,
            events=events,
            metrics=metrics,
            stats=payload.get("stats"),
        )
