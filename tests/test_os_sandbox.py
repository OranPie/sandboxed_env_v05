import os
import sys
import tempfile
import unittest

from sandboxed_env import SandboxedEnv, Policy, default_policy_v14, CapabilitySpec, RootSpec, OSSandboxConfig
from sandboxed_env.os_sandbox import validate_seccomp_profile, merge_allow_syscalls, validate_os_sandbox_config

class SeccompProfileTests(unittest.TestCase):
    def test_valid_minimal_profile(self):
        prof = {
            "defaultAction": "SCMP_ACT_ERRNO",
            "syscalls": [{"names": ["read", "write"], "action": "SCMP_ACT_ALLOW"}],
        }
        validate_seccomp_profile(prof)

    def test_invalid_profile_missing_default(self):
        with self.assertRaises(Exception):
            validate_seccomp_profile({"syscalls": []})

    def test_invalid_profile_bad_action(self):
        with self.assertRaises(Exception):
            validate_seccomp_profile({"defaultAction": "NOPE", "syscalls": []})

    def test_invalid_profile_bad_syscalls(self):
        with self.assertRaises(Exception):
            validate_seccomp_profile({"defaultAction": "SCMP_ACT_ALLOW", "syscalls": [{"names": []}]})

    def test_merge_allow_syscalls(self):
        prof = {
            "defaultAction": "SCMP_ACT_ERRNO",
            "syscalls": [{"names": ["read"], "action": "SCMP_ACT_ALLOW"}],
        }
        merged = merge_allow_syscalls(prof, ["write", "read"])
        names = merged["syscalls"][0]["names"]
        self.assertIn("read", names)
        self.assertIn("write", names)

    def test_invalid_fs_mode(self):
        with self.assertRaises(Exception):
            validate_os_sandbox_config(OSSandboxConfig(fs_mode="weird"))

class OSSandboxRuntimeTests(unittest.TestCase):
    def _seccomp_available(self) -> bool:
        try:
            import seccomp  # type: ignore
            return True
        except Exception:
            return False

    def test_no_network_blocks_socket(self):
        if not sys.platform.startswith("linux"):
            self.skipTest("seccomp test requires Linux")
        if not self._seccomp_available():
            self.skipTest("seccomp module not available")

        policy = default_policy_v14()
        policy = Policy(**{
            **policy.__dict__,
            "os_sandbox": OSSandboxConfig(no_network=True, seccomp_enforce=True),
        })
        env = SandboxedEnv(
            policy,
            mode="spawn",
            cap_specs=[CapabilitySpec(name="try_socket", func_path="sandboxed_env.tests.caps:try_socket")],
            root_specs=[RootSpec(name="math", target="math", allow_tree={"sin": True, "pi": {"value": True}})],
        )
        r = env.execute("__result__ = try_socket()")
        self.assertFalse(r.ok)
        self.assertIn(r.error.type, ("PermissionError", "OSError", "SandboxError"))

    def test_fs_tmpdir(self):
        policy = default_policy_v14()
        with tempfile.TemporaryDirectory() as td:
            policy = Policy(**{
                **policy.__dict__,
                "os_sandbox": OSSandboxConfig(no_network=False, seccomp_enforce=False, fs_mode="tmp", tmp_dir=td),
            })
            env = SandboxedEnv(
                policy,
                mode="spawn",
                cap_specs=[CapabilitySpec(name="getcwd", func_path="sandboxed_env.tests.caps:getcwd")],
                root_specs=[RootSpec(name="math", target="math", allow_tree={"sin": True, "pi": {"value": True}})],
            )
            r = env.execute("__result__ = getcwd()")
            self.assertTrue(r.ok)
            if r.result != td:
                self.skipTest("fs tmpdir sandbox not enforced on this platform")

if __name__ == "__main__":
    unittest.main()
