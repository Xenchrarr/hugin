from __future__ import annotations

from src.persistence.UserCommandPermissionStorage import UserCommandPermissionStorage

_storage = UserCommandPermissionStorage()


def list_by_user(user_id: int) -> list[str]:
    return _storage.list_by_user(user_id)


def add(user_id: int, command_path: str) -> None:
    _storage.add(user_id, command_path.strip().lower())


def remove(user_id: int, command_path: str) -> None:
    _storage.remove(user_id, command_path.strip().lower())
