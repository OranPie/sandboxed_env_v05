from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Union

from .audit import AuditSink, AuditSinkSpec
from .capabilities import CapabilitySpec, load_dotted
from .policy import Policy
from .roots import RootSpec
from .runner import RunnerSpec

class Plugin(Protocol):
    name: str

    def setup(self, ctx: "PluginContext") -> None:
        ...

@dataclass
class PluginContext:
    policy: Policy
    cap_specs: List[CapabilitySpec]
    cap_registry: Dict[str, Callable[..., Any]]
    roots: Dict[str, Any]
    root_specs: List[RootSpec]
    audit_sinks: List[AuditSink]
    audit_sink_specs: List[AuditSinkSpec]
    runner: RunnerSpec
    locale: str

@dataclass(frozen=True)
class PluginSpec:
    name: str
    plugin_path: str
    config: Optional[Any] = None
    priority: int = 0

PluginLike = Union[Plugin, PluginSpec]


def apply_plugins(plugins: Iterable[PluginLike], ctx: PluginContext) -> None:
    resolved = [_resolve_plugin(p) for p in plugins]
    resolved.sort(key=lambda x: x[0])
    for _, plugin in resolved:
        plugin.setup(ctx)


def _resolve_plugin(plugin: PluginLike) -> tuple[int, Plugin]:
    if isinstance(plugin, PluginSpec):
        factory = load_dotted(plugin.plugin_path)
        inst = _instantiate(factory, plugin.config)
        if not hasattr(inst, "setup"):
            raise ValueError(f"plugin '{plugin.name}' does not implement setup(ctx)")
        if not getattr(inst, "name", None):
            setattr(inst, "name", plugin.name)
        return plugin.priority, inst
    if not hasattr(plugin, "setup"):
        raise ValueError("plugin object missing setup(ctx)")
    return 0, plugin


def _instantiate(factory: Any, config: Optional[Any]) -> Any:
    if not callable(factory):
        return factory
    if config is None:
        return factory()
    if isinstance(config, dict):
        try:
            return factory(**config)
        except TypeError:
            return factory(config)
    return factory(config)
