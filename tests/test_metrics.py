import os
import tempfile
import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.database as database
from app.database import Base
from app.models import Goal, PomodoroLog, Task, User
from app.services.metrics import get_user_profile, serialize_task


class MetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def setUp(self):
        self.db_path = os.path.join(self.tempdir.name, "metrics-test.db")
        engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        database.engine = engine
        database.SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = Session(engine)

        self.user = User(username="metrics-user", password_hash="hashed")
        self.db.add(self.user)
        self.db.flush()
        self.goal = Goal(user_id=self.user.id, content="完成论文初稿")
        self.db.add(self.goal)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_profile_prefers_morning_when_focus_logs_cluster_there(self):
        morning_start = datetime.now().astimezone().replace(hour=9, minute=0, second=0, microsecond=0)
        evening_start = datetime.now().astimezone().replace(hour=20, minute=0, second=0, microsecond=0)

        task = Task(
            user_id=self.user.id,
            goal_id=self.goal.id,
            title="写作",
            description="撰写核心章节",
            scheduled_for=morning_start,
            due_at=morning_start + timedelta(minutes=50),
            status="done",
            estimated_minutes=50,
            order_index=0,
            delay_count=0,
            completed_at=morning_start + timedelta(minutes=50),
        )
        self.db.add(task)
        self.db.flush()

        logs = [
            PomodoroLog(
                user_id=self.user.id,
                task_id=task.id,
                start_time=morning_start + timedelta(days=offset),
                end_time=morning_start + timedelta(days=offset, minutes=50),
                actual_seconds=50 * 60,
                planned_minutes=50,
                status="done",
            )
            for offset in range(3)
        ]
        logs.append(
            PomodoroLog(
                user_id=self.user.id,
                task_id=task.id,
                start_time=evening_start,
                end_time=evening_start + timedelta(minutes=20),
                actual_seconds=20 * 60,
                planned_minutes=25,
                status="interrupted",
            )
        )
        self.db.add_all(logs)
        self.db.commit()

        profile = get_user_profile(self.db, self.user.id)

        self.assertEqual(profile["peak_period"], "morning")
        self.assertIn("上午高效", profile["summary"])
        self.assertEqual(profile["preferred_task_style"], "balanced")
        self.assertEqual(profile["total_completed_sessions"], 3)

    def test_profile_without_logs_returns_observation_defaults(self):
        profile = get_user_profile(self.db, self.user.id)
        self.assertEqual(profile["peak_period"], "morning")
        self.assertEqual(profile["total_focus_minutes"], 0)
        self.assertIn("建议优先安排高价值任务", profile["summary"])
        self.assertEqual(len(profile["period_breakdown"]), 4)

    def test_serialize_task_marks_overdue(self):
        due_at = datetime.now().astimezone() - timedelta(hours=2)
        task = Task(
            user_id=self.user.id,
            goal_id=self.goal.id,
            title="补材料",
            scheduled_for=due_at - timedelta(hours=1),
            due_at=due_at,
            status="todo",
            estimated_minutes=30,
            order_index=0,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        payload = serialize_task(task)
        self.assertTrue(payload["overdue"])


if __name__ == "__main__":
    unittest.main()
