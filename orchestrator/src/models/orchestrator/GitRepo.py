from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class GitRepo:
    id: int
    name: str
    url: str
    branch: str = 'main'
    enabled: bool = True
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "branch": self.branch,
            "enabled": self._bool_from_int(self.enabled),
            "created": self._dt(self.created),
            "updated": self._dt(self.updated),
        }

    @staticmethod
    def _dt(value: Optional[datetime]):
        return value.isoformat() if value else None

    @staticmethod
    def _bool_from_int(value) -> bool:
        if isinstance(value, bool):
            return value
        return value == 1

    @staticmethod
    def from_db_row(row) -> "GitRepo":
        return GitRepo(
            id=row[0],
            name=row[1],
            url=row[2],
            branch=row[3],
            enabled=row[4],
            created=row[5],
            updated=row[6],
        )

    @staticmethod
    def from_dict(obj: dict) -> "GitRepo":
        return GitRepo(
            id=obj.get("id", 0),
            name=obj.get("name", ""),
            url=obj.get("url", ""),
            branch=obj.get("branch", "main"),
            enabled=obj.get("enabled", True),
            created=obj.get("created"),
            updated=obj.get("updated"),
        )
