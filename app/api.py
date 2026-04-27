from datetime import datetime, timedelta
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Goal, PomodoroLog, Task, User
from app.schemas import (
    AuthPayload,
    AuthResponse,
    BootstrapResponse,
    GoalAnalyzeRequest,
    GoalConfirmRequest,
    HealthResponse,
    PomodoroFinishRequest,
    PomodoroStartRequest,
    PomodoroStartResponse,
    PreferencesUpdate,
    ReviewRequest,
    TaskEditRequest,
    TaskPostponeRequest,
    TaskStatusUpdate,
    UserOut,
)
from app.security import create_access_token, hash_password, verify_password
from app.services.ai import PROVIDER_PRESETS, generate_goal_plan, generate_review
from app.services.integrations import database_health, resolve_ai_config
from app.services.metrics import get_stats, serialize_task


router = APIRouter(prefix="/api")


def parse_due_date(goal_text: str):
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", goal_text)
    if not match:
        return None
    try:
        return datetime.fromisoformat("%sT00:00:00" % match.group(1)).date()
    except ValueError:
        return None


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        time=datetime.now().astimezone(),
        stack=["FastAPI", "SQLAlchemy", "LangChain", "MySQL-ready"],
    )


@router.get("/integrations/status")
def integration_status(db: Session = Depends(get_db)):
    return {
        "database": database_health(db),
        "provider_presets": PROVIDER_PRESETS,
        "env_keys": {
            "OPENAI_API_KEY": bool(settings.openai_api_key),
            "AZURE_OPENAI_API_KEY": bool(settings.azure_openai_api_key),
            "AZURE_OPENAI_ENDPOINT": bool(settings.azure_openai_endpoint),
            "AZURE_OPENAI_API_VERSION": bool(settings.azure_openai_api_version),
            "DEEPSEEK_API_KEY": bool(settings.deepseek_api_key),
            "QWEN_API_KEY": bool(settings.qwen_api_key),
            "DASHSCOPE_API_KEY": bool(settings.dashscope_api_key),
            "ZHIPU_API_KEY": bool(settings.zhipu_api_key),
            "GOOGLE_API_KEY": bool(settings.google_api_key),
            "GEMINI_API_KEY": bool(settings.gemini_api_key),
        },
    }


@router.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: AuthPayload, db: Session = Depends(get_db)) -> AuthResponse:
    user = User(username=payload.username.strip(), password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="用户名已存在") from exc
    db.refresh(user)
    return AuthResponse(token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: AuthPayload, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.username == payload.username.strip()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return AuthResponse(token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/bootstrap", response_model=BootstrapResponse)
def bootstrap(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> BootstrapResponse:
    tasks = db.scalars(
        select(Task)
        .where(Task.user_id == current_user.id)
        .order_by(
            case((Task.status == "in_progress", 0), (Task.status == "todo", 1), else_=2),
            Task.scheduled_for,
            Task.order_index,
            Task.id,
        )
    ).all()
    recent_logs = db.execute(
        select(
            PomodoroLog.id,
            PomodoroLog.task_id,
            Task.title.label("task_title"),
            PomodoroLog.status,
            PomodoroLog.planned_minutes,
            PomodoroLog.actual_seconds,
            PomodoroLog.start_time,
            PomodoroLog.end_time,
        )
        .join(Task, Task.id == PomodoroLog.task_id)
        .where(PomodoroLog.user_id == current_user.id)
        .order_by(PomodoroLog.id.desc())
        .limit(8)
    ).all()
    return BootstrapResponse(
        user=UserOut.model_validate(current_user),
        tasks=[serialize_task(task) for task in tasks],
        stats=get_stats(db, current_user.id),
        recent_logs=[dict(row._mapping) for row in recent_logs],
        provider_presets=PROVIDER_PRESETS,
    )


@router.put("/preferences")
def update_preferences(
    payload: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.focus_minutes = payload.focus_minutes
    current_user.break_minutes = payload.break_minutes
    current_user.quiet_hours = payload.quiet_hours.strip()
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return {"user": UserOut.model_validate(current_user)}


@router.post("/goals/analyze")
def analyze_goal(
    payload: GoalAnalyzeRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        ai_config = resolve_ai_config(payload.ai_config)
        result = generate_goal_plan(
            ai_config,
            payload.goal_text.strip(),
            current_user.focus_minutes,
            current_user.break_minutes,
            current_user.quiet_hours,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        **result.model_dump(mode="json"),
        "provider": ai_config.provider,
        "model": ai_config.model,
    }


@router.post("/goals/confirm", status_code=status.HTTP_201_CREATED)
def confirm_goal(
    payload: GoalConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    goal = Goal(
        user_id=current_user.id,
        content=payload.goal_text.strip(),
        due_date=parse_due_date(payload.goal_text.strip()),
        feedback=payload.agent_feedback.strip(),
    )
    db.add(goal)
    db.flush()
    created_tasks = []
    for index, task in enumerate(payload.tasks):
        item = Task(
            user_id=current_user.id,
            goal_id=goal.id,
            title=task.title,
            description=task.description,
            scheduled_for=task.scheduled_for,
            due_at=task.due_at,
            status="todo",
            estimated_minutes=task.estimated_minutes,
            order_index=index,
        )
        db.add(item)
        created_tasks.append(item)
    db.commit()
    for item in created_tasks:
        db.refresh(item)
    return {
        "message": "正式任务已同步到看板",
        "goal_id": goal.id,
        "tasks": [serialize_task(task) for task in created_tasks],
    }


@router.post("/review/generate")
def generate_ai_review(
    payload: ReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = db.scalars(select(Task).where(Task.user_id == current_user.id).order_by(Task.updated_at.desc())).all()
    stats = get_stats(db, current_user.id)
    try:
        ai_config = resolve_ai_config(payload.ai_config)
        review = generate_review(ai_config, stats, [serialize_task(task) for task in tasks])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "review": review.review,
        "provider": ai_config.provider,
        "model": ai_config.model,
    }


@router.patch("/tasks/{task_id}/status")
def update_task_status(
    task_id: int,
    payload: TaskStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == current_user.id))
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task.status = payload.status
    task.updated_at = datetime.now().astimezone()
    if payload.status == "in_progress":
        task.last_started_at = datetime.now().astimezone()
    if payload.status == "done":
        task.completed_at = datetime.now().astimezone()
    else:
        task.completed_at = None
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"task": serialize_task(task)}


@router.patch("/tasks/{task_id}")
def edit_task(
    task_id: int,
    payload: TaskEditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == current_user.id))
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task.title = payload.title
    task.description = payload.description
    task.scheduled_for = payload.scheduled_for
    task.due_at = payload.due_at
    task.estimated_minutes = payload.estimated_minutes
    task.updated_at = datetime.now().astimezone()
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"task": serialize_task(task)}


@router.post("/tasks/postpone")
def postpone_task(
    payload: TaskPostponeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.scalar(select(Task).where(Task.id == payload.task_id, Task.user_id == current_user.id))
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    anchor = task.scheduled_for or task.due_at or datetime.now().astimezone()
    task.scheduled_for = anchor + timedelta(minutes=payload.minutes)
    task.status = "todo"
    task.delay_count += 1
    task.updated_at = datetime.now().astimezone()
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"task": serialize_task(task)}


@router.post("/pomodoro/start", response_model=PomodoroStartResponse, status_code=status.HTTP_201_CREATED)
def start_pomodoro(
    payload: PomodoroStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PomodoroStartResponse:
    task = db.scalar(select(Task).where(Task.id == payload.task_id, Task.user_id == current_user.id))
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task.status = "in_progress"
    task.last_started_at = datetime.now().astimezone()
    task.updated_at = datetime.now().astimezone()
    log = PomodoroLog(
        user_id=current_user.id,
        task_id=task.id,
        planned_minutes=payload.planned_minutes,
        status="running",
    )
    db.add(task)
    db.add(log)
    db.commit()
    db.refresh(log)
    return PomodoroStartResponse(log_id=log.id, planned_minutes=payload.planned_minutes)


@router.post("/pomodoro/finish")
def finish_pomodoro(
    payload: PomodoroFinishRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log = db.scalar(
        select(PomodoroLog).where(
            PomodoroLog.id == payload.log_id,
            PomodoroLog.task_id == payload.task_id,
            PomodoroLog.user_id == current_user.id,
        )
    )
    if not log:
        raise HTTPException(status_code=404, detail="番茄记录不存在")
    task = db.scalar(select(Task).where(Task.id == payload.task_id, Task.user_id == current_user.id))
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    log.actual_seconds = payload.actual_seconds
    log.end_time = datetime.now().astimezone()
    log.status = payload.result
    task.updated_at = datetime.now().astimezone()
    if payload.result == "done":
        task.status = "done"
        task.completed_at = datetime.now().astimezone()
    else:
        task.status = "todo"
    db.add(log)
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"task": serialize_task(task)}
