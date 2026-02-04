from __future__ import annotations
import json
import sys

from .env import _run_worker
from .roots import build_roots_from_specs
from .wire import policy_from_dict, cap_specs_from_list, root_specs_from_list
from .audit import audit_sink_specs_from_list

def main() -> int:
    raw = sys.stdin.read()
    if not raw:
        return 2
    payload = json.loads(raw)
    policy = policy_from_dict(payload["policy"])
    cap_specs = cap_specs_from_list(payload.get("cap_specs") or [])
    root_specs = root_specs_from_list(payload.get("root_specs") or [])
    audit_specs = audit_sink_specs_from_list(payload.get("audit_sink_specs") or [])
    roots = {}
    if root_specs:
        roots, _ = build_roots_from_specs(root_specs)

    out = _run_worker(
        code=payload["code"],
        policy=policy,
        cap_specs=cap_specs,
        roots=roots,
        inputs=payload.get("inputs"),
        mode=payload.get("mode", "spawn"),
        cap_registry=None,
        root_specs=root_specs,
        tokens=payload.get("tokens"),
        session_tokens=payload.get("session_tokens"),
        tenant_tokens=payload.get("tenant_tokens"),
        audit_sinks=None,
        audit_sink_specs=audit_specs,
    )
    json.dump(out, sys.stdout)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
