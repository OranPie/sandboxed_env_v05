# 配置文档（v1.4）

本文档覆盖 SandboxedEnv 的**完整可配置项**、默认值与常见组合方式。

## 目录

- 核心入口：`SandboxedEnv`
- 执行入口：`SandboxedEnv.execute`
- 策略：`Policy`
- 确定性：`DeterminismConfig`
- OS 沙箱：`OSSandboxConfig`
- 能力：`CapabilitySpec` / `BudgetSpec`
- Scope：`TokenScope` / `ScopeBundle`
- 根对象：`RootSpec`
- 审计：`AuditSinkSpec`
- 运行器：`RunnerSpec`
- 预设：`PolicyPreset`
- 返回结构：`SandboxResult`

## 核心入口：SandboxedEnv

```python
SandboxedEnv(
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
)
```

说明：

- `policy`：安全策略，默认 `default_policy_v14()`。
- `mode`：`"spawn"`（默认）或 `"fork"`。Windows 仅支持 `"spawn"`。
- `cap_specs`：能力规格列表，详见下文。
- `cap_registry`：仅 `fork` 模式使用，映射 `name -> callable`。
- `roots`：仅 `fork` 模式传入；`spawn` 模式应使用 `root_specs`。
- `root_specs`：`spawn` 模式下用于在 worker 内重建 roots。
- `runner`：默认 `local_runner()`；可用 `command_runner(...)` 进入容器/nsjail/firejail。
- `audit_sinks`：仅 `fork` 模式可用的审计 sink 实例列表。
- `audit_sink_specs`：`spawn`/`command` 模式可序列化的审计配置。
- `session_tokens` / `tenant_tokens`：跨多次执行持久化 token scope。

Spawn-safe 约束（`mode != "fork"`）：

- `cap_registry` 不可用，必须给 `CapabilitySpec.func_path` 或 `cap_path`
- `audit_sinks` 不可用，必须使用 `audit_sink_specs`
- `input_schema` / `output_schema` 必须是 `dict`
- `command` runner 不支持 stdout 审计 sink

## 执行入口：SandboxedEnv.execute

```python
execute(
    code: str,
    inputs: Optional[Dict[str, Any]] = None,
    *,
    tokens: Optional[int] = None,
) -> SandboxResult
```

- `code`：要运行的源码字符串。
- `inputs`：输入对象，会被深度冻结并注入为局部变量：
  - dict：直接解包为局部变量
  - 其他：注入为 `input`
- `tokens`：**本次执行**的 token scope（exec scope）。
- `session_tokens` / `tenant_tokens`：来自 `SandboxedEnv` 构造器，可跨次执行递减。

Token 消耗顺序：`exec -> session -> tenant`，优先消耗能覆盖本次 cost 的 scope。

## 策略：Policy

`Policy` 控制语法、内置函数、资源限制、schema 等。建议从 `default_policy_v14()` 开始修改。

字段与默认值（见 `policy.py`）：

- **builtin_allowlist**：可用内置函数名集合（默认来自 `default_policy_v14()` 的安全集合）
- **call_name_allowlist**：允许直接调用的 `Name(...)` 集合（默认同上）
- **attr_allowlist**：允许的 `root.attr`（默认 `{}`）
- **allow_def** = False
- **allow_lambda** = False
- **allow_class** = False
- **allow_try** = False
- **allow_with** = False
- **allow_loops** = True
- **allow_comprehension** = True
- **allow_subscript** = True
- **allow_dunder_names** = {"__result__", "__events__", "__stats__"}
- **restrict_loop_iterables** = True
- **loop_iter_allowlist** = {"range","list","tuple"}
- **allow_loop_iter_literals** = True
- **allow_loop_iter_names** = True
- **max_ast_nodes** = 7000
- **max_loop_nesting** = 3
- **max_comp_nesting** = 3
- **max_literal_elems** = 100000
- **max_const_alloc_elems** = 1000000
- **timeout_ms** = 800
- **max_steps** = 120000
- **max_stdout_bytes** = 32000
- **max_stderr_bytes** = 32000
- **max_memory_mb** = 256
- **max_cpu_seconds** = 1
- **max_open_files** = 32
- **max_recursion** = 300
- **determinism** = None
- **input_schema** = None
- **output_schema** = None
- **os_sandbox** = None

建议：

- 只通过 `attr_allowlist` 暴露极少量 root 属性
- 生产使用时启用更严格的 `timeout_ms` / `max_steps`

## 确定性：DeterminismConfig

```python
DeterminismConfig(
    seed: int = 0,
    fake_time: Optional[float] = None,
    time_step: float = 0.0,
    float_format: Optional[str] = None,
)
```

- `seed`：随机数种子
- `fake_time`：若设置，则 `time.time()`/`perf_counter()` 返回伪时间
- `time_step`：伪时间每次调用递增的步长
- `float_format`：若设置，将 float 格式化为字符串（如 ".6g"）

## OS 沙箱：OSSandboxConfig

```python
OSSandboxConfig(
    seccomp_profile: Optional[str] = None,
    seccomp_enforce: bool = False,
    no_network: bool = True,
    fs_mode: str = "tmp",  # none|tmp|ro
    fs_enforce: bool = False,
    fs_chroot: bool = False,
    tmp_dir: Optional[str] = None,
)
```

说明：

- 仅 Linux 支持 seccomp 与 fs 强制；非 Linux 下若 `seccomp_enforce`/`fs_enforce` 为 True 会报错。
- `seccomp_profile`：OCI 风格 JSON profile 路径。
- `no_network`：默认 True，利用 seccomp 阻断 socket 相关调用。
- `fs_mode`：
  - `none`：不做文件系统限制
  - `tmp`：切到临时目录（可选 `tmp_dir`）
  - `ro`：尝试将根目录 remount 为只读
- `fs_chroot`：在 `tmp` 模式下尝试 chroot（需要特权）

## 能力：CapabilitySpec

```python
CapabilitySpec(
    name: str,
    func_path: Optional[str] = None,      # spawn：pkg.mod:func
    cap_path: Optional[str] = None,       # 可选：pkg.mod:cap（实现 validate/budget/serialize）
    init_path: Optional[str] = None,      # 可选：pkg.mod:init
    close_path: Optional[str] = None,     # 可选：pkg.mod:close
    validator_path: Optional[str] = None, # 可选：pkg.mod:validator
    serializer_path: Optional[str] = None,# 可选：pkg.mod:serializer
    budget: BudgetSpec = BudgetSpec(),
    tokens_per_call: int = 0,
    tokens_per_byte: float = 0.0,
    arg_repr_limit: int = 400,
)
```

要点：

- `func_path`：spawn 模式必须提供（或 `cap_path`）。
- `cap_path`：若提供，指向具备 `validate/budget/serialize` 的可调用对象。
- `init_path`/`close_path`：能力生命周期钩子，`init` 在 worker 初始化调用，返回值会传给 `close(state)`。
- `validator_path`：入参校验
- `serializer_path`：返回值标准化（在 `cap.serialize` 之后）
- `tokens_per_call` / `tokens_per_byte`：按调用数 + 输出大小消耗 tokens。

## 能力预算：BudgetSpec

```python
BudgetSpec(
    max_calls: Optional[int] = 100,          # per-run
    max_total_ms: Optional[int] = 200,       # per-run
    max_qps: Optional[float] = None,         # rate limit
    max_bandwidth: Optional[int] = None,     # bytes/sec (bytes_out)
    max_ret_bytes: Optional[int] = 200_000,  # per-call
    max_call_ms: Optional[int] = None,       # per-call
    max_total_bytes: Optional[int] = None,   # per-run
    max_tokens: Optional[int] = None,        # per-exec scope
)
```

- `max_tokens`：若设置，会初始化 **exec scope** 的 token 上限。

## Scope：TokenScope / ScopeBundle

```python
TokenScope(tokens: Optional[int])

ScopeBundle(
    exec_scope: TokenScope,
    session_scope: TokenScope,
    tenant_scope: TokenScope,
)
```

消耗规则（内部实现）：

- 优先从 `exec`、再 `session`、再 `tenant` 中扣减
- `None` 表示该 scope 不限额
- 若三者都为 `None`，则 tokens 不受限

## 根对象：RootSpec

```python
RootSpec(
    name: str,
    target: str,         # "module" 或 "pkg.mod:obj"
    allow_tree: Dict[str, Any],
)
```

- `allow_tree`：SafeModuleProxy 白名单树。
  - 允许调用：`"sin": True`
  - 允许常量：`"pi": {"value": True}`

## 审计：AuditSinkSpec

```python
AuditSinkSpec(
    kind: str,            # "memory"|"stdout"|"file"|"webhook"|"otel"
    options: Dict[str, Any],
)
```

可用类型与 options：

- `memory`：无参数（仅 fork 模式直接传 AuditSink 实例时更常用）
- `stdout`：无参数（command runner 不支持）
- `file`：`{"path": "/tmp/audit.jsonl"}`
- `webhook`：`{"url": "https://...", "timeout_s": 1.0}`
- `otel`：`{"service_name": "sandboxed_env"}`

## 运行器：RunnerSpec

```python
RunnerSpec(
    kind: str = "local",          # local|command
    command: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
)
```

- `local`：默认，直接在子进程运行 worker
- `command`：通过外部命令运行 worker（容器/nsjail/firejail）

`command` runner 额外限制：

- 必须 `mode="spawn"`
- 必须使用 `root_specs`
- 不支持 `audit_sinks`
- 不支持 `stdout` 审计 sink

## 预设：PolicyPreset

```python
PolicyPreset(
    name: str,
    policy: Policy,
    root_specs: List[RootSpec] = [],
    description: str = "",
)
```

内置预设名称：

- `pure_compute`
- `compute_plus_math`
- `compute_plus_http`

## 返回结构：SandboxResult

```python
SandboxResult(
    ok: bool,
    result: Any = None,
    locals: Dict[str, Any] = {},
    error: Optional[ErrorInfo] = None,
    events: List[Event] = [],
    metrics: Metrics = Metrics(),
    stats: Any = None,
)
```

`stats` 在 v1.4 结构如下：

```python
{
  "user": <__stats__ 的 JSON-safe 值>,
  "token_scopes": {"exec": int|None, "session": int|None, "tenant": int|None}
}
```

## 常见配置示例

**1) 纯计算（无能力）**

```python
from sandboxed_env import SandboxedEnv, default_policy_v14

env = SandboxedEnv(default_policy_v14())
```

**2) 数学 + 能力 + tokens**

```python
from sandboxed_env import (
  SandboxedEnv, default_policy_v14, CapabilitySpec, BudgetSpec, RootSpec
)

env = SandboxedEnv(
  default_policy_v14(),
  mode="spawn",
  cap_specs=[
    CapabilitySpec(
      name="add",
      func_path="mycaps:add",
      budget=BudgetSpec(max_calls=10),
      tokens_per_call=2,
    )
  ],
  root_specs=[RootSpec(name="math", target="math", allow_tree={"sin": True, "pi": {"value": True}})],
  session_tokens=100,
)
```

**3) 外部 runner（nsjail）**

```python
import sys
from sandboxed_env import SandboxedEnv, command_runner, RootSpec

runner = command_runner(["nsjail", "--quiet", "--", sys.executable, "-m", "sandboxed_env.worker_entry"])
env = SandboxedEnv(mode="spawn", runner=runner,
                   root_specs=[RootSpec(name="math", target="math", allow_tree={"sin": True})])
```
