import math
import unittest

from sandboxed_env import (
    SandboxedEnv,
    Policy,
    default_policy_v14,
    CapabilitySpec,
    BudgetSpec,
    RootSpec,
    SafeModuleProxy,
)

CAP_ADD = "sandboxed_env.tests.caps:add"
CAP_BIG = "sandboxed_env.tests.caps:return_big"

def _env_with_caps(*caps, policy=None):
    policy = policy or default_policy_v14()
    return SandboxedEnv(
        policy,
        mode="spawn",
        cap_specs=list(caps),
        root_specs=[RootSpec(name="math", target="math", allow_tree={"sin": True, "pi": {"value": True}})],
    )

class SandboxTests(unittest.TestCase):
    def test_basic_result(self):
        env = _env_with_caps(CapabilitySpec(name="add", func_path=CAP_ADD))
        r = env.execute("__result__ = add(1, 2)")
        self.assertTrue(r.ok)
        self.assertEqual(r.result, 3)

    def test_events_append(self):
        env = _env_with_caps(CapabilitySpec(name="add", func_path=CAP_ADD))
        r = env.execute("__events__ = [{'type':'user','data':{'x':1}}]")
        self.assertTrue(r.ok)
        self.assertTrue(any(e.type == "user" and e.data.get("x") == 1 for e in r.events))

    def test_stats_field(self):
        env = _env_with_caps()
        r = env.execute("__stats__ = {'n': 5}")
        self.assertTrue(r.ok)
        self.assertEqual(r.stats.get("user"), {"n": 5})
        self.assertIn("token_scopes", r.stats)

    def test_stats_user_none(self):
        env = _env_with_caps()
        r = env.execute("__result__ = 1")
        self.assertTrue(r.ok)
        self.assertIn("user", r.stats)
        self.assertIsNone(r.stats.get("user"))
        self.assertIn("token_scopes", r.stats)
        self.assertIsNone(r.stats["token_scopes"]["exec"])

    def test_schema_input_ok(self):
        policy = default_policy_v14()
        policy = Policy(**{
            **policy.__dict__,
            "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
        })
        env = _env_with_caps(policy=policy)
        r = env.execute("__result__ = 1", inputs={"x": 3})
        self.assertTrue(r.ok)

    def test_schema_input_fail(self):
        policy = default_policy_v14()
        policy = Policy(**{
            **policy.__dict__,
            "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
        })
        env = _env_with_caps(policy=policy)
        r = env.execute("__result__ = 1", inputs={"x": "nope"})
        self.assertFalse(r.ok)
        self.assertEqual(r.error.stage, "schema")

    def test_schema_output_fail(self):
        policy = default_policy_v14()
        policy = Policy(**{
            **policy.__dict__,
            "output_schema": {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
        })
        env = _env_with_caps(policy=policy)
        r = env.execute("__result__ = {'x': 'nope'}")
        self.assertFalse(r.ok)
        self.assertEqual(r.error.stage, "schema")

    def test_schema_format_email(self):
        policy = default_policy_v14()
        policy = Policy(**{
            **policy.__dict__,
            "output_schema": {"type": "string", "format": "email"},
        })
        env = _env_with_caps(policy=policy)
        r = env.execute("__result__ = 'a@b.com'")
        self.assertTrue(r.ok)
        r2 = env.execute("__result__ = 'nope'")
        self.assertFalse(r2.ok)
        self.assertEqual(r2.error.stage, "schema")

    def test_schema_pattern(self):
        policy = default_policy_v14()
        policy = Policy(**{
            **policy.__dict__,
            "output_schema": {"type": "string", "pattern": "^a.+z$"},
        })
        env = _env_with_caps(policy=policy)
        r = env.execute("__result__ = 'abcz'")
        self.assertTrue(r.ok)
        r2 = env.execute("__result__ = 'ab'")
        self.assertFalse(r2.ok)
        self.assertEqual(r2.error.stage, "schema")

    def test_loop_iterable_restriction_block(self):
        env = _env_with_caps()
        r = env.execute("x = 3\nfor i in x:\n    pass\n__result__ = 1")
        self.assertFalse(r.ok)
        self.assertEqual(r.error.stage, "policy")

    def test_loop_iterable_allow_range(self):
        env = _env_with_caps()
        r = env.execute("s = 0\nfor i in range(3):\n    s = s + i\n__result__ = s")
        self.assertTrue(r.ok)
        self.assertEqual(r.result, 3)

    def test_suspicious_allocation_block(self):
        env = _env_with_caps()
        r = env.execute("x = list(range(2000000))\n__result__ = 1")
        self.assertFalse(r.ok)
        self.assertEqual(r.error.stage, "policy")

    def test_safe_module_proxy_callable_only(self):
        proxy = SafeModuleProxy(math, allow={"pi": True}, name="math")
        with self.assertRaises(AttributeError):
            _ = proxy.pi
        proxy2 = SafeModuleProxy(math, allow={"pi": {"value": True}}, name="math")
        self.assertEqual(proxy2.pi, math.pi)

    def test_capability_budget_max_calls(self):
        cap = CapabilitySpec(name="add", func_path=CAP_ADD, budget=BudgetSpec(max_calls=1))
        env = _env_with_caps(cap)
        r = env.execute("x = add(1,2)\ny = add(2,3)\n__result__ = x + y")
        self.assertFalse(r.ok)
        self.assertEqual(r.error.type, "CapabilityBudgetError")

    def test_token_scope(self):
        cap = CapabilitySpec(name="add", func_path=CAP_ADD, budget=BudgetSpec(), tokens_per_call=2)
        env = _env_with_caps(cap)
        r = env.execute("x = add(1,2)\n__result__ = x", tokens=1)
        self.assertFalse(r.ok)
        self.assertEqual(r.error.type, "CapabilityBudgetError")

    def test_token_scopes_exec_decrement(self):
        cap = CapabilitySpec(name="add", func_path=CAP_ADD, budget=BudgetSpec(), tokens_per_call=2)
        env = _env_with_caps(cap)
        r = env.execute("x = add(1,2)\n__result__ = x", tokens=5)
        self.assertTrue(r.ok)
        self.assertEqual(r.stats["token_scopes"]["exec"], 3)

    def test_token_scopes_session_used(self):
        cap = CapabilitySpec(name="add", func_path=CAP_ADD, budget=BudgetSpec(), tokens_per_call=2)
        env = SandboxedEnv(default_policy_v14(), mode="spawn", cap_specs=[cap], session_tokens=5, tenant_tokens=0)
        r = env.execute("x = add(1,2)\n__result__ = x", tokens=1)
        self.assertTrue(r.ok)
        self.assertEqual(r.stats["token_scopes"]["exec"], 1)
        self.assertEqual(r.stats["token_scopes"]["session"], 3)

    def test_token_scopes_tenant_used(self):
        cap = CapabilitySpec(name="add", func_path=CAP_ADD, budget=BudgetSpec(), tokens_per_call=2)
        env = SandboxedEnv(default_policy_v14(), mode="spawn", cap_specs=[cap], session_tokens=1, tenant_tokens=4)
        r = env.execute("x = add(1,2)\n__result__ = x", tokens=1)
        self.assertTrue(r.ok)
        self.assertEqual(r.stats["token_scopes"]["exec"], 1)
        self.assertEqual(r.stats["token_scopes"]["session"], 1)
        self.assertEqual(r.stats["token_scopes"]["tenant"], 2)

    def test_session_tokens_persist(self):
        cap = CapabilitySpec(name="add", func_path=CAP_ADD, budget=BudgetSpec(), tokens_per_call=2)
        env = SandboxedEnv(default_policy_v14(), mode="spawn", cap_specs=[cap], session_tokens=3, tenant_tokens=0)
        r1 = env.execute("x = add(1,2)\n__result__ = x", tokens=0)
        self.assertTrue(r1.ok)
        self.assertEqual(env.session_tokens, 1)
        r2 = env.execute("x = add(1,2)\n__result__ = x", tokens=0)
        self.assertFalse(r2.ok)
        self.assertEqual(r2.error.type, "CapabilityBudgetError")

    def test_session_tokens_used_when_exec_unlimited(self):
        cap = CapabilitySpec(name="add", func_path=CAP_ADD, budget=BudgetSpec(), tokens_per_call=2)
        env = SandboxedEnv(default_policy_v14(), mode="spawn", cap_specs=[cap], session_tokens=5, tenant_tokens=0)
        r = env.execute("x = add(1,2)\n__result__ = x")
        self.assertTrue(r.ok)
        self.assertEqual(r.stats["token_scopes"]["session"], 3)

    def test_token_scopes_default_none(self):
        env = _env_with_caps()
        r = env.execute("__result__ = 1")
        self.assertTrue(r.ok)
        self.assertIsNone(r.stats["token_scopes"]["exec"])
        self.assertIsNone(r.stats["token_scopes"]["session"])
        self.assertIsNone(r.stats["token_scopes"]["tenant"])

    def test_capability_max_tokens_default_exec_scope(self):
        cap = CapabilitySpec(name="add", func_path=CAP_ADD, budget=BudgetSpec(max_tokens=1), tokens_per_call=2)
        env = _env_with_caps(cap)
        r = env.execute("x = add(1,2)\n__result__ = x")
        self.assertFalse(r.ok)
        self.assertEqual(r.error.type, "CapabilityBudgetError")

    def test_init_close_hooks(self):
        import os
        import tempfile
        cap = CapabilitySpec(
            name="add",
            func_path=CAP_ADD,
            init_path="sandboxed_env.tests.caps:init_counter",
            close_path="sandboxed_env.tests.caps:close_counter",
        )
        env = _env_with_caps(cap)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "cap_close.txt")
            os.environ["CAP_CLOSE_PATH"] = path
            r = env.execute("__result__ = 1")
            self.assertTrue(r.ok)
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            self.assertIn("init", data)
            self.assertIn("close", data)
        os.environ.pop("CAP_CLOSE_PATH", None)

    def test_error_excerpt_caret(self):
        env = _env_with_caps()
        r = env.execute("x =\n__result__ = 1")
        self.assertFalse(r.ok)
        self.assertEqual(r.error.stage, "parse")
        self.assertIsNotNone(r.error.excerpt)
        self.assertIsNotNone(r.error.caret)

if __name__ == "__main__":
    unittest.main()
