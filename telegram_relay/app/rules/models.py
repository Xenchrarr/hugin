from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class ForwardAction(BaseModel):
    type: Literal["forward"]
    destination: str
    redact: list[dict[str, str]] = Field(default_factory=list)
    include_fields: Optional[list[str]] = None
    exclude_fields: Optional[list[str]] = None


class SkipAction(BaseModel):
    type: Literal["skip"]


class LogAction(BaseModel):
    type: Literal["log"]
    level: str = "info"


Action = Annotated[
    Union[ForwardAction, SkipAction, LogAction],
    Field(discriminator="type"),
]


class Rule(BaseModel):
    name: str
    priority: int = 100
    enabled: bool = True
    # conditions is a raw dict parsed by the operator engine:
    #   {"all": [...]} | {"any": [...]} | {"not": {...}}
    #   | {"field": str, "op": str, "value": Any}
    #   | None / {} for catch-all
    conditions: Optional[dict[str, Any]] = None
    actions: list[Action] = Field(default_factory=list)
    continue_: bool = Field(False, alias="continue")

    model_config = {"populate_by_name": True}
