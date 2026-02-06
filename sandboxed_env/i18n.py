from __future__ import annotations
from dataclasses import replace
from typing import Any, Dict, Optional, Tuple
import re

from .result import ErrorInfo

DEFAULT_LOCALE = "en"

_BUNDLES: Dict[str, Dict[str, str]] = {
    "en": {
        "error.import_not_allowed": "import is not allowed",
        "error.global_not_allowed": "global is not allowed",
        "error.nonlocal_not_allowed": "nonlocal is not allowed",
        "error.del_not_allowed": "del is not allowed",
        "error.raise_not_allowed": "raise is not allowed",
        "error.yield_not_allowed": "yield is not allowed",
        "error.async_not_allowed": "async is not allowed",
        "error.class_not_allowed": "class is not allowed",
        "error.def_not_allowed": "def is not allowed",
        "error.lambda_not_allowed": "lambda is not allowed",
        "error.try_not_allowed": "try/except is not allowed",
        "error.with_not_allowed": "with is not allowed",
        "error.subscript_not_allowed": "subscript is not allowed",
        "error.dunder_name_not_allowed": "dunder names are not allowed",
        "error.dunder_attr_not_allowed": "dunder attribute is not allowed",
        "error.attr_root_only": "only root.attr attribute access is allowed",
        "error.attr_not_allowed": "attribute '{root}.{attr}' is not allowed",
        "error.loop_iter_not_allowed": "loop iterable is not allowed",
        "error.loop_nesting_too_deep": "loop nesting too deep",
        "error.comp_iter_not_allowed": "comprehension iterable is not allowed",
        "error.comp_nesting_too_deep": "comprehension nesting too deep",
        "error.literal_too_large": "literal too large",
        "error.suspicious_const_alloc": "suspicious constant allocation",
        "error.ast_node_limit": "AST node limit exceeded",
        "error.step_limit": "step limit exceeded: {max_steps}",
        "error.timeout": "exceeded {ms}ms",
        "error.cap_max_call_ms": "cap max_call_ms exceeded ({ms}ms)",
        "error.cap_max_ret_bytes": "cap max_ret_bytes exceeded ({bytes} bytes)",
        "error.cap_max_calls": "cap max_calls exceeded ({calls})",
        "error.cap_max_total_ms": "cap max_total_ms exceeded ({ms}ms)",
        "error.cap_max_total_bytes": "cap max_total_bytes exceeded ({bytes} bytes)",
        "error.cap_max_qps": "cap max_qps exceeded ({qps})",
        "error.cap_max_bandwidth": "cap max_bandwidth exceeded ({bytes} bytes/sec)",
        "error.token_budget": "token budget exceeded: need {need}, remaining {remaining}",
        "error.token_budget_scopes": "token budget exceeded across scopes",
        "error.worker_no_payload": "no payload from worker",
        "error.worker_no_payload_err": "no payload from worker: {msg}",
        "error.worker_invalid_payload": "invalid payload: {msg}",
    },
    "zh-CN": {
        "error.import_not_allowed": "禁止 import",
        "error.global_not_allowed": "禁止 global",
        "error.nonlocal_not_allowed": "禁止 nonlocal",
        "error.del_not_allowed": "禁止 del",
        "error.raise_not_allowed": "禁止 raise",
        "error.yield_not_allowed": "禁止 yield",
        "error.async_not_allowed": "禁止 async",
        "error.class_not_allowed": "禁止 class",
        "error.def_not_allowed": "禁止 def",
        "error.lambda_not_allowed": "禁止 lambda",
        "error.try_not_allowed": "禁止 try/except",
        "error.with_not_allowed": "禁止 with",
        "error.subscript_not_allowed": "禁止下标访问",
        "error.dunder_name_not_allowed": "禁止双下划线名称",
        "error.dunder_attr_not_allowed": "禁止双下划线属性",
        "error.attr_root_only": "仅允许 root.attr 形式的属性访问",
        "error.attr_not_allowed": "属性 '{root}.{attr}' 不被允许",
        "error.loop_iter_not_allowed": "循环迭代对象不被允许",
        "error.loop_nesting_too_deep": "循环嵌套过深",
        "error.comp_iter_not_allowed": "推导式迭代对象不被允许",
        "error.comp_nesting_too_deep": "推导式嵌套过深",
        "error.literal_too_large": "字面量过大",
        "error.suspicious_const_alloc": "可疑的大常量分配",
        "error.ast_node_limit": "AST 节点数量超限",
        "error.step_limit": "执行步数超限：{max_steps}",
        "error.timeout": "超时（超过 {ms}ms）",
        "error.cap_max_call_ms": "能力单次耗时超限（{ms}ms）",
        "error.cap_max_ret_bytes": "能力返回大小超限（{bytes} 字节）",
        "error.cap_max_calls": "能力调用次数超限（{calls}）",
        "error.cap_max_total_ms": "能力总耗时超限（{ms}ms）",
        "error.cap_max_total_bytes": "能力总输出超限（{bytes} 字节）",
        "error.cap_max_qps": "能力 QPS 超限（{qps}）",
        "error.cap_max_bandwidth": "能力带宽超限（{bytes} 字节/秒）",
        "error.token_budget": "token 预算超限：需要 {need}，剩余 {remaining}",
        "error.token_budget_scopes": "跨 scope 的 token 预算超限",
        "error.worker_no_payload": "worker 未返回 payload",
        "error.worker_no_payload_err": "worker 未返回 payload：{msg}",
        "error.worker_invalid_payload": "payload 无效：{msg}",
    },
}

_EXACT_MESSAGE_KEYS: Dict[str, str] = {
    "import is not allowed": "error.import_not_allowed",
    "global is not allowed": "error.global_not_allowed",
    "nonlocal is not allowed": "error.nonlocal_not_allowed",
    "del is not allowed": "error.del_not_allowed",
    "raise is not allowed": "error.raise_not_allowed",
    "yield is not allowed": "error.yield_not_allowed",
    "async is not allowed": "error.async_not_allowed",
    "class is not allowed": "error.class_not_allowed",
    "def is not allowed": "error.def_not_allowed",
    "lambda is not allowed": "error.lambda_not_allowed",
    "try/except is not allowed": "error.try_not_allowed",
    "with is not allowed": "error.with_not_allowed",
    "subscript is not allowed": "error.subscript_not_allowed",
    "dunder names are not allowed": "error.dunder_name_not_allowed",
    "dunder attribute is not allowed": "error.dunder_attr_not_allowed",
    "only root.attr attribute access is allowed": "error.attr_root_only",
    "loop iterable is not allowed": "error.loop_iter_not_allowed",
    "loop nesting too deep": "error.loop_nesting_too_deep",
    "comprehension iterable is not allowed": "error.comp_iter_not_allowed",
    "comprehension nesting too deep": "error.comp_nesting_too_deep",
    "literal too large": "error.literal_too_large",
    "suspicious constant allocation": "error.suspicious_const_alloc",
    "AST node limit exceeded": "error.ast_node_limit",
    "token budget exceeded across scopes": "error.token_budget_scopes",
    "no payload from worker": "error.worker_no_payload",
}

_PATTERN_KEYS: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^attribute '(.+)\.(.+)' is not allowed$"), "error.attr_not_allowed"),
    (re.compile(r"^step limit exceeded: (\d+)$"), "error.step_limit"),
    (re.compile(r"^cap max_call_ms exceeded \((\d+)ms\)$"), "error.cap_max_call_ms"),
    (re.compile(r"^cap max_ret_bytes exceeded \((\d+) bytes\)$"), "error.cap_max_ret_bytes"),
    (re.compile(r"^cap max_calls exceeded \((\d+)\)$"), "error.cap_max_calls"),
    (re.compile(r"^cap max_total_ms exceeded \((\d+)ms\)$"), "error.cap_max_total_ms"),
    (re.compile(r"^cap max_total_bytes exceeded \((\d+) bytes\)$"), "error.cap_max_total_bytes"),
    (re.compile(r"^cap max_qps exceeded \((.+)\)$"), "error.cap_max_qps"),
    (re.compile(r"^cap max_bandwidth exceeded \((\d+) bytes/sec\)$"), "error.cap_max_bandwidth"),
    (re.compile(r"^token budget exceeded: need (\d+), remaining (\d+)$"), "error.token_budget"),
    (re.compile(r"^no payload from worker: (.+)$"), "error.worker_no_payload_err"),
    (re.compile(r"^invalid payload: (.*)$"), "error.worker_invalid_payload"),
    (re.compile(r"^exceeded (\d+)ms$"), "error.timeout"),
)


def register_bundle(locale: str, messages: Dict[str, str]) -> None:
    if not locale:
        return
    bundle = _BUNDLES.get(locale)
    if bundle is None:
        _BUNDLES[locale] = dict(messages)
        return
    bundle.update(messages)


def translate(key: str, locale: Optional[str] = None, **params: Any) -> str:
    loc = locale or DEFAULT_LOCALE
    bundle = _BUNDLES.get(loc) or {}
    text = bundle.get(key)
    if text is None:
        text = (_BUNDLES.get(DEFAULT_LOCALE) or {}).get(key)
    if text is None:
        text = key
    if params:
        try:
            return text.format(**params)
        except Exception:
            return text
    return text


def translate_message(message: str, locale: Optional[str] = None) -> str:
    if not message:
        return message
    key = _EXACT_MESSAGE_KEYS.get(message)
    if key:
        return translate(key, locale)
    for pattern, pkey in _PATTERN_KEYS:
        match = pattern.match(message)
        if not match:
            continue
        params = _match_to_params(pkey, match.groups())
        return translate(pkey, locale, **params)
    return message


def translate_error(err: Optional[ErrorInfo], locale: Optional[str] = None) -> Optional[ErrorInfo]:
    if err is None:
        return None
    loc = locale or DEFAULT_LOCALE
    if not loc or loc == DEFAULT_LOCALE:
        return err
    msg = translate_message(err.message, loc)
    if msg == err.message:
        return err
    return replace(err, message=msg)


def timeout_message(ms: int, locale: Optional[str] = None) -> str:
    return translate("error.timeout", locale, ms=ms)


def _match_to_params(key: str, groups: Tuple[str, ...]) -> Dict[str, Any]:
    if key == "error.attr_not_allowed":
        root, attr = groups
        return {"root": root, "attr": attr}
    if key == "error.step_limit":
        return {"max_steps": int(groups[0])}
    if key in {"error.cap_max_call_ms", "error.cap_max_total_ms"}:
        return {"ms": int(groups[0])}
    if key in {"error.cap_max_ret_bytes", "error.cap_max_total_bytes", "error.cap_max_bandwidth"}:
        return {"bytes": int(groups[0])}
    if key == "error.cap_max_calls":
        return {"calls": int(groups[0])}
    if key == "error.cap_max_qps":
        return {"qps": groups[0]}
    if key == "error.token_budget":
        return {"need": int(groups[0]), "remaining": int(groups[1])}
    if key == "error.worker_no_payload_err":
        return {"msg": groups[0]}
    if key == "error.worker_invalid_payload":
        return {"msg": groups[0]}
    if key == "error.timeout":
        return {"ms": int(groups[0])}
    return {}
