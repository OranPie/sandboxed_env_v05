import random
import multiprocessing as mp

from sandboxed_env import SandboxedEnv, default_policy_v14
from sandboxed_env.examples.fuzz_payloads import PAYLOADS

def rand_expr(r: random.Random) -> str:
    choices = [
        str(r.randint(-10, 10)),
        f"({r.randint(0, 5)} + {r.randint(0, 5)})",
        f"({r.randint(0, 5)} * {r.randint(0, 5)})",
    ]
    return r.choice(choices)

def rand_stmt(r: random.Random) -> str:
    if r.random() < 0.5:
        return f"x = {rand_expr(r)}"
    n = r.randint(0, 5)
    return f"""s = 0
for i in range({n}):
    s = s + i
"""

def run_fuzz(seed: int, rounds: int = 50) -> None:
    r = random.Random(seed)
    env = SandboxedEnv(default_policy_v14())

    for i in range(rounds):
        code = rand_stmt(r) + "\\n__result__ = 1"
        res = env.execute(code)
        if res.error and res.error.stage not in ("policy", "runtime", "timeout", "schema"):
            print("unexpected error:", res.error)

    for p in PAYLOADS:
        res = env.execute(p)
        if res.ok:
            print("payload unexpectedly ok:", p)

if __name__ == "__main__" and mp.current_process().name == "MainProcess":
    run_fuzz(0, rounds=100)
