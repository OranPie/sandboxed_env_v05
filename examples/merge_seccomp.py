import json
import sys

from sandboxed_env.os_sandbox import merge_allow_syscalls

def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python -m sandboxed_env.examples.merge_seccomp <base.json> <syscall> [syscall...]")
        return 2
    base_path = sys.argv[1]
    add = sys.argv[2:]
    with open(base_path, "r", encoding="utf-8") as f:
        prof = json.load(f)
    prof = merge_allow_syscalls(prof, add)
    json.dump(prof, sys.stdout, indent=2)
    print()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
