from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import json
import os
import sys
import tempfile
import subprocess

from .policy import OSSandboxConfig
from .errors import SandboxError

ALLOWED_ACTIONS = {
    "SCMP_ACT_ALLOW",
    "SCMP_ACT_ERRNO",
    "SCMP_ACT_KILL",
    "SCMP_ACT_TRAP",
    "SCMP_ACT_LOG",
    "SCMP_ACT_KILL_PROCESS",
    "SCMP_ACT_KILL_THREAD",
}

def _load_seccomp() -> Optional[object]:
    try:
        import seccomp  # type: ignore
        return seccomp
    except Exception:
        return None

def _action_from_str(seccomp_mod, action: str):
    return getattr(seccomp_mod, action, None)

def validate_seccomp_profile(profile: dict) -> None:
    if not isinstance(profile, dict):
        raise SandboxError("seccomp profile must be a dict")
    if "defaultAction" not in profile:
        raise SandboxError("seccomp profile missing defaultAction")
    if profile["defaultAction"] not in ALLOWED_ACTIONS:
        raise SandboxError("seccomp defaultAction invalid")
    syscalls = profile.get("syscalls")
    if not isinstance(syscalls, list):
        raise SandboxError("seccomp syscalls must be a list")
    for rule in syscalls:
        if not isinstance(rule, dict):
            raise SandboxError("seccomp syscall rule must be dict")
        action = rule.get("action", "SCMP_ACT_ALLOW")
        if action not in ALLOWED_ACTIONS:
            raise SandboxError("seccomp syscall action invalid")
        names = rule.get("names")
        if not isinstance(names, list) or not names:
            raise SandboxError("seccomp syscall names must be list")
        for n in names:
            if not isinstance(n, str) or not n:
                raise SandboxError("seccomp syscall name invalid")

def merge_allow_syscalls(profile: dict, names: list[str]) -> dict:
    validate_seccomp_profile(profile)
    allow_rule = None
    for rule in profile.get("syscalls", []):
        if rule.get("action", "SCMP_ACT_ALLOW") == "SCMP_ACT_ALLOW":
            allow_rule = rule
            break
    if allow_rule is None:
        allow_rule = {"names": [], "action": "SCMP_ACT_ALLOW"}
        profile.setdefault("syscalls", []).append(allow_rule)
    merged = set(allow_rule.get("names") or [])
    for n in names:
        if n:
            merged.add(n)
    allow_rule["names"] = sorted(merged)
    validate_seccomp_profile(profile)
    return profile

def _apply_seccomp_no_network(flt, seccomp_mod, *, enforce: bool) -> None:
    deny = seccomp_mod.SCMP_ACT_ERRNO(13)  # EACCES
    for name in [
        "socket", "connect", "accept", "accept4", "bind", "listen",
        "sendto", "recvfrom", "sendmsg", "recvmsg", "getsockopt", "setsockopt",
        "getpeername", "getsockname", "shutdown",
    ]:
        try:
            flt.add_rule(deny, name)
        except Exception:
            if enforce:
                raise

def apply_seccomp(cfg: OSSandboxConfig, *, profile: Optional[dict] = None) -> None:
    seccomp_mod = _load_seccomp()
    if seccomp_mod is None:
        if cfg.seccomp_enforce:
            raise SandboxError("seccomp module not available")
        return
    prof = profile
    if prof is None and cfg.seccomp_profile:
        with open(cfg.seccomp_profile, "r", encoding="utf-8") as f:
            prof = json.load(f)
    if prof:
        validate_seccomp_profile(prof)
        default_action = _action_from_str(seccomp_mod, prof.get("defaultAction", "SCMP_ACT_ALLOW"))
        if default_action is None:
            raise SandboxError("invalid seccomp defaultAction")
        flt = seccomp_mod.SyscallFilter(defaction=default_action)
        for rule in prof.get("syscalls", []):
            action = _action_from_str(seccomp_mod, rule.get("action", "SCMP_ACT_ALLOW"))
            if action is None:
                raise SandboxError("invalid seccomp action")
            for name in rule.get("names", []):
                try:
                    flt.add_rule(action, name)
                except Exception:
                    if cfg.seccomp_enforce:
                        raise
    else:
        flt = seccomp_mod.SyscallFilter(defaction=seccomp_mod.SCMP_ACT_ALLOW)

    if cfg.no_network:
        _apply_seccomp_no_network(flt, seccomp_mod, enforce=cfg.seccomp_enforce)
    flt.load()

def apply_fs_sandbox(cfg: OSSandboxConfig) -> None:
    mode = cfg.fs_mode
    if mode == "none":
        return
    if mode == "tmp":
        tmp = cfg.tmp_dir or tempfile.mkdtemp(prefix="sandbox_")
        os.environ["TMPDIR"] = tmp
        os.environ["TEMP"] = tmp
        os.environ["TMP"] = tmp
        os.chdir(tmp)
        if cfg.fs_chroot:
            try:
                os.chroot(tmp)
                os.chdir("/")
            except Exception:
                if cfg.fs_enforce:
                    raise SandboxError("fs_chroot failed")
    elif mode == "ro":
        try:
            subprocess.run(["/bin/mount", "-o", "remount,ro", "/"], check=True)
        except Exception:
            if cfg.fs_enforce:
                raise SandboxError("remount ro failed")
    else:
        if cfg.fs_enforce:
            raise SandboxError(f"unknown fs_mode: {mode}")

def apply_os_sandbox(cfg: Optional[OSSandboxConfig]) -> None:
    if cfg is None:
        return
    validate_os_sandbox_config(cfg)
    if not sys.platform.startswith("linux"):
        if cfg.seccomp_enforce or cfg.fs_enforce:
            raise SandboxError("OS sandbox requires Linux support")
        return

    prof = None
    if cfg.seccomp_profile and cfg.fs_chroot:
        with open(cfg.seccomp_profile, "r", encoding="utf-8") as f:
            prof = json.load(f)
    apply_fs_sandbox(cfg)
    if cfg.seccomp_profile or cfg.no_network:
        apply_seccomp(cfg, profile=prof)

def validate_os_sandbox_config(cfg: OSSandboxConfig) -> None:
    if cfg.fs_mode not in ("none", "tmp", "ro"):
        raise SandboxError(f"unknown fs_mode: {cfg.fs_mode}")
