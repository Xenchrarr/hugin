import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RequestLog:
    id: uuid.UUID | str
    job_run_id: uuid.UUID | str
    area: str
    request_data: str
    request_type: str
    created: datetime
    response_code: int
    response: Optional[str]
    function_name: str
    api_name: str
    description: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": str(self.id) if self.id else None,
            "job_run_id": str(self.job_run_id) if self.job_run_id else None,
            "area": self.area,
            "request_data": self.request_data,
            "request_type": self.request_type,
            "created": self._dt(self.created),
            "response_code": self.response_code,
            "response": self.response,
            "function_name": self.function_name,
            "api_name": self.api_name,
            "description": self.description,
        }

    @staticmethod
    def _dt(value: Optional[datetime]):
        return value.isoformat() if value else None

    @staticmethod
    def from_db_row(row) -> "RequestLog":
        return RequestLog(
            id=row[0],
            job_run_id=row[1],
            area=row[2],
            request_data=row[3],
            request_type=row[4],
            created=row[5],
            response_code=row[6],
            response=row[7],
            function_name=row[8],
            api_name=row[9],
            description=row[10],
        )