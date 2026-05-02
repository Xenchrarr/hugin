"""
Condition operators for the rule engine.

Each operator takes (field_value, reference_value) and returns bool.

Supported ops:
  eq        field == value
  neq       field != value
  in        field in value  (value must be a list)
  not_in    field not in value
  contains  value in field  (field must be a string)
  regex     re.search(value, field)
  exists    field is not None
  gt        field > value
  lt        field < value
"""

import re
from typing import Any

from app.normalizer import NormalizedMessage


def _get_field(msg: NormalizedMessage, field: str) -> Any:
    return getattr(msg, field, None)


_OPERATORS: dict = {
    "eq":       lambda v, ref: v == ref,
    "neq":      lambda v, ref: v != ref,
    "in":       lambda v, ref: v in ref,
    "not_in":   lambda v, ref: v not in ref,
    "contains": lambda v, ref: isinstance(v, str) and ref in v,
    "regex":    lambda v, ref: bool(re.search(ref, v)) if isinstance(v, str) else False,
    "exists":   lambda v, _ref: v is not None,
    "gt":       lambda v, ref: v is not None and v > ref,
    "lt":       lambda v, ref: v is not None and v < ref,
}


def evaluate_condition(condition: dict, msg: NormalizedMessage) -> bool:
    """Recursively evaluate a condition tree against a NormalizedMessage."""
    if "all" in condition:
        return all(evaluate_condition(c, msg) for c in condition["all"])
    if "any" in condition:
        return any(evaluate_condition(c, msg) for c in condition["any"])
    if "not" in condition:
        return not evaluate_condition(condition["not"], msg)

    # Leaf node
    field = condition.get("field")
    op = condition.get("op")
    ref_value = condition.get("value")

    if not field or not op:
        return False

    op_fn = _OPERATORS.get(op)
    if op_fn is None:
        raise ValueError(f"Unknown condition operator: {op!r}")

    return op_fn(_get_field(msg, field), ref_value)
