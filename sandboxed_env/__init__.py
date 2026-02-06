"""SandboxedEnv v1.4

A practical Python sandbox design using:
- AST policy checks (no import, no dunder, controlled calls)
- Capability allowlist with per-capability budgets + audit
- Optional root.attr allowlist with SafeModuleProxy
- Subprocess isolation + timeout + step budget + best-effort rlimits (Linux)
- Deep-freeze inputs + JSON-safe outputs
- Event stream: stdout/stderr/capability calls are returned as timestamped events
"""

from .env import SandboxedEnv
from .policy import Policy, default_policy_v05, default_policy_v06, default_policy_v07, default_policy_v08, default_policy_v09, default_policy_v10, default_policy_v11, default_policy_v12, default_policy_v13, default_policy_v14, DeterminismConfig, OSSandboxConfig
from .capabilities import CapabilitySpec, CapabilityCost, BudgetSpec, TokenScope, ScopeBundle, Capability
from .roots import RootSpec
from .proxies import SafeModuleProxy
from .result import SandboxResult, ErrorInfo, Event, Metrics
from .presets import PolicyPreset, policy_presets, get_policy_preset
from .runner import RunnerSpec, local_runner, command_runner
from .audit import AuditSink, AuditSinkSpec, build_audit_sinks, audit_sink_specs_from_list, audit_sink_specs_to_list
from .schema import SchemaError, validate_schema, validate_schema_cached
from .i18n import register_bundle, translate, translate_error, translate_message
from .plugin_system import PluginSpec, PluginContext, apply_plugins

__all__ = [
    "SandboxedEnv",
    "Policy",
    "default_policy_v05",
    "default_policy_v06",
    "default_policy_v07",
    "default_policy_v08",
    "default_policy_v09",
    "default_policy_v10",
    "default_policy_v11",
    "default_policy_v12",
    "default_policy_v13",
    "default_policy_v14",
    "DeterminismConfig",
    "OSSandboxConfig",
    "CapabilitySpec",
    "CapabilityCost",
    "BudgetSpec",
    "TokenScope",
    "ScopeBundle",
    "Capability",
    "RootSpec",
    "SafeModuleProxy",
    "SandboxResult",
    "ErrorInfo",
    "Event",
    "Metrics",
    "PolicyPreset",
    "policy_presets",
    "get_policy_preset",
    "RunnerSpec",
    "local_runner",
    "command_runner",
    "AuditSink",
    "AuditSinkSpec",
    "build_audit_sinks",
    "audit_sink_specs_from_list",
    "audit_sink_specs_to_list",
    "SchemaError",
    "validate_schema",
    "validate_schema_cached",
    "register_bundle",
    "translate",
    "translate_error",
    "translate_message",
    "PluginSpec",
    "PluginContext",
    "apply_plugins",
]
