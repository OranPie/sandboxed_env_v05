from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass(frozen=True)
class RunnerSpec:
    kind: str = "local"  # local|command
    command: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None

def local_runner() -> RunnerSpec:
    return RunnerSpec(kind="local")

def command_runner(command: List[str], *, env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None) -> RunnerSpec:
    return RunnerSpec(kind="command", command=command, env=env, cwd=cwd)
