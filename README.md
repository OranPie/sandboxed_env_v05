# SandboxedEnv v1.4

A practical, capability-based Python sandbox.

## What this provides

- **AST policy**: no `import`, no dunder names, no arbitrary attribute access
- **Function allowlist**: only allow calling `Name(...)` for allowlisted names
- **Optional `root.attr` allowlist**: only allow `root.attr` where `root` and `attr` are allowlisted
- **Safe roots**: `SafeModuleProxy` exposes only allowlisted attributes
- **Capabilities**: explicit list, each with budgets (`BudgetSpec`) + audit events
- **Process isolation**: runs code in a subprocess with timeout
- **Step budget**: uses `sys.settrace` to enforce an execution step limit
- **Best-effort rlimits** (Linux): CPU, memory (AS), open files
- **Input deep-freeze**: prevents sandbox mutating caller-provided objects
- **Output JSON-safe**: returns only JSON-ish values with truncation
- **Event stream**: stdout/stderr/capability calls are returned as timestamped events
- **Policy presets**: pure_compute, compute_plus_math, compute_plus_http
- **Determinism options**: seeded random, optional fake time, optional float normalization
- **Return contract**: __result__, __events__, __stats__ (plus token scopes)
- **Better errors**: excerpt + caret with line/col
- **Spawn-safe defaults**: dotted-path capabilities by default (Windows-friendly)
- **Runner options**: local process or external container/nsjail/firejail command
- **Capability framework**: validate/budget/serialize hooks, budgets, scopes, audit sinks
- **Smarter static checks**: loop-iterable restrictions + suspicious allocation detection
- **Type shaping**: optional input/output schema validation
- **Module proxy hardening**: callable-only attrs, read-only return wrapping
- **OS hardening**: seccomp profile, no-network default, filesystem sandbox (best-effort)

## Installation / layout

This repository is a pure-Python package:

- `sandboxed_env_v05/` package
- `examples/basic_demo.py`

You can run the demo with:

```bash
python -m sandboxed_env.examples.basic_demo
```

(Or add this package folder to your PYTHONPATH.)

## Quick usage (fork mode recommended on Unix)

```python
import math
from sandboxed_env import SandboxedEnv, default_policy_v14, Policy, CapabilitySpec, BudgetSpec, SafeModuleProxy

policy = default_policy_v14()
policy = Policy(**{
    **policy.__dict__,
    "attr_allowlist": {"math": {"sin", "cos", "pi"}},
})

math_proxy = SafeModuleProxy(math, allow={"sin": True, "cos": True, "pi": {"value": True}}, name="math")


def add(a, b): return a + b


env = SandboxedEnv(
    policy,
    mode="fork",
    roots={"math": math_proxy},
    cap_registry={"add": add},
    cap_specs=[CapabilitySpec(name="add", budget=BudgetSpec(max_calls=20, max_total_ms=50))],
)

r = env.execute("print(add(1,2)); __result__=math.pi")
print(r.ok, r.result)
```

Note: v1.4 defaults to `mode="spawn"` for Windows-friendly behavior. When using spawn-safe mode,
capabilities must be registered via dotted paths only.

## Policy presets

```python
from sandboxed_env import get_policy_preset, SandboxedEnv

preset = get_policy_preset("compute_plus_math")
env = SandboxedEnv(preset.policy, root_specs=preset.root_specs)
```

## Return contract

Inside sandboxed code you can set:

```python
__result__ = {"value": 123}
__events__ = [{"type": "user", "data": {"note": "hello"}}]
__stats__ = {"items": 42}
```

These are surfaced on `SandboxResult.result`, `SandboxResult.events` (appended),
and `SandboxResult.stats["user"]`. Token scopes are exposed in `SandboxResult.stats["token_scopes"]`.

## Upgrade notes (v1.4)

- `SandboxResult.stats` now returns a dict with `user` and `token_scopes` (instead of raw `__stats__`).
- Token scopes include `exec`, `session`, and `tenant`; session/tenant scopes can be persisted via `SandboxedEnv`.

## Determinism options

```python
from sandboxed_env import Policy, DeterminismConfig, default_policy_v14

policy = default_policy_v14()
policy = Policy(**{
    **policy.__dict__,
    "determinism": DeterminismConfig(seed=0, fake_time=0.0, time_step=0.0, float_format=".6g"),
})
```

## Type shaping (schemas)

You can restrict inputs/outputs using a JSON-schema-like dict:

```python
policy = Policy(**{
    **policy.__dict__,
    "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
    "output_schema": {"type": "object", "properties": {"x": {"type": "integer"}}},
})
```

Schemas are validated against the JSON-safe inputs/outputs.

## Schema caching and formats

Schema validation uses a small cache keyed by JSON serialization to reduce overhead.
Supported string formats include `email` and `uuid`, and regex `pattern`.

## Spawn mode (portable)

Spawn mode is the default in v1.4. In spawn mode, capabilities must be importable by dotted paths:

```python
CapabilitySpec(name="add", func_path="mycaps:add")
```

Roots can be provided via `RootSpec`:

```python
from sandboxed_env import RootSpec

RootSpec(name="math", target="math", allow_tree={"sin": True, "pi": {"value": True}})
```

Then:

```python
env = SandboxedEnv(mode="spawn", cap_specs=[...], root_specs=[...])
```

## Smarter static checks

Loop iterables are restricted to `range`/`list`/`tuple` (literals or calls) by default (configurable in `Policy`).
The AST checker also blocks suspicious constant-folded allocations (e.g. gigantic `[*] * N`).

## Module proxy hardening

`SafeModuleProxy` now exposes callable attributes only, and wraps return values as read-only. For constants,
use `{"value": True}` in the allow-tree:

```python
SafeModuleProxy(math, allow={"sin": True, "pi": {"value": True}}, name="math")
```

## OS hardening (seccomp / no-network / filesystem)

Best-effort OS sandboxing (Linux) can be configured via `OSSandboxConfig`:

```python
from sandboxed_env import OSSandboxConfig, Policy

policy = Policy(**{
    **policy.__dict__,
    "os_sandbox": OSSandboxConfig(
        seccomp_profile="/path/to/seccomp.json",
        seccomp_enforce=False,
        no_network=True,
        fs_mode="tmp",
        fs_enforce=False,
        fs_chroot=False,
    ),
})
```

If seccomp isn't available, enforcement will be skipped unless `seccomp_enforce=True`.
The seccomp profile is expected to be a minimal OCI-style JSON (defaultAction + syscalls names).

Validate a profile:

```bash
python -m sandboxed_env.examples.validate_seccomp examples/seccomp_minimal.json
```

Merge additional syscalls into a base profile:

```bash
python -m sandboxed_env.examples.merge_seccomp examples/seccomp_minimal.json openat stat
```

## Capability framework (v1.4)

Each capability can provide:
- `validate(args, kwargs)` input validation
- `budget(cost)` custom budget checks
- `serialize(ret)` output normalization

You can load a full capability object with `cap_path="pkg.mod:cap"` (must be callable and implement the hooks).

Built-in budgets live in `BudgetSpec`, with per-call, per-run, QPS, bandwidth, and size limits:

```python
from sandboxed_env import CapabilitySpec, BudgetSpec

cap = CapabilitySpec(
    name="http_get",
    func_path="mycaps:http_get",
    budget=BudgetSpec(max_calls=20, max_qps=2.0, max_bandwidth=50_000, max_ret_bytes=20_000),
    tokens_per_byte=1.0,
)
```

Per-execution tokens are supplied at execution time:

```python
r = env.execute("...", tokens=1000)

# Optionally track session/tenant tokens across runs:
env = SandboxedEnv(session_tokens=10_000, tenant_tokens=1_000_000)
```

## Audit sinks

Audit sinks are pluggable and can write to memory, file, stdout, OpenTelemetry, or webhook.

```python
from sandboxed_env import AuditSinkSpec

env = SandboxedEnv(
    mode="spawn",
    cap_specs=[...],
    audit_sink_specs=[
        AuditSinkSpec(kind="file", options={"path": "/tmp/sandbox_audit.jsonl"}),
        AuditSinkSpec(kind="stdout", options={}),
    ],
)
```

Note: token scopes are exposed in `SandboxResult.stats["token_scopes"]` and can be recorded by the host
alongside audit events if needed.

## Fuzzing harness

Run the basic fuzzing harness (random AST + regression payloads):

```bash
python -m sandboxed_env.examples.fuzz_harness
```

## Runner options (container / nsjail / firejail)

You can run the worker inside an external runner by providing a command
that ultimately executes the worker entrypoint:

```python
import sys
from sandboxed_env import SandboxedEnv, command_runner

runner = command_runner([
    "nsjail", "--quiet", "--", sys.executable, "-m", "sandboxed_env.worker_entry"
])

env = SandboxedEnv(mode="spawn", runner=runner, cap_specs=[...], root_specs=[...])
```

Note: `spawn` requires that objects passed to worker are picklable. Prefer `RootSpec` to recreate roots inside worker.

## Security notes

- This is a **practical** sandbox combining policy + subprocess isolation. For stronger isolation against highly adversarial code, add containerization/seccomp.
- Keep `attr_allowlist` small. Prefer exposing functions as capabilities instead of allowing general attribute access.
- All I/O should go through capabilities with validators and budgets.
