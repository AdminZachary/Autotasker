import os
import random
import string
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as database
from app.database import Base
from app.main import app
from app.schemas import GoalDiscussionSchema, GoalPlanSchema, ReviewSchema


def build_task(title: str, start: str, end: str, minutes: int = 30) -> dict:
    return {
        "title": title,
        "description": f"{title} 的执行说明",
        "scheduled_for": start,
        "due_at": end,
        "estimated_minutes": minutes,
    }


class AutoTaskerFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def setUp(self):
        self.db_path = os.path.join(self.tempdir.name, f"autotasker-test-{random.randint(1, 10_000_000)}.db")
        engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        database.engine = engine
        database.SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def auth_headers(self) -> dict:
        response = self.client.post(
            "/api/auth/register",
            json={"username": "tester", "password": "password123"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}

    def test_analyze_discuss_confirm_flow(self):
        headers = self.auth_headers()

        initial_plan = GoalPlanSchema(
            status="ok",
            agent_feedback="我先给你一版适合上午推进的初版草案。",
            staging_tasks=[
                build_task("调研竞品", "2026-05-20T09:00:00+08:00", "2026-05-20T09:40:00+08:00", 40),
                build_task("整理访谈提纲", "2026-05-20T10:00:00+08:00", "2026-05-20T10:30:00+08:00", 30),
            ],
        )
        discussed_plan_1 = GoalDiscussionSchema(
            assistant_message="我把高价值任务前移到了上午，并拆细了第一项。",
            updated_plan=[
                build_task("调研竞品清单", "2026-05-20T08:40:00+08:00", "2026-05-20T09:10:00+08:00", 30),
                build_task("撰写竞品对比", "2026-05-20T09:20:00+08:00", "2026-05-20T10:00:00+08:00", 40),
                build_task("整理访谈提纲", "2026-05-20T10:20:00+08:00", "2026-05-20T10:50:00+08:00", 30),
            ],
        )
        discussed_plan_2 = GoalDiscussionSchema(
            assistant_message="我把晚上的轻量整理保留，上午继续作为主攻时段。",
            updated_plan=[
                build_task("调研竞品清单", "2026-05-20T08:40:00+08:00", "2026-05-20T09:10:00+08:00", 30),
                build_task("撰写竞品对比", "2026-05-20T09:20:00+08:00", "2026-05-20T10:00:00+08:00", 40),
                build_task("整理访谈提纲", "2026-05-20T19:30:00+08:00", "2026-05-20T20:00:00+08:00", 30),
            ],
        )

        with patch("app.api.generate_goal_plan_with_profile", return_value=initial_plan):
            analyze_response = self.client.post(
                "/api/goals/analyze",
                headers=headers,
                json={
                    "goal_text": "在 2026-05-22 前完成调研方案",
                    "ai_config": {
                        "provider": "openai",
                        "model": "gpt-test",
                        "api_key": "test-key",
                        "base_url": "https://api.openai.com/v1",
                    },
                },
            )
        self.assertEqual(analyze_response.status_code, 200, analyze_response.text)
        self.assertEqual(len(analyze_response.json()["staging_tasks"]), 2)

        discuss_payload = {
            "goal_text": "在 2026-05-22 前完成调研方案",
            "current_plan": analyze_response.json()["staging_tasks"],
            "conversation": [{"role": "assistant", "content": analyze_response.json()["agent_feedback"]}],
            "user_message": "把重要任务都前移到上午，并拆细第一项",
            "actions": ["split_tasks", "raise_priority"],
            "version": 1,
            "ai_config": {
                "provider": "openai",
                "model": "gpt-test",
                "api_key": "test-key",
                "base_url": "https://api.openai.com/v1",
            },
        }
        with patch("app.api.generate_goal_discussion", return_value=discussed_plan_1):
            discuss_response = self.client.post("/api/goals/discuss", headers=headers, json=discuss_payload)
        self.assertEqual(discuss_response.status_code, 200, discuss_response.text)
        self.assertEqual(discuss_response.json()["version"], 2)
        self.assertEqual(len(discuss_response.json()["updated_plan"]), 3)

        discuss_payload["current_plan"] = discuss_response.json()["updated_plan"]
        discuss_payload["conversation"].extend(
            [
                {"role": "user", "content": "把重要任务都前移到上午，并拆细第一项"},
                {"role": "assistant", "content": discuss_response.json()["assistant_message"]},
            ]
        )
        discuss_payload["user_message"] = "保留晚上轻量整理，但上午仍然是主攻时段"
        discuss_payload["actions"] = []
        discuss_payload["version"] = 2
        with patch("app.api.generate_goal_discussion", return_value=discussed_plan_2):
            discuss_response_2 = self.client.post("/api/goals/discuss", headers=headers, json=discuss_payload)
        self.assertEqual(discuss_response_2.status_code, 200, discuss_response_2.text)
        self.assertEqual(discuss_response_2.json()["version"], 3)

        confirm_response = self.client.post(
            "/api/goals/confirm",
            headers=headers,
            json={
                "goal_text": "在 2026-05-22 前完成调研方案",
                "agent_feedback": discuss_response_2.json()["assistant_message"],
                "tasks": discuss_response_2.json()["updated_plan"],
            },
        )
        self.assertEqual(confirm_response.status_code, 201, confirm_response.text)
        self.assertEqual(len(confirm_response.json()["tasks"]), 3)

        bootstrap_response = self.client.get("/api/bootstrap", headers=headers)
        self.assertEqual(bootstrap_response.status_code, 200, bootstrap_response.text)
        payload = bootstrap_response.json()
        self.assertEqual(len(payload["tasks"]), 3)
        self.assertIn("user_profile", payload)
        self.assertIn("period_breakdown", payload["user_profile"])

    def test_review_and_profile_endpoint_shape(self):
        headers = self.auth_headers()

        with patch("app.api.generate_review", return_value=ReviewSchema(review="建议继续把高价值任务放在上午。")):
            review_response = self.client.post(
                "/api/review/generate",
                headers=headers,
                json={
                    "ai_config": {
                        "provider": "openai",
                        "model": "gpt-test",
                        "api_key": "test-key",
                        "base_url": "https://api.openai.com/v1",
                    }
                },
            )
        self.assertEqual(review_response.status_code, 200, review_response.text)
        self.assertIn("review", review_response.json())

        bootstrap_response = self.client.get("/api/bootstrap", headers=headers)
        self.assertEqual(bootstrap_response.status_code, 200, bootstrap_response.text)
        profile = bootstrap_response.json()["user_profile"]
        self.assertIn("summary", profile)
        self.assertIn("peak_period_label", profile)
        self.assertIn("suggested_focus_window", profile)

    def test_discuss_fuzz_smoke_never_returns_500(self):
        headers = self.auth_headers()

        with patch(
            "app.api.generate_goal_discussion",
            return_value=GoalDiscussionSchema(
                assistant_message="我保留了当前草案，并按你的表达做了稳妥解释。",
                updated_plan=[build_task("任务 A", "2026-05-20T09:00:00+08:00", "2026-05-20T09:30:00+08:00", 30)],
            ),
        ):
            alphabet = string.ascii_letters + string.digits + "测试用户画像🙂\n\t!@#$%^&*()[]{}"
            for _ in range(25):
                message = "".join(random.choice(alphabet) for _ in range(random.randint(1, 120)))
                response = self.client.post(
                    "/api/goals/discuss",
                    headers=headers,
                    json={
                        "goal_text": "在 2026-05-22 前完成调研方案",
                        "current_plan": [build_task("任务 A", "2026-05-20T09:00:00+08:00", "2026-05-20T09:30:00+08:00", 30)],
                        "conversation": [{"role": "assistant", "content": "初版草案已生成"}],
                        "user_message": message,
                        "actions": [],
                        "version": 1,
                        "ai_config": {
                            "provider": "openai",
                            "model": "gpt-test",
                            "api_key": "test-key",
                            "base_url": "https://api.openai.com/v1",
                        },
                    },
                )
                self.assertIn(response.status_code, (200, 422), response.text)

    def test_discuss_rejects_invalid_action(self):
        headers = self.auth_headers()
        response = self.client.post(
            "/api/goals/discuss",
            headers=headers,
            json={
                "goal_text": "在 2026-05-22 前完成调研方案",
                "current_plan": [build_task("任务 A", "2026-05-20T09:00:00+08:00", "2026-05-20T09:30:00+08:00", 30)],
                "conversation": [{"role": "assistant", "content": "初版草案已生成"}],
                "user_message": "",
                "actions": ["hack_schedule"],
                "version": 1,
                "ai_config": {
                    "provider": "openai",
                    "model": "gpt-test",
                    "api_key": "test-key",
                    "base_url": "https://api.openai.com/v1",
                },
            },
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
