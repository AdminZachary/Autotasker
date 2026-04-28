from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.schemas import AIConfig
from app.services.ai import get_provider_base_url


def mask_database_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    if not parsed.netloc or "@" not in parsed.netloc:
        return url
    credentials, host = parsed.netloc.rsplit("@", 1)
    if ":" not in credentials:
        return urlunsplit((parsed.scheme, f"{credentials}@{host}", parsed.path, parsed.query, parsed.fragment))
    username = credentials.split(":", 1)[0]
    masked_netloc = f"{username}:***@{host}"
    return urlunsplit((parsed.scheme, masked_netloc, parsed.path, parsed.query, parsed.fragment))


def resolve_ai_config(ai_config: AIConfig) -> AIConfig:
    api_key = ai_config.api_key
    if not api_key:
        if ai_config.provider == "openai":
            api_key = settings.openai_api_key
        elif ai_config.provider == "azure_openai":
            api_key = settings.azure_openai_api_key
        elif ai_config.provider == "deepseek":
            api_key = settings.deepseek_api_key
        elif ai_config.provider == "qwen":
            api_key = settings.qwen_api_key or settings.dashscope_api_key
        elif ai_config.provider == "glm":
            api_key = settings.zhipu_api_key
        elif ai_config.provider == "gemini":
            api_key = settings.gemini_api_key or settings.google_api_key
    if not api_key:
        raise ValueError("当前供应商没有可用的 API Key；请在页面填写，或在 .env 中配置对应环境变量")
    return AIConfig(
        provider=ai_config.provider,
        model=ai_config.model,
        api_key=api_key,
        base_url=ai_config.base_url or get_provider_base_url(ai_config.provider) or None,
    )


def database_health(db: Session) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True, "url": mask_database_url(settings.resolved_database_url)}
    except Exception as exc:
        return {"ok": False, "url": mask_database_url(settings.resolved_database_url), "error": str(exc)}
