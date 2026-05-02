from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id: int
    username: str
    display_name: Optional[str]
    phone_number: Optional[str]
    telegram_user_id: Optional[int]
    config: dict
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    is_admin: bool = False
    password_hash: Optional[str] = None  # only populated during auth

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "phone_number": self.phone_number,
            "telegram_user_id": self.telegram_user_id,
            "config": self.config,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def from_db_row(row) -> User:
        """Expects 9-column row (no password_hash): id, username, display_name, phone_number, telegram_user_id, config, created_at, updated_at, is_admin."""
        return User(
            id=row[0],
            username=row[1],
            display_name=row[2],
            phone_number=row[3],
            telegram_user_id=row[4],
            config=row[5] or {},
            created_at=row[6],
            updated_at=row[7],
            is_admin=row[8],
        )

    @staticmethod
    def from_db_row_auth(row) -> User:
        """Expects 10-column row (is_admin at index 8, password_hash at index 9)."""
        user = User.from_db_row(row)
        user.password_hash = row[9]
        return user

    @staticmethod
    def from_dict(obj: dict) -> User:
        return User(
            id=obj.get("id", 0),
            username=obj.get("username", ""),
            display_name=obj.get("display_name"),
            phone_number=obj.get("phone_number"),
            telegram_user_id=obj.get("telegram_user_id"),
            config=obj.get("config", {}),
            created_at=obj.get("created_at"),
            updated_at=obj.get("updated_at"),
            is_admin=bool(obj.get("is_admin", False)),        )
