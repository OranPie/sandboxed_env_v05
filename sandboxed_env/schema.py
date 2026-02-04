from __future__ import annotations
from typing import Any, Dict, List, Optional
import re

class SchemaError(Exception):
    pass

_SCHEMA_CACHE: dict[str, Any] = {}

def _cache_key(schema: Any) -> Optional[str]:
    try:
        import json
        return json.dumps(schema, sort_keys=True, ensure_ascii=True)
    except Exception:
        return None

def validate_schema_cached(value: Any, schema: Any) -> None:
    key = _cache_key(schema)
    if key is None:
        validate_schema(value, schema)
        return
    compiled = _SCHEMA_CACHE.get(key)
    if compiled is None:
        compiled = schema
        _SCHEMA_CACHE[key] = compiled
    validate_schema(value, compiled)

def _path_join(path: str, part: str) -> str:
    if not path:
        return part
    if part.startswith("["):
        return f"{path}{part}"
    return f"{path}.{part}"

def validate_schema(value: Any, schema: Any, *, path: str = "$") -> None:
    if schema is None:
        return

    if callable(schema):
        try:
            ok = schema(value)
        except Exception as e:
            raise SchemaError(f"{path}: {e}")
        if ok is False:
            raise SchemaError(f"{path}: schema callable returned False")
        return

    if hasattr(schema, "model_validate"):
        try:
            schema.model_validate(value)
            return
        except Exception as e:
            raise SchemaError(f"{path}: {e}")
    if hasattr(schema, "parse_obj"):
        try:
            schema.parse_obj(value)
            return
        except Exception as e:
            raise SchemaError(f"{path}: {e}")

    if not isinstance(schema, dict):
        raise SchemaError(f"{path}: invalid schema")

    if "anyOf" in schema:
        last_err = None
        for sub in schema["anyOf"]:
            try:
                validate_schema(value, sub, path=path)
                return
            except SchemaError as e:
                last_err = e
        raise SchemaError(str(last_err) if last_err else f"{path}: anyOf failed")

    if "oneOf" in schema:
        ok = 0
        for sub in schema["oneOf"]:
            try:
                validate_schema(value, sub, path=path)
                ok += 1
            except SchemaError:
                pass
        if ok != 1:
            raise SchemaError(f"{path}: oneOf failed")

    if "allOf" in schema:
        for sub in schema["allOf"]:
            validate_schema(value, sub, path=path)

    if "enum" in schema:
        if value not in schema["enum"]:
            raise SchemaError(f"{path}: value not in enum")

    t = schema.get("type")
    if isinstance(t, list):
        ok = False
        last = None
        for tt in t:
            try:
                validate_schema(value, {**schema, "type": tt}, path=path)
                ok = True
                break
            except SchemaError as e:
                last = e
        if not ok:
            raise SchemaError(str(last) if last else f"{path}: type mismatch")
        return

    if t == "null":
        if value is not None:
            raise SchemaError(f"{path}: expected null")
        return
    if t == "boolean":
        if not isinstance(value, bool):
            raise SchemaError(f"{path}: expected boolean")
        return
    if t == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise SchemaError(f"{path}: expected integer")
        _check_number(value, schema, path)
        return
    if t == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise SchemaError(f"{path}: expected number")
        _check_number(value, schema, path)
        return
    if t == "string":
        if not isinstance(value, str):
            raise SchemaError(f"{path}: expected string")
        _check_string(value, schema, path)
        return
    if t == "array":
        if not isinstance(value, list):
            raise SchemaError(f"{path}: expected array")
        _check_array(value, schema, path)
        return
    if t == "object":
        if not isinstance(value, dict):
            raise SchemaError(f"{path}: expected object")
        _check_object(value, schema, path)
        return

def _check_number(value: float, schema: Dict[str, Any], path: str) -> None:
    if "minimum" in schema and value < schema["minimum"]:
        raise SchemaError(f"{path}: below minimum")
    if "maximum" in schema and value > schema["maximum"]:
        raise SchemaError(f"{path}: above maximum")

def _check_string(value: str, schema: Dict[str, Any], path: str) -> None:
    if "minLength" in schema and len(value) < schema["minLength"]:
        raise SchemaError(f"{path}: too short")
    if "maxLength" in schema and len(value) > schema["maxLength"]:
        raise SchemaError(f"{path}: too long")
    if "pattern" in schema:
        try:
            if re.search(schema["pattern"], value) is None:
                raise SchemaError(f"{path}: pattern mismatch")
        except re.error:
            raise SchemaError(f"{path}: invalid pattern")
    if "format" in schema:
        fmt = schema["format"]
        if fmt == "email":
            if re.match(r"^[^@]+@[^@]+\.[^@]+$", value) is None:
                raise SchemaError(f"{path}: invalid email")
        elif fmt == "uuid":
            if re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", value) is None:
                raise SchemaError(f"{path}: invalid uuid")

def _check_array(value: List[Any], schema: Dict[str, Any], path: str) -> None:
    if "minItems" in schema and len(value) < schema["minItems"]:
        raise SchemaError(f"{path}: too few items")
    if "maxItems" in schema and len(value) > schema["maxItems"]:
        raise SchemaError(f"{path}: too many items")
    if "items" in schema:
        for i, v in enumerate(value):
            validate_schema(v, schema["items"], path=_path_join(path, f"[{i}]"))

def _check_object(value: Dict[str, Any], schema: Dict[str, Any], path: str) -> None:
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    for r in required:
        if r not in value:
            raise SchemaError(f"{_path_join(path, r)}: missing required")
    additional = schema.get("additionalProperties", True)
    for k, v in value.items():
        if k in props:
            validate_schema(v, props[k], path=_path_join(path, str(k)))
        elif not additional:
            raise SchemaError(f"{_path_join(path, str(k))}: unexpected property")
