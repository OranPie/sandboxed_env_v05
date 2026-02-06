import importlib.util
import unittest

from sandboxed_env import SandboxedEnv, PluginSpec


class ThirdPartyPluginTests(unittest.TestCase):
    def test_numpy_caps(self):
        if not importlib.util.find_spec("numpy"):
            self.skipTest("numpy not installed")
        env = SandboxedEnv(plugins=[
            PluginSpec(name="numpy", plugin_path="sandboxed_env.plugins.numpy_caps:NumpyCapsPlugin"),
        ])
        r = env.execute("__result__ = np_sum([1,2,3])")
        self.assertTrue(r.ok)
        self.assertEqual(r.result, 6.0)

    def test_pandas_caps(self):
        if not importlib.util.find_spec("pandas"):
            self.skipTest("pandas not installed")
        env = SandboxedEnv(plugins=[
            PluginSpec(name="pandas", plugin_path="sandboxed_env.plugins.pandas_caps:PandasCapsPlugin"),
        ])
        code = """
csv = 'a,b\n1,2\n3,4\n'
__result__ = pd_csv_to_records(csv)
"""
        r = env.execute(code)
        self.assertTrue(r.ok)
        self.assertEqual(r.result, [{"a": 1, "b": 2}, {"a": 3, "b": 4}])

    def test_dateutil_caps(self):
        if not importlib.util.find_spec("dateutil"):
            self.skipTest("dateutil not installed")
        env = SandboxedEnv(plugins=[
            PluginSpec(name="dateutil", plugin_path="sandboxed_env.plugins.dateutil_caps:DateutilCapsPlugin"),
        ])
        r = env.execute("__result__ = parse_date('2024-01-02T03:04:05Z')")
        self.assertTrue(r.ok)
        self.assertEqual(r.result, "2024-01-02")


if __name__ == "__main__":
    unittest.main()
