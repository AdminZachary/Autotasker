from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    focus_minutes: Mapped[int] = mapped_column(Integer, default=25)
    break_minutes: Mapped[int] = mapped_column(Integer, default=5)
    quiet_hours: Mapped[str] = mapped_column(String(50), default="12:00-14:00")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now().astimezone)

    goals: Mapped[List["Goal"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tasks: Mapped[List["Task"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    pomodoro_logs: Mapped[List["PomodoroLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now().astimezone)

    user: Mapped["User"] = relationship(back_populates="goals")
    tasks: Mapped[List["Task"]] = relationship(back_populates="goal", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="todo", index=True)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=25)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    delay_count: Mapped[int] = mapped_column(Integer, default=0)
    last_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now().astimezone)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now().astimezone,
        onupdate=datetime.now().astimezone,
    )

    user: Mapped["User"] = relationship(back_populates="tasks")
    goal: Mapped["Goal"] = relationship(back_populates="tasks")
    pomodoro_logs: Mapped[List["PomodoroLog"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class PomodoroLog(Base):
    __tablename__ = "pomodoro_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now().astimezone)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_minutes: Mapped[int] = mapped_column(Integer, default=25)
    actual_seconds: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now().astimezone)

    user: Mapped["User"] = relationship(back_populates="pomodoro_logs")
    task: Mapped["Task"] = relationship(back_populates="pomodoro_logs")
