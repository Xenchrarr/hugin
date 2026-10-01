from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import IntEnum
from zoneinfo import ZoneInfo


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
    max_concurrent: int = 1
    workflow_input: dict = field(default_factory=dict)
    run_at: Optional[datetime] = None
    once_status: Optional[str] = None

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
            "max_concurrent": self.max_concurrent,
            "input": self.workflow_input or {},
            "run_at": self._dt(self.run_at),
            "once_status": self.once_status,
        }

    @staticmethod
    def _dt(value: Optional[datetime]):
        if isinstance(value, datetime):
            return value.isoformat()
        return value



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
            max_concurrent=row[14] if len(row) > 14 and row[14] else 1,
            workflow_input=row[15] if len(row) > 15 and row[15] else {},
            run_at=row[16] if len(row) > 16 else None,
            once_status=row[17] if len(row) > 17 else None,
        )

    @staticmethod
    def get_int_from_bool(value: bool) -> int: return 1 if value else 0

    @staticmethod
    def get_bool_from_int(value: int):
        return True if value == 1 else False

    @staticmethod
    def from_dict(obj: dict) -> 'Job':
        run_at = obj.get("run_at")
        if isinstance(run_at, str) and run_at:
            run_at = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
            if run_at.tzinfo is None:
                run_at = run_at.replace(tzinfo=ZoneInfo("Europe/Oslo"))
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
            obj.get("ran_last"),
            max(1, int(obj.get("max_concurrent", 1) or 1)),
            obj.get("input", obj.get("workflow_input", {})) or {},
            run_at,
            obj.get("once_status"),
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
