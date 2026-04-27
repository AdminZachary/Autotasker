from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class UserOut(BaseModel):
    id: int
    username: str
    focus_minutes: int
    break_minutes: int
    quiet_hours: str

    model_config = {"from_attributes": True}


class AuthPayload(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=128)


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class PreferencesUpdate(BaseModel):
    focus_minutes: int = Field(ge=15, le=90)
    break_minutes: int = Field(ge=3, le=30)
    quiet_hours: str = Field(min_length=5, max_length=50)


class AIConfig(BaseModel):
    provider: Literal["openai", "azure_openai", "deepseek", "qwen", "glm", "gemini", "custom_compatible"] = "openai"
    model: str = Field(min_length=1, max_length=120)
    api_key: Optional[str] = Field(default=None, max_length=500)
    base_url: Optional[str] = Field(default=None, max_length=500)


class GoalAnalyzeRequest(BaseModel):
    goal_text: str = Field(min_length=1, max_length=4000)
    ai_config: AIConfig


class StageTaskSchema(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    scheduled_for: datetime
    due_at: datetime
    estimated_minutes: int = Field(ge=15, le=180)

    @field_validator("due_at")
    @classmethod
    def due_after_schedule(cls, value: datetime, info):
        scheduled = info.data.get("scheduled_for")
        if scheduled and value <= scheduled:
            raise ValueError("due_at 必须晚于 scheduled_for")
        return value


class GoalPlanSchema(BaseModel):
    status: Literal["ok", "suggest_adjustment"]
    agent_feedback: str = Field(min_length=1, max_length=800)
    staging_tasks: list[StageTaskSchema] = Field(default_factory=list)


class GoalConfirmRequest(BaseModel):
    goal_text: str = Field(min_length=1, max_length=4000)
    agent_feedback: str = Field(min_length=1, max_length=800)
    tasks: list[StageTaskSchema] = Field(min_length=1)


class TaskOut(BaseModel):
    id: int
    goal_id: int
    title: str
    description: str
    scheduled_for: Optional[datetime]
    due_at: Optional[datetime]
    status: str
    estimated_minutes: int
    order_index: int
    delay_count: int
    last_started_at: Optional[datetime]
    completed_at: Optional[datetime]
    updated_at: datetime
    overdue: bool


class TaskStatusUpdate(BaseModel):
    status: Literal["todo", "in_progress", "done"]


class TaskEditRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    scheduled_for: datetime
    due_at: datetime
    estimated_minutes: int = Field(ge=15, le=180)


class TaskPostponeRequest(BaseModel):
    task_id: int
    minutes: int = Field(default=30, ge=15, le=240)


class PomodoroStartRequest(BaseModel):
    task_id: int
    planned_minutes: int = Field(ge=15, le=90)


class PomodoroFinishRequest(BaseModel):
    log_id: int
    task_id: int
    actual_seconds: int = Field(ge=0)
    result: Literal["done", "interrupted"]


class PomodoroStartResponse(BaseModel):
    log_id: int
    planned_minutes: int


class ReviewRequest(BaseModel):
    ai_config: AIConfig


class ReviewSchema(BaseModel):
    review: str = Field(min_length=1, max_length=500)


class StatsOut(BaseModel):
    total_tasks: int
    done_tasks: int
    in_progress_tasks: int
    todo_tasks: int
    overdue_tasks: int
    delay_total: int
    focus_minutes_total: int
    completion_rate: float
    trend: list[dict]
    review: str


class RecentLogOut(BaseModel):
    id: int
    task_id: int
    task_title: str
    status: str
    planned_minutes: int
    actual_seconds: int
    start_time: datetime
    end_time: Optional[datetime]


class BootstrapResponse(BaseModel):
    user: UserOut
    tasks: list[TaskOut]
    stats: StatsOut
    recent_logs: list[RecentLogOut]
    provider_presets: dict[str, str]


class HealthResponse(BaseModel):
    status: str
    time: datetime
    stack: list[str]
