from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Literal, TypeAlias

from src.services.core.cancellation_service import is_cancelled
from src.services.core.threading_service import JobCancelledException


class OnFailure(str, Enum):
    STOP = "stop"
    CONTINUE = "continue"


class WorkflowStepError(Exception):
    pass


StepOutcome = Literal["succeeded", "partial", "nothing"]


@dataclass(frozen=True, slots=True)
class StepArtifact:
    original_filename: str
    storage_path: str
    download_url: str

    def __post_init__(self) -> None:
        for name in ("original_filename", "storage_path", "download_url"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"Step artifact {name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class StepContext:
    job_run_id: str
    step_run_id: str
    step_key: str
    attempt: int
    run_by: str = ""

    def check_cancellation(self) -> None:
        if is_cancelled(self.job_run_id):
            raise JobCancelledException("Workflow execution was cancelled")


@dataclass(slots=True)
class StepResult:
    outcome: StepOutcome = "succeeded"
    output: dict = field(default_factory=dict)
    summary: str = ""
    artifacts: list[StepArtifact] = field(default_factory=list)


StepReturn: TypeAlias = StepResult | dict | None
StepHandler: TypeAlias = Callable[[StepContext, dict], StepReturn]
