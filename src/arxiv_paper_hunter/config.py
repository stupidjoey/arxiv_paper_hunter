from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
import os


def default_keywords() -> list[str]:
    return [
        "recommendation system",
        "recommender system",
        "CTR prediction",
        "LLM for rec",
    ]


def default_categories() -> list[str]:
    # Recsys/IR/ML/LLM-adjacent categories.
    return [
        "cs.IR",
        "cs.LG",
        "cs.AI",
        "stat.ML",
        "cs.CL",
    ]


def default_company_whitelist() -> list[str]:
    # Regex-friendly whitelist; kept lowercase to simplify matching.
    return [
        "google",
        "deepmind",
        "meta",
        "facebook",
        "instagram",
        "bytedance",
        "tiktok",
        "douyin",
        "toutiao",
        "tencent",
        "wechat",
        "alibaba",
        "taobao",
        "tmall",
        "kuaishou",
        "xiaohongshu",
        "bilibili",
        "baidu",
        "microsoft",
        "apple",
        "amazon",
        "netflix",
    ]


@dataclass
class SearchConfig:
    keywords: list[str] = field(default_factory=default_keywords)
    categories: list[str] = field(default_factory=default_categories)
    last_n_days: int = 1  # yesterday by default
    max_results: int = 500
    page_size: int = 100

    @property
    def since(self) -> date:
        return date.today() - timedelta(days=self.last_n_days)

    @property
    def until(self) -> date:
        # Inclusive end date; use today to avoid missing late uploads in some TZs.
        return date.today()


@dataclass
class GatekeeperConfig:
    company_whitelist: list[str] = field(default_factory=default_company_whitelist)


@dataclass
class ArchivistConfig:
    base_dir: Path = Path("downloads")


@dataclass
class AnalystConfig:
    # Name of env var storing the API key; set export DEEPSEEK_API_KEY=your_key before running.
    api_key_env: str = "DEEPSEEK_API_KEY"
    model: str = os.environ.get("LLM_MODEL", "deepseek-chat")
    base_url: str | None = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1/chat/completions")
    max_tokens: int = 2048  # DeepSeek limit is 8192; keep conservative default.

    @property
    def api_key(self) -> str | None:
        # Read the API key from the named environment variable.
        return os.environ.get(self.api_key_env)


@dataclass
class AppConfig:
    search: SearchConfig = field(default_factory=SearchConfig)
    gatekeeper: GatekeeperConfig = field(default_factory=GatekeeperConfig)
    archivist: ArchivistConfig = field(default_factory=ArchivistConfig)
    analyst: AnalystConfig = field(default_factory=AnalystConfig)
    telegram: "TelegramConfig" = field(default_factory=lambda: TelegramConfig())


@dataclass
class TelegramConfig:
    token: str | None = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id: str | None = os.environ.get("TELEGRAM_CHAT_ID")
