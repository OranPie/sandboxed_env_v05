PAYLOADS = [
    "__import__('os').system('id')",
    "open('/etc/passwd').read()",
    "().__class__.__mro__",
    "import os",
    "lambda x: x",
    "class X: pass",
    "while True: pass",
    "x = [0] * (10**9)",
    "x = 'a' * (10**9)",
    "x = list(range(10**9))",
]
