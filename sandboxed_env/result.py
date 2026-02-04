from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List

@dataclass
class ErrorInfo:
    stage: str                 # parse|policy|runtime|timeout|worker
    type: str
    message: str
    lineno: Optional[int] = None
    col: Optional[int] = None
    excerpt: Optional[str] = None
    caret: Optional[str] = None
    tb: Optional[str] = None   # trimmed traceback (runtime only)

@dataclass
class Metrics:
    wall_ms: int = 0
    ast_nodes: int = 0
    steps: int = 0
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    user_ms: int = 0
    sys_ms: int = 0
    max_rss_kb: int = 0
    cap_calls: Dict[str, int] = field(default_factory=dict)
    cap_ms: Dict[str, int] = field(default_factory=dict)
    cap_bytes_out: Dict[str, int] = field(default_factory=dict)
    cap_bytes_in: Dict[str, int] = field(default_factory=dict)

@dataclass
class Event:
    ts_ms: int
    type: str                  # stdout|stderr|cap|info
    data: Dict[str, Any]

@dataclass
class SandboxResult:
    ok: bool
    result: Any = None
    locals: Dict[str, Any] = field(default_factory=dict)
    error: Optional[ErrorInfo] = None
    events: List[Event] = field(default_factory=list)
    metrics: Metrics = field(default_factory=Metrics)
    stats: Any = None
