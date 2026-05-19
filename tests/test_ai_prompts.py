import unittest

from app.schemas import DraftConversationMessage, StageTaskSchema
from app.services.ai import build_discussion_prompts, build_goal_prompts


class PromptBuilderTests(unittest.TestCase):
    def test_goal_prompt_contains_user_profile_summary(self):
        _, prompt = build_goal_prompts(
            "在 2026-05-22 前完成调研方案",
            25,
            5,
            "12:00-14:00",
            "用户通常在上午高效，适合先安排高价值任务。",
        )
        self.assertIn("历史执行特征", prompt)
        self.assertIn("上午高效", prompt)

    def test_discussion_prompt_contains_conversation_and_actions(self):
        current_plan = [
            StageTaskSchema(
                title="调研竞品",
                description="先收集对标信息",
                scheduled_for="2026-05-20T09:00:00+08:00",
                due_at="2026-05-20T09:40:00+08:00",
                estimated_minutes=40,
            )
        ]
        conversation = [
            DraftConversationMessage(role="assistant", content="我先安排一版上午优先的草案。"),
            DraftConversationMessage(role="user", content="把任务拆得更细一点。"),
        ]
        _, prompt = build_discussion_prompts(
            "在 2026-05-22 前完成调研方案",
            current_plan,
            conversation,
            "把重要任务都前移到上午",
            ["split_tasks", "raise_priority"],
            25,
            5,
            "12:00-14:00",
            "用户晚上完成率更低，建议上午主攻。",
        )
        self.assertIn("当前草案", prompt)
        self.assertIn("历史讨论", prompt)
        self.assertIn("拆小任务", prompt)
        self.assertIn("提高优先级", prompt)
        self.assertIn("上午主攻", prompt)


if __name__ == "__main__":
    unittest.main()
