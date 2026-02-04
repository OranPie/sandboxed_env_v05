import json
import sys

from sandboxed_env.os_sandbox import validate_seccomp_profile

def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m sandboxed_env.examples.validate_seccomp <profile.json>")
        return 2
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        prof = json.load(f)
    try:
        validate_seccomp_profile(prof)
    except Exception as e:
        print(f"invalid: {e}")
        return 1
    print("ok")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
