import math
import multiprocessing as mp
from sandboxed_env import SandboxedEnv, default_policy_v14, Policy, CapabilitySpec, RootSpec, BudgetSpec

def main() -> None:
    # Example 1: spawn mode with RootSpec + dotted func_path capability
    policy = default_policy_v14()
    policy = Policy(**{
        **policy.__dict__,
        "attr_allowlist": {"math": {"sin", "cos", "pi"}},
    })

    env = SandboxedEnv(
        policy,
        mode="spawn",
        cap_specs=[CapabilitySpec(name="add", func_path="examples.caps:add", budget=BudgetSpec(max_calls=20, max_total_ms=50, max_ret_bytes=5000))],
        root_specs=[RootSpec(name="math", target="math", allow_tree={"sin": True, "cos": True, "pi": {"value": True}})],
    )

    r = env.execute("""
x = add(1, 2)
y = math.sin(1.0) + math.pi
print("x", x, "y", y)
__result__ = {"x": x, "y": y}
""")
    print("spawn ok:", r.ok)
    print("result:", r.result)
    print("error:", r.error)
    print("metrics:", r.metrics)
    print("event types:", [e.type for e in r.events[:8]])

    # Example 2: spawn mode (portable) with RootSpec + dotted func_path capability
    # Note: for spawn mode, your capability function must be importable via dotted path.
    #
    # Create a small module and reference it with "module:func" (see README).

if __name__ == "__main__" and mp.current_process().name == "MainProcess":
    main()
