from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)


class SkillContext(BaseModel):
    user_id: str
    request_id: str = ""
    triggered_by: str = "api"

    def model_post_init(self, __context: object) -> None:
        if not self.request_id:
            self.request_id = str(uuid.uuid4())


class SkillResult(BaseModel, Generic[TOutput]):
    success: bool
    data: TOutput | None = None
    error: str | None = None
    error_code: str | None = None
    cached: bool = False
    execution_ms: int = 0
    executed_at: str = ""

    def model_post_init(self, __context: object) -> None:
        if not self.executed_at:
            self.executed_at = datetime.now(timezone.utc).isoformat()


class BaseSkill(ABC, Generic[TInput, TOutput]):
    name: str
    version: str = "1.0.0"
    description: str

    @abstractmethod
    async def run(self, input: TInput, ctx: SkillContext) -> SkillResult[TOutput]:
        pass
