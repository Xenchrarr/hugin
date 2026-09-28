from __future__ import annotations

import json
import re

from src.persistence.DatabaseLogger import DatabaseLogger
from src.persistence.UserStorage import UserStorage
from src.services.external.call_service import ring_phone


_E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")


def run_phone_call(param: str = "") -> dict:
    """Place one ring-only call for a scheduled Hugin job.

    Parameters are JSON: {"target": "<user id, name, or E.164>",
    "ring_seconds": 20}. Explicit user_id, user, and phone keys are also
    accepted for API-created jobs.
    """
    values = _parse_param(param)
    ring_seconds = _bounded_ring_seconds(values.get("ring_seconds", 20))
    phone, label = _resolve_target(values)

    logger = DatabaseLogger()
    logger.log_info(f"Starting phone-call job for {label} ({_masked(phone)}), up to {ring_seconds}s")
    result = ring_phone(phone, ring_seconds=ring_seconds)
    status = str(result.get("status") or "unknown")
    logger.log_info(f"Phone-call job for {label} finished with status: {status}")

    if not result.get("ok"):
        raise RuntimeError(f"Call to {label} did not reach an accepted outcome: {status}")
    return result


def _parse_param(param: str) -> dict:
    raw = str(param or "").strip()
    if not raw:
        raise ValueError("Phone-call job requires a target")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = {"target": raw}
    if not isinstance(value, dict):
        raise ValueError("Phone-call job parameter must be a JSON object or target")
    return value


def _resolve_target(values: dict) -> tuple[str, str]:
    storage = UserStorage()
    explicit_phone = str(values.get("phone") or "").strip()
    target = str(values.get("target") or "").strip()
    user_id = values.get("user_id")
    user_name = str(values.get("user") or "").strip()

    if explicit_phone:
        phone, label = explicit_phone, "explicit number"
    elif user_id is not None or (target.isdigit() and target):
        resolved_id = int(user_id if user_id is not None else target)
        user = storage.get_user(resolved_id)
        if not user:
            raise ValueError(f"Hugin user {resolved_id} was not found")
        phone = str(user.phone_number or "").strip()
        label = user.display_name or user.username or f"user {resolved_id}"
    elif user_name or (target and not target.startswith("+")):
        resolved_name = user_name or target
        user = storage.get_user_by_name(resolved_name)
        if not user:
            raise ValueError(f"Hugin user '{resolved_name}' was not found")
        phone = str(user.phone_number or "").strip()
        label = user.display_name or user.username or resolved_name
    else:
        phone, label = target, "explicit number"

    if not phone:
        raise ValueError(f"{label} does not have a phone number")
    if not _E164.fullmatch(phone):
        raise ValueError(f"Phone number for {label} must use E.164 format")
    return phone, label


def _bounded_ring_seconds(value) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("ring_seconds must be a number from 5 to 60") from exc
    if not 5 <= seconds <= 60:
        raise ValueError("ring_seconds must be between 5 and 60")
    return seconds


def _masked(phone: str) -> str:
    return f"***{phone[-4:]}"
