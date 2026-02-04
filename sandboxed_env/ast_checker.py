from __future__ import annotations
import ast
from .policy import Policy
from .errors import SandboxError

class PolicyChecker(ast.NodeVisitor):
    def __init__(self, p: Policy, *, known_iter_names: set[str] | None = None):
        self.p = p
        self.node_count = 0
        self.loop_depth = 0
        self.comp_depth = 0
        self.iter_names: set[str] = set(known_iter_names or set())

    def generic_visit(self, node):
        self.node_count += 1
        if self.node_count > self.p.max_ast_nodes:
            col = getattr(node, "col_offset", None)
            if col is not None:
                col = col + 1
            raise SandboxError("AST node limit exceeded", lineno=getattr(node, "lineno", None), col=col)
        super().generic_visit(node)

    def _const_int(self, node: ast.AST) -> int | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = self._const_int(node.operand)
            if v is None:
                return None
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.BinOp):
            a = self._const_int(node.left)
            b = self._const_int(node.right)
            if a is None or b is None:
                return None
            try:
                if isinstance(node.op, ast.Add):
                    return a + b
                if isinstance(node.op, ast.Sub):
                    return a - b
                if isinstance(node.op, ast.Mult):
                    return a * b
                if isinstance(node.op, ast.FloorDiv) and b != 0:
                    return a // b
                if isinstance(node.op, ast.Pow) and b >= 0:
                    if abs(a) >= 2 and b > 30:
                        return self.p.max_const_alloc_elems + 1
                    return a ** b
            except Exception:
                return None
        return None

    def _const_len(self, node: ast.AST) -> int | None:
        if isinstance(node, (ast.List, ast.Tuple)):
            return len(node.elts)
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            return len(node.value)
        return None

    def _is_allowed_iter(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Name) and self.p.allow_loop_iter_names:
            return node.id in self.iter_names
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id in self.p.loop_iter_allowlist
        if self.p.allow_loop_iter_literals and isinstance(node, (ast.List, ast.Tuple)):
            return True
        return False

    def _deny(self, msg: str, node: ast.AST | None = None):
        lineno = getattr(node, "lineno", None)
        col = getattr(node, "col_offset", None)
        if col is not None:
            col = col + 1
        raise SandboxError(msg, lineno=lineno, col=col)

    def visit_Import(self, node): self._deny("import is not allowed", node)
    def visit_ImportFrom(self, node): self._deny("import is not allowed", node)
    def visit_Global(self, node): self._deny("global is not allowed", node)
    def visit_Nonlocal(self, node): self._deny("nonlocal is not allowed", node)
    def visit_Delete(self, node): self._deny("del is not allowed", node)
    def visit_Raise(self, node): self._deny("raise is not allowed", node)
    def visit_Yield(self, node): self._deny("yield is not allowed", node)
    def visit_YieldFrom(self, node): self._deny("yield is not allowed", node)
    def visit_Await(self, node): self._deny("await is not allowed", node)
    def visit_AsyncFunctionDef(self, node): self._deny("async is not allowed", node)
    def visit_AsyncFor(self, node): self._deny("async is not allowed", node)
    def visit_AsyncWith(self, node): self._deny("async is not allowed", node)

    def visit_ClassDef(self, node):
        if not self.p.allow_class: self._deny("class is not allowed", node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if not self.p.allow_def: self._deny("def is not allowed", node)
        self.generic_visit(node)

    def visit_Lambda(self, node):
        if not self.p.allow_lambda: self._deny("lambda is not allowed", node)
        self.generic_visit(node)

    def visit_Try(self, node):
        if not self.p.allow_try: self._deny("try/except is not allowed", node)
        self.generic_visit(node)

    def visit_With(self, node):
        if not self.p.allow_with: self._deny("with is not allowed", node)
        self.generic_visit(node)

    def visit_Subscript(self, node):
        if not self.p.allow_subscript: self._deny("subscript is not allowed", node)
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id.startswith("__") and node.id.endswith("__"):
            if node.id not in self.p.allow_dunder_names:
                self._deny("dunder names are not allowed", node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self._deny("dunder attribute is not allowed", node)
        if not isinstance(node.value, ast.Name):
            self._deny("only root.attr attribute access is allowed", node)
        root = node.value.id
        allowed = self.p.attr_allowlist.get(root)
        if not allowed or node.attr not in allowed:
            self._deny(f"attribute '{root}.{node.attr}' is not allowed", node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if self._is_allowed_iter(node.value):
                self.iter_names.add(name)
            else:
                self.iter_names.discard(name)
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        if isinstance(node.op, ast.Mult):
            a_len = self._const_len(node.left)
            b_len = self._const_len(node.right)
            a_int = self._const_int(node.left)
            b_int = self._const_int(node.right)
            if a_len is not None and b_int is not None:
                if a_len * b_int > self.p.max_const_alloc_elems:
                    self._deny("suspicious constant allocation", node)
            if b_len is not None and a_int is not None:
                if b_len * a_int > self.p.max_const_alloc_elems:
                    self._deny("suspicious constant allocation", node)
        self.generic_visit(node)

    def visit_List(self, node: ast.List):
        if len(node.elts) > self.p.max_literal_elems:
            self._deny("literal too large", node)
        self.generic_visit(node)

    def visit_Tuple(self, node: ast.Tuple):
        if len(node.elts) > self.p.max_literal_elems:
            self._deny("literal too large", node)
        self.generic_visit(node)

    def visit_Set(self, node: ast.Set):
        if len(node.elts) > self.p.max_literal_elems:
            self._deny("literal too large", node)
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict):
        if len(node.keys) > self.p.max_literal_elems:
            self._deny("literal too large", node)
        self.generic_visit(node)

    def visit_For(self, node):
        if not self.p.allow_loops: self._deny("loops are not allowed", node)
        if self.p.restrict_loop_iterables and not self._is_allowed_iter(node.iter):
            self._deny("loop iterable is not allowed", node)
        self.loop_depth += 1
        if self.loop_depth > self.p.max_loop_nesting:
            self._deny("loop nesting too deep", node)
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_While(self, node):
        if not self.p.allow_loops: self._deny("loops are not allowed", node)
        self.loop_depth += 1
        if self.loop_depth > self.p.max_loop_nesting:
            self._deny("loop nesting too deep", node)
        self.generic_visit(node)
        self.loop_depth -= 1

    def _visit_comp(self, node):
        if not self.p.allow_comprehension: self._deny("comprehension is not allowed", node)
        self.comp_depth += 1
        if self.comp_depth > self.p.max_comp_nesting:
            self._deny("comprehension nesting too deep", node)
        if self.p.restrict_loop_iterables:
            for g in node.generators:
                if not self._is_allowed_iter(g.iter):
                    self._deny("comprehension iterable is not allowed", node)
        self.generic_visit(node)
        self.comp_depth -= 1

    def visit_ListComp(self, node): self._visit_comp(node)
    def visit_SetComp(self, node): self._visit_comp(node)
    def visit_DictComp(self, node): self._visit_comp(node)
    def visit_GeneratorExp(self, node): self._visit_comp(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            fn = node.func.id
            if fn not in self.p.call_name_allowlist:
                self._deny(f"call '{fn}' is not allowed", node)
            if fn in ("list", "tuple") and node.args:
                a0 = node.args[0]
                if isinstance(a0, ast.Call) and isinstance(a0.func, ast.Name) and a0.func.id == "range":
                    size = self._range_size(a0)
                    if size is not None and size > self.p.max_const_alloc_elems:
                        self._deny("suspicious constant allocation", node)
        elif isinstance(node.func, ast.Attribute):
            # root.attr validated in visit_Attribute
            pass
        else:
            self._deny("only f(...) or root.attr(...) calls are allowed", node)
        self.generic_visit(node)

    def _range_size(self, node: ast.Call) -> int | None:
        if not (isinstance(node.func, ast.Name) and node.func.id == "range"):
            return None
        args = node.args
        if len(args) == 1:
            stop = self._const_int(args[0])
            if stop is None:
                return None
            return max(0, stop)
        if len(args) >= 2:
            start = self._const_int(args[0])
            stop = self._const_int(args[1])
            step = self._const_int(args[2]) if len(args) >= 3 else 1
            if start is None or stop is None or step in (None, 0):
                return None
            try:
                n = (stop - start + (step - 1 if step > 0 else step + 1)) // step
            except Exception:
                return None
            return max(0, n)
        return None
