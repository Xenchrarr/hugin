from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class IcalSource:
    id: int
    name: str
    url: str
    enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    color: str = '#1976d2'

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
            "color": self.color,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def from_db_row(row) -> IcalSource:
        return IcalSource(
            id=row[0],
            name=row[1],
            url=row[2],
            enabled=bool(row[3]),
            created_at=row[4],
            updated_at=row[5],
            color=row[6] if row[6] else '#1976d2',
        )

    @staticmethod
    def from_dict(obj: dict) -> IcalSource:
        return IcalSource(
            id=obj.get("id", 0),
            name=obj.get("name", ""),
            url=obj.get("url", ""),
            enabled=bool(obj.get("enabled", True)),
            color=obj.get("color", "#1976d2"),
        )
