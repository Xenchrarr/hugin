from __future__ import annotations

from src.persistence.ScriptPermissionStorage import ScriptPermissionStorage, ScriptPermission

_storage = ScriptPermissionStorage()


def get_all_script_permissions() -> list[ScriptPermission]:
    return _storage.get_all()


def get_allowed_script_names() -> list[str]:
    return _storage.get_allowed_script_names()


def upsert_script_permission(script_name: str, allowed: bool) -> None:
    _storage.upsert(script_name, allowed)


def delete_script_permission(script_name: str) -> None:
    _storage.delete(script_name)
