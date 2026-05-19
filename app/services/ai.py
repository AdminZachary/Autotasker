import json
from datetime import datetime
from urllib.parse import urlparse

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from app.config import settings
from app.schemas import AIConfig, DraftConversationMessage, GoalDiscussionSchema, GoalPlanSchema, ReviewSchema, StageTaskSchema


PROVIDER_PRESETS = {
    "openai": "https://api.openai.com/v1",
    "azure_openai": settings.azure_openai_endpoint or "",
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}


def get_provider_base_url(provider: str) -> str:
    return PROVIDER_PRESETS.get(provider, "")


def build_goal_prompts(
    goal_text: str,
    focus_minutes: int,
    break_minutes: int,
    quiet_hours: str,
    user_profile_summary: str,
) -> tuple[str, str]:
    current = datetime.now().astimezone()
    system_prompt = (
        "你是 AutoTasker 的任务规划智能体。"
        "你负责把自然语言目标拆解成可以直接进入暂存区的结构化任务草案。"
        "任务安排必须使用绝对日期和时间，不能使用相对日期。"
    )
    user_prompt = f"""
当前服务器时间：{current.isoformat(timespec="minutes")}
当前时区：{current.tzname() or "local"}
用户偏好：
- 番茄默认时长：{focus_minutes} 分钟
- 休息时长：{break_minutes} 分钟
- 不可安排时间：{quiet_hours}
- 历史执行特征：{user_profile_summary}

用户目标：
{goal_text}

请返回任务规划结果。
要求：
1. 如果目标明显不合理、太空泛、截止日期已过，返回 suggest_adjustment 且不生成任务。
2. 如果目标合理，生成 4-8 个任务。
3. 每个任务都要有清晰标题、说明、开始时间、截止时间和分钟数。
4. 单个任务 15-180 分钟。
5. 时间要避开不可安排时段。
6. 任务覆盖准备、主体推进、检查收尾。
7. 不要输出 Markdown。
""".strip()
    return system_prompt, user_prompt


def build_discussion_prompts(
    goal_text: str,
    current_plan: list[StageTaskSchema],
    conversation: list[DraftConversationMessage],
    user_message: str,
    actions: list[str],
    focus_minutes: int,
    break_minutes: int,
    quiet_hours: str,
    user_profile_summary: str,
) -> tuple[str, str]:
    current = datetime.now().astimezone()
    action_labels = {
        "split_tasks": "拆小任务",
        "compress_schedule": "压缩到更短周期",
        "delay_one_day": "整体推迟一天",
        "avoid_quiet_hours": "严格避开安静时段",
        "raise_priority": "提高优先级",
    }
    current_plan_json = json.dumps([task.model_dump(mode="json") for task in current_plan], ensure_ascii=False, indent=2)
    conversation_json = json.dumps([item.model_dump(mode="json") for item in conversation], ensure_ascii=False, indent=2)
    action_text = "、".join(action_labels.get(item, item) for item in actions) or "无"
    system_prompt = (
        "你是 AutoTasker 的草案讨论智能体。"
        "你必须基于当前任务草案做增量调整，而不是忽略上下文完全重写。"
        "你需要同时返回给用户看的解释，以及系统可直接采用的结构化新版草案。"
        "除非用户明确要求删除、合并或改写，否则要尽量保留已有任务的核心意图。"
        "任务安排必须使用绝对日期和时间，不能使用相对日期。"
    )
    user_prompt = f"""
当前服务器时间：{current.isoformat(timespec="minutes")}
当前时区：{current.tzname() or "local"}
用户偏好：
- 番茄默认时长：{focus_minutes} 分钟
- 休息时长：{break_minutes} 分钟
- 不可安排时间：{quiet_hours}
- 历史执行特征：{user_profile_summary}

用户总目标：
{goal_text}

当前草案：
{current_plan_json}

历史讨论：
{conversation_json}

本轮用户输入：
{user_message or "（本轮仅使用快捷动作）"}

本轮快捷动作：
{action_text}

要求：
1. 先理解用户本轮意图，再在当前草案上做增量调整。
2. 允许拒绝不合理要求，但必须解释原因，并给出可执行替代方案。
3. assistant_message 使用中文，简洁说明你做了什么调整。
4. updated_plan 必须保留至少 1 个任务，不能输出空列表。
5. 每个任务都要有标题、说明、开始时间、截止时间和分钟数。
6. 单个任务 15-180 分钟。
7. 时间必须避开不可安排时段，且优先利用用户更高效的时段安排高价值任务。
8. 不要输出 Markdown。
""".strip()
    return system_prompt, user_prompt


def build_review_prompts(stats: dict, tasks: list[dict]) -> tuple[str, str]:
    system_prompt = (
        "你是 AutoTasker 的复盘智能体。"
        "你需要基于执行数据给出简洁、具体、可落地的阶段性建议。"
    )
    user_prompt = f"""
统计数据：
{stats}

任务快照：
{tasks}

要求：
1. 输出中文。
2. 先指出主要瓶颈，再给出下一步行动。
3. 控制在 120 字以内。
""".strip()
    return system_prompt, user_prompt


def build_langchain_model(ai_config: AIConfig):
    if ai_config.provider == "azure_openai":
        endpoint = ai_config.base_url or get_provider_base_url("azure_openai")
        if not endpoint:
            raise ValueError("Azure OpenAI 缺少 Endpoint，请在页面填写，或在 .env 中配置 AZURE_OPENAI_ENDPOINT")
        if not settings.azure_openai_api_version:
            raise ValueError("Azure OpenAI 缺少 API Version，请在 .env 中配置 AZURE_OPENAI_API_VERSION")
        return AzureChatOpenAI(
            azure_deployment=ai_config.model,
            api_key=ai_config.api_key,
            azure_endpoint=endpoint,
            api_version=settings.azure_openai_api_version,
            temperature=0.2,
            timeout=25,
            max_retries=0,
        )
    if ai_config.provider == "gemini":
        endpoint = ai_config.base_url or get_provider_base_url("gemini")
        parsed = urlparse(endpoint)
        api_endpoint = parsed.netloc or endpoint.replace("https://", "").replace("http://", "").split("/", 1)[0]
        return ChatGoogleGenerativeAI(
            model=ai_config.model,
            api_key=ai_config.api_key,
            temperature=0.2,
            request_timeout=25,
            client_options={"api_endpoint": api_endpoint or "generativelanguage.googleapis.com"},
        )
    return ChatOpenAI(
        model=ai_config.model,
        api_key=ai_config.api_key,
        base_url=ai_config.base_url or get_provider_base_url(ai_config.provider),
        temperature=0.2,
        timeout=25,
        max_retries=0,
    )


def invoke_structured(ai_config: AIConfig, schema, system_prompt: str, user_prompt: str):
    llm = build_langchain_model(ai_config)
    method = "function_calling" if ai_config.provider != "gemini" else None
    structured_llm = llm.with_structured_output(schema, method=method) if method else llm.with_structured_output(schema)
    last_error = None
    prompt = user_prompt
    for _ in range(3):
        try:
            return structured_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
        except Exception as exc:
            last_error = exc
            prompt = (
                f"{user_prompt}\n\n"
                "注意：你上一轮输出未通过结构校验。"
                "这次请严格按照 schema 返回，不要输出解释文字。"
            )
    raise ValueError("AI 调用失败: %s" % last_error)


def generate_goal_plan(ai_config: AIConfig, goal_text: str, focus_minutes: int, break_minutes: int, quiet_hours: str) -> GoalPlanSchema:
    system_prompt, user_prompt = build_goal_prompts(goal_text, focus_minutes, break_minutes, quiet_hours, "暂无历史执行数据")
    return invoke_structured(ai_config, GoalPlanSchema, system_prompt, user_prompt)


def generate_goal_plan_with_profile(
    ai_config: AIConfig,
    goal_text: str,
    focus_minutes: int,
    break_minutes: int,
    quiet_hours: str,
    user_profile_summary: str,
) -> GoalPlanSchema:
    system_prompt, user_prompt = build_goal_prompts(
        goal_text,
        focus_minutes,
        break_minutes,
        quiet_hours,
        user_profile_summary,
    )
    return invoke_structured(ai_config, GoalPlanSchema, system_prompt, user_prompt)


def generate_goal_discussion(
    ai_config: AIConfig,
    goal_text: str,
    current_plan: list[StageTaskSchema],
    conversation: list[DraftConversationMessage],
    user_message: str,
    actions: list[str],
    focus_minutes: int,
    break_minutes: int,
    quiet_hours: str,
    user_profile_summary: str,
) -> GoalDiscussionSchema:
    system_prompt, user_prompt = build_discussion_prompts(
        goal_text,
        current_plan,
        conversation,
        user_message,
        actions,
        focus_minutes,
        break_minutes,
        quiet_hours,
        user_profile_summary,
    )
    return invoke_structured(ai_config, GoalDiscussionSchema, system_prompt, user_prompt)


def generate_review(ai_config: AIConfig, stats: dict, tasks: list[dict]) -> ReviewSchema:
    system_prompt, user_prompt = build_review_prompts(stats, tasks)
    return invoke_structured(ai_config, ReviewSchema, system_prompt, user_prompt)
