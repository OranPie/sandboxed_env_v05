# SandboxedEnv v1.4

一个实用的、基于能力（capability）的 Python 沙箱。

## 提供的能力

- **AST 策略**：禁止 `import`、禁止双下划线名称、禁止任意属性访问
- **函数白名单**：仅允许调用白名单中的 `Name(...)`
- **可选的 `root.attr` 白名单**：仅允许白名单中的 `root.attr`
- **安全根对象**：`SafeModuleProxy` 仅暴露白名单属性
- **能力列表**：显式列出，每个能力都有预算（`BudgetSpec`）+ 审计事件
- **进程隔离**：在子进程中运行代码，带超时
- **步数预算**：使用 `sys.settrace` 强制执行步数限制
- **尽力而为的 rlimits**（Linux）：CPU、内存（AS）、打开文件数
- **输入深度冻结**：防止沙箱修改调用方传入对象
- **JSON 安全输出**：仅返回 JSON-ish 值，并进行截断
- **事件流**：stdout/stderr/能力调用以带时间戳事件返回
- **策略预设**：pure_compute、compute_plus_math、compute_plus_http
- **确定性选项**：随机种子、可选伪时间、可选浮点格式化
- **返回约定**：__result__、__events__、__stats__（另含 token scopes）
- **更好的错误**：带行/列的代码片段 + 光标
- **默认可安全 spawn**：默认使用点路径能力（Windows 友好）
- **运行器选项**：本地进程或外部容器/nsjail/firejail 命令
- **能力框架**：validate/budget/serialize 钩子、预算、scope、审计 sink
- **更智能的静态检查**：循环迭代限制 + 可疑分配检测
- **类型约束**：可选输入/输出 schema 校验
- **模块代理加固**：仅可调用属性、返回只读包装
- **OS 加固**：seccomp profile、默认禁网、文件系统沙箱（尽力而为）

## 安装 / 目录结构

该仓库是纯 Python 包：

- `sandboxed_env_v05/` 包
- `examples/basic_demo.py`

可运行示例：

```bash
python -m sandboxed_env.examples.basic_demo
```

（或将此包目录加入 PYTHONPATH。）

## 快速使用（Unix 推荐 fork 模式）

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

注意：v1.4 默认使用 `mode="spawn"` 以兼容 Windows。使用 spawn-safe 模式时，
能力必须通过点路径注册。

## 策略预设

```python
from sandboxed_env import get_policy_preset, SandboxedEnv

preset = get_policy_preset("compute_plus_math")
env = SandboxedEnv(preset.policy, root_specs=preset.root_specs)
```

## 返回约定

在沙箱代码内可设置：

```python
__result__ = {"value": 123}
__events__ = [{"type": "user", "data": {"note": "hello"}}]
__stats__ = {"items": 42}
```

这些会体现在 `SandboxResult.result`、`SandboxResult.events`（追加），
以及 `SandboxResult.stats["user"]` 中。Token scopes 在 `SandboxResult.stats["token_scopes"]` 中。

## 升级说明（v1.4）

- `SandboxResult.stats` 现在返回包含 `user` 和 `token_scopes` 的 dict（不再直接返回原始 `__stats__`）。
- Token scopes 包括 `exec`、`session`、`tenant`；可通过 `SandboxedEnv` 持久化 session/tenant scope。

## 确定性选项

```python
from sandboxed_env import Policy, DeterminismConfig, default_policy_v14

policy = default_policy_v14()
policy = Policy(**{
    **policy.__dict__,
    "determinism": DeterminismConfig(seed=0, fake_time=0.0, time_step=0.0, float_format=".6g"),
})
```

## 类型约束（schema）

你可以使用 JSON-schema 风格的 dict 约束输入/输出：

```python
policy = Policy(**{
    **policy.__dict__,
    "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
    "output_schema": {"type": "object", "properties": {"x": {"type": "integer"}}},
})
```

Schema 会基于 JSON-safe 的输入/输出进行校验。

## Schema 缓存与格式

Schema 校验使用基于 JSON 序列化的小缓存以降低开销。
支持的字符串格式包括 `email`、`uuid`，以及正则 `pattern`。

## Spawn 模式（可移植）

v1.4 默认是 spawn 模式。该模式下能力必须可以通过点路径导入：

```python
CapabilitySpec(name="add", func_path="mycaps:add")
```

根对象可通过 `RootSpec` 提供：

```python
from sandboxed_env import RootSpec

RootSpec(name="math", target="math", allow_tree={"sin": True, "pi": {"value": True}})
```

然后：

```python
env = SandboxedEnv(mode="spawn", cap_specs=[...], root_specs=[...])
```

## 更智能的静态检查

默认限制循环迭代对象为 `range`/`list`/`tuple`（字面量或调用，可在 `Policy` 配置）。
AST 检查器也会阻止可疑的常量折叠分配（例如巨大的 `[*] * N`）。

## 模块代理加固

`SafeModuleProxy` 现在只暴露可调用属性，并将返回值包装为只读。常量需要在 allow-tree 中使用
`{"value": True}`：

```python
SafeModuleProxy(math, allow={"sin": True, "pi": {"value": True}}, name="math")
```

## OS 加固（seccomp / 禁网 / 文件系统）

Linux 上可通过 `OSSandboxConfig` 配置尽力而为的 OS 沙箱：

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

如果 seccomp 不可用，除非 `seccomp_enforce=True`，否则会跳过强制。
seccomp profile 期望是最小化的 OCI 风格 JSON（defaultAction + syscalls names）。

校验 profile：

```bash
python -m sandboxed_env.examples.validate_seccomp examples/seccomp_minimal.json
```

将额外 syscalls 合并到基础 profile：

```bash
python -m sandboxed_env.examples.merge_seccomp examples/seccomp_minimal.json openat stat
```

## 能力框架（v1.4）

每个能力可提供：
- `validate(args, kwargs)` 输入校验
- `budget(cost)` 自定义预算检查
- `serialize(ret)` 输出规范化

可通过 `cap_path="pkg.mod:cap"` 加载完整能力对象（必须可调用并实现上述钩子）。

内置预算在 `BudgetSpec` 中，包含 per-call、per-run、QPS、带宽与大小限制：

```python
from sandboxed_env import CapabilitySpec, BudgetSpec

cap = CapabilitySpec(
    name="http_get",
    func_path="mycaps:http_get",
    budget=BudgetSpec(max_calls=20, max_qps=2.0, max_bandwidth=50_000, max_ret_bytes=20_000),
    tokens_per_byte=1.0,
)
```

每次执行的 token 在执行时提供：

```python
r = env.execute("...", tokens=1000)

# 可选：跨运行跟踪 session/tenant tokens
env = SandboxedEnv(session_tokens=10_000, tenant_tokens=1_000_000)
```

## 审计 sinks

审计 sinks 可插拔，支持内存、文件、stdout、OpenTelemetry 或 webhook。

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

说明：token scopes 暴露在 `SandboxResult.stats["token_scopes"]` 中，必要时可由宿主端与审计事件一并记录。

## 模糊测试

运行基础 fuzz harness（随机 AST + 回归 payloads）：

```bash
python -m sandboxed_env.examples.fuzz_harness
```

## 运行器选项（container / nsjail / firejail）

你可以通过提供一个命令，将 worker 放到外部 runner 中执行：

```python
import sys
from sandboxed_env import SandboxedEnv, command_runner

runner = command_runner([
    "nsjail", "--quiet", "--", sys.executable, "-m", "sandboxed_env.worker_entry"
])

env = SandboxedEnv(mode="spawn", runner=runner, cap_specs=[...], root_specs=[...])
```

注意：`spawn` 要求传入 worker 的对象可被 pickle。优先使用 `RootSpec` 在 worker 内重建 roots。

## 安全说明

- 这是一个结合策略 + 进程隔离的**实用**沙箱。若面对强对抗性代码，建议增加容器化/seccomp。
- 保持 `attr_allowlist` 尽量小。优先以能力形式暴露函数，而非允许任意属性访问。
- 所有 I/O 都应通过具备 validator 和 budget 的能力进行。
