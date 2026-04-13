from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import IntEnum


class Weekday(IntEnum):
    monday = 0
    tuesday = 1
    wednesday = 2
    thursday = 3
    friday = 4
    saturday = 5
    sunday = 6


@dataclass
class Job:
    id: int
    name: str
    enabled: bool
    job_type: str
    hour: int
    minute: int
    created_at: datetime
    updated_at: datetime
    trigger: str
    param: str = ''
    weekday: str = ''
    description: str = ''
    grouping_value: str = ''
    ran_last: Optional[datetime] = None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "enabled": Job.get_bool_from_int(self.enabled),
            "job_type": self.job_type,
            "hour": self.hour,
            "minute": self.minute,
            "created_at": self._dt(self.created_at),
            "updated_at": self._dt(self.updated_at),
            "trigger": self.trigger,
            "param": self.param,
            "weekday": self.weekday,
            "description": self.description,
            "grouping_value": self.grouping_value,
            "ran_last": self._dt(self.ran_last),
        }

    @staticmethod
    def _dt(value: Optional[datetime]):
        return value.isoformat() if value else None



    @staticmethod
    def from_db_row(row) -> "Job":
        return Job(
            id=row[0],
            name=row[1],
            enabled=row[2],
            job_type=row[3],
            hour=row[4],
            minute=row[5],
            created_at=row[6],
            updated_at=row[7],
            trigger=row[8],
            param=row[9],
            weekday=row[10],
            description=row[11],
            grouping_value=row[12],
            ran_last=row[13],
        )

    @staticmethod
    def get_int_from_bool(value: bool) -> int: return 1 if value else 0

    @staticmethod
    def get_bool_from_int(value: int):
        return True if value == 1 else False

    @staticmethod
    def from_dict(obj: dict) -> 'Job':
        return Job(
            obj.get("id", 0),
            obj.get("name"),
            obj.get("enabled"),
            obj.get("job_type"),
            obj.get("hour"),
            obj.get("minute"),
            obj.get("created_at"),
            obj.get("updated_at"),
            obj.get("trigger"),
            obj.get("param"),
            obj.get("weekday"),
            obj.get("description"),
            obj.get("grouping_value"),
            obj.get("ran_last")
        )


    def get_weekday_from_int(self) -> str:
        value = int(self.weekday)
        if value == 0:
            return 'monday'
        if value == 1:
            return 'tuesday'
        if value == 2:
            return 'wednesday'
        if value == 3:
            return 'thursday'
        if value == 4:
            return 'friday'
        if value == 5:
            return 'saturday'
        if value == 6:
            return 'sunday'
        return ''

    def get_int_from_weekday(self) -> int:
        value = self.weekday

        if value == '':
            raise Exception("Weekday is empty")
        if value == 'monday':
            return 0
        if value == 'tuesday':
            return 1
        if value == 'wednesday':
            return 2
        if value == 'thursday':
            return 3
        if value == 'friday':
            return 4
        if value == 'saturday':
            return 5
        if value == 'sunday':
            return 6
        return -1