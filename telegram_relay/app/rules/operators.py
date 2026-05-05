"""
Condition operators for the rule engine.

Each operator takes (field_value, reference_value) and returns bool.

Supported ops:
  eq        field == value  (numeric type-coercive)
  neq       field != value  (numeric type-coercive)
  in        field in value  (value must be a list, numeric type-coercive)
  not_in    field not in value
  contains  value in field  (field must be a string)
  regex     re.search(value, field)
  exists    field is not None
  gt        field > value
  lt        field < value
"""

import logging
import re
from typing import Any

from app.normalizer import NormalizedMessage

logger = logging.getLogger(__name__)


def _get_field(msg: NormalizedMessage, field: str) -> Any:
    return getattr(msg, field, None)


def _numeric_eq(v, ref) -> bool:
    """Equality check with numeric type coercion.

    Handles the case where a chat_id is stored as a string (e.g. "-1222103376")
    in the DB/JSON but arrives as an int from TDLib, or vice versa.
    """
    if v == ref:
        return True
    try:
        return type(v) != type(ref) and int(v) == int(ref)
    except (TypeError, ValueError):
        return False


_OPERATORS: dict = {
    "eq":       _numeric_eq,
    "neq":      lambda v, ref: not _numeric_eq(v, ref),
    "in":       lambda v, ref: any(_numeric_eq(v, r) for r in ref),
    "not_in":   lambda v, ref: not any(_numeric_eq(v, r) for r in ref),
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

    field_value = _get_field(msg, field)
    result = op_fn(field_value, ref_value)
    logger.debug(
        "Condition: field=%r value=%r (type=%s) op=%r ref=%r (type=%s) → %s",
        field, field_value, type(field_value).__name__,
        op, ref_value, type(ref_value).__name__, result,
    )
    return result
