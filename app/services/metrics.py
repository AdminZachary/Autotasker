from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PomodoroLog, Task


PERIOD_LABELS = {
    "morning": "上午高效",
    "afternoon": "下午稳定",
    "evening": "晚上高效",
    "night": "深夜灵感",
}


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


def get_period_key(dt: Optional[datetime]) -> str:
    dt = normalize_dt(dt)
    hour = dt.hour if dt else 9
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 24:
        return "evening"
    return "night"


def infer_task_style(avg_focus_minutes: float) -> tuple[str, str]:
    if avg_focus_minutes >= 50:
        return "deep_work", "更适合 50 分钟以上的深度专注块"
    if avg_focus_minutes >= 30:
        return "balanced", "适合 30-50 分钟的均衡节奏"
    return "short_sprint", "更适合 15-30 分钟的短冲刺"


def infer_discipline(delay_total: int, task_count: int) -> tuple[str, str]:
    if task_count <= 0:
        return "unknown", "还没有足够的执行数据"
    ratio = delay_total / max(task_count, 1)
    if ratio >= 1.2:
        return "needs_buffer", "排程容易偏紧，建议预留缓冲"
    if ratio >= 0.5:
        return "adaptive", "会根据现实节奏调整计划"
    return "steady", "计划执行相对稳定"


def build_user_profile_summary(profile: dict) -> str:
    return (
        f"用户通常在{profile['peak_period_label']}，建议优先安排高价值任务在{profile['suggested_focus_window']}。"
        f"{profile['preferred_task_style_label']}，当前执行纪律判断为：{profile['scheduling_discipline_label']}。"
    )


def get_user_profile(db: Session, user_id: int) -> dict:
    logs = db.scalars(
        select(PomodoroLog).where(PomodoroLog.user_id == user_id).order_by(PomodoroLog.start_time.desc()).limit(200)
    ).all()
    tasks = db.scalars(select(Task).where(Task.user_id == user_id)).all()

    period_stats = {
        key: {
            "key": key,
            "label": PERIOD_LABELS[key],
            "focus_minutes": 0,
            "completed_sessions": 0,
            "total_sessions": 0,
            "completion_rate": 0.0,
        }
        for key in PERIOD_LABELS
    }

    total_focus_minutes = 0
    completed_sessions = 0
    for log in logs:
        key = get_period_key(log.start_time)
        minutes = int((log.actual_seconds or 0) / 60)
        period_stats[key]["focus_minutes"] += minutes
        period_stats[key]["total_sessions"] += 1
        total_focus_minutes += minutes
        if log.status == "done":
            period_stats[key]["completed_sessions"] += 1
            completed_sessions += 1

    for stats in period_stats.values():
        total = stats["total_sessions"]
        done = stats["completed_sessions"]
        stats["completion_rate"] = round(done / total, 2) if total else 0.0

    ordered_periods = list(period_stats.values())
    peak_period = max(
        ordered_periods,
        key=lambda item: (item["focus_minutes"], item["completed_sessions"], item["completion_rate"]),
    )

    avg_focus_minutes = total_focus_minutes / max(len(logs), 1) if logs else 0
    preferred_task_style, preferred_task_style_label = infer_task_style(avg_focus_minutes)
    delay_total = sum(task.delay_count for task in tasks)
    scheduling_discipline, scheduling_discipline_label = infer_discipline(delay_total, len(tasks))
    profile = {
        "peak_period": peak_period["key"],
        "peak_period_label": peak_period["label"],
        "preferred_task_style": preferred_task_style,
        "preferred_task_style_label": preferred_task_style_label,
        "scheduling_discipline": scheduling_discipline,
        "scheduling_discipline_label": scheduling_discipline_label,
        "suggested_focus_window": peak_period["label"],
        "total_focus_minutes": total_focus_minutes,
        "total_completed_sessions": completed_sessions,
        "period_breakdown": ordered_periods,
    }
    profile["summary"] = build_user_profile_summary(profile)
    return profile
