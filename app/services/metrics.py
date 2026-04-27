from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PomodoroLog, Task


def normalize_dt(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return value


def serialize_task(task: Task) -> dict:
    now = datetime.now().astimezone()
    due_at = normalize_dt(task.due_at)
    scheduled_for = normalize_dt(task.scheduled_for)
    last_started_at = normalize_dt(task.last_started_at)
    completed_at = normalize_dt(task.completed_at)
    updated_at = normalize_dt(task.updated_at)
    overdue = bool(due_at and task.status != "done" and due_at < now)
    return {
        "id": task.id,
        "goal_id": task.goal_id,
        "title": task.title,
        "description": task.description or "",
        "scheduled_for": scheduled_for,
        "due_at": due_at,
        "status": task.status,
        "estimated_minutes": task.estimated_minutes,
        "order_index": task.order_index,
        "delay_count": task.delay_count,
        "last_started_at": last_started_at,
        "completed_at": completed_at,
        "updated_at": updated_at or now,
        "overdue": overdue,
    }


def build_local_review(stats: dict) -> str:
    notes = []
    if stats["total_tasks"] == 0:
        return "当前还没有正式任务，先生成并确认一组草案。"
    if stats["overdue_tasks"] > 0:
        notes.append("有逾期任务，说明当前排程偏紧。")
    if stats["delay_total"] >= max(2, stats["done_tasks"]):
        notes.append("延期次数偏高，建议把任务切得更小。")
    if stats["focus_minutes_total"] < 60:
        notes.append("当前专注时长偏少，可以先稳定每天 1-2 个番茄。")
    if stats["completion_rate"] >= 0.6:
        notes.append("完成率不错，下一轮可以细化任务说明。")
    if not notes:
        notes.append("整体节奏稳定，可以聚焦最常被延期的任务类型。")
    return " ".join(notes)


def get_stats(db: Session, user_id: int) -> dict:
    total_tasks = db.scalar(select(func.count(Task.id)).where(Task.user_id == user_id)) or 0
    done_tasks = db.scalar(select(func.count(Task.id)).where(Task.user_id == user_id, Task.status == "done")) or 0
    in_progress_tasks = db.scalar(
        select(func.count(Task.id)).where(Task.user_id == user_id, Task.status == "in_progress")
    ) or 0
    todo_tasks = db.scalar(select(func.count(Task.id)).where(Task.user_id == user_id, Task.status == "todo")) or 0
    overdue_tasks = db.scalar(
        select(func.count(Task.id)).where(
            Task.user_id == user_id,
            Task.status != "done",
            Task.due_at.is_not(None),
            Task.due_at < datetime.now().astimezone(),
        )
    ) or 0
    delay_total = db.scalar(select(func.coalesce(func.sum(Task.delay_count), 0)).where(Task.user_id == user_id)) or 0
    focus_minutes_total = int(
        (db.scalar(select(func.coalesce(func.sum(PomodoroLog.actual_seconds), 0)).where(PomodoroLog.user_id == user_id)) or 0)
        / 60
    )
    trend_rows = db.execute(
        select(func.date(Task.completed_at), func.count(Task.id))
        .where(Task.user_id == user_id, Task.completed_at.is_not(None))
        .group_by(func.date(Task.completed_at))
        .order_by(func.date(Task.completed_at).desc())
        .limit(7)
    ).all()
    trend = [{"day": str(row[0]), "count": row[1]} for row in reversed(trend_rows)]
    completion_rate = round(done_tasks / total_tasks, 2) if total_tasks else 0
    stats = {
        "total_tasks": total_tasks,
        "done_tasks": done_tasks,
        "in_progress_tasks": in_progress_tasks,
        "todo_tasks": todo_tasks,
        "overdue_tasks": overdue_tasks,
        "delay_total": int(delay_total),
        "focus_minutes_total": focus_minutes_total,
        "completion_rate": completion_rate,
        "trend": trend,
    }
    stats["review"] = build_local_review(stats)
    return stats
