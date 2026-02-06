import unittest

from sandboxed_env import SandboxedEnv, PluginSpec

class PluginI18nTests(unittest.TestCase):
    def test_text_caps_plugin(self):
        env = SandboxedEnv(plugins=[
            PluginSpec(name="text", plugin_path="sandboxed_env.plugins.text_caps:TextCapsPlugin", config={"max_calls": 5}),
        ])
        r = env.execute("__result__ = upper('hello')")
        self.assertTrue(r.ok)
        self.assertEqual(r.result, "HELLO")

    def test_math_roots_plugin(self):
        env = SandboxedEnv(plugins=[
            PluginSpec(name="math", plugin_path="sandboxed_env.plugins.math_roots:MathRootsPlugin"),
        ])
        r = env.execute("__result__ = math.pi")
        self.assertTrue(r.ok)
        self.assertAlmostEqual(r.result, 3.141592653589793, places=6)

    def test_i18n_zh_cn(self):
        env = SandboxedEnv(locale="zh-CN")
        r = env.execute("import os")
        self.assertFalse(r.ok)
        self.assertEqual(r.error.message, "禁止 import")

if __name__ == "__main__":
    unittest.main()
