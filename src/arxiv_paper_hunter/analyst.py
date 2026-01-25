from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import logging
import textwrap
from typing import Any, Dict

import requests

from .config import AnalystConfig
from .harvester import Paper

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency
    PdfReader = None


SUMMARY_PROMPT = """\
你是一名资深推荐算法工程师。请阅读这篇论文，并输出 JSON 格式的总结，字段：
1. 一句话核心创新点 (one_liner)
2. 解决的问题 (problem)
3. 核心方法/架构 (method)
4. 实验结论 (results)
5. 工业界应用价值：评分 1-5 及理由 (industry_value)
仅返回 JSON。
"""


class Analyst:
    def __init__(self, config: AnalystConfig | None = None):
        self.config = config or AnalystConfig()

    def summarize_pdf(self, pdf_path: Path) -> str:
        if not self.config.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set; cannot run summarization.")
        text = self._extract_text(pdf_path, max_pages=6)
        content = f"{SUMMARY_PROMPT}\n\n论文内容（截断预览）:\n{text}"
        completion = self._chat_completion(content)
        return completion

    def translate_abstract(self, paper: Paper) -> str:
        if not self.config.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set; cannot translate.")
        prompt = textwrap.dedent(
            f"""
            Translate the following arXiv paper abstract from English to Chinese.
            Preserve named entities and keep it concise.

            Title: {paper.title}
            Abstract: {paper.summary}
            """
        ).strip()
        return self._chat_completion(prompt, temperature=0.2)

    def llm_vote_is_industry(self, paper: Paper, companies: list[str]) -> bool:
        if not self.config.api_key:
            return False
        prompt = textwrap.dedent(
            f"""
            你是审稿人，请判断作者单位是否包含以下公司之一：
            {', '.join(companies)}
            论文：
            Title: {paper.title}
            Authors: {', '.join([a.name for a in paper.authors])}
            Abstract: {paper.summary}
            回复 yes 或 no。
            """
        ).strip()
        reply = self._chat_completion(prompt, temperature=0)
        return "yes" in reply.lower()

    def _chat_completion(
        self,
        content: str,
        temperature: float = 0.2,
    ) -> str:
        url = self._resolve_endpoint()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": content},
            ],
            "max_tokens": min(self.config.max_tokens, 8192),
            "temperature": temperature,
        }
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
        if resp.status_code >= 400:
            # Surface server message to help debug credentials/endpoint/payload issues.
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise requests.HTTPError(f"{resp.status_code} {detail}", response=resp)
        data = resp.json()
        message = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return message.strip()

    def _resolve_endpoint(self) -> str:
        base = (self.config.base_url or "https://api.deepseek.com/v1/chat/completions").rstrip("/")
        # Normalize common inputs to the required /v1/chat/completions path.
        if base.endswith("api.deepseek.com") or base.endswith("api.deepseek.com/api"):
            return base + "/v1/chat/completions"
        if base.endswith("api.deepseek.com/chat/completions"):
            return base.replace("api.deepseek.com/chat/completions", "api.deepseek.com/v1/chat/completions")
        return base

    def _extract_text(self, pdf_path: Path, max_pages: int = 5) -> str:
        if PdfReader is None:
            raise RuntimeError("pypdf is required for PDF parsing. Please install it.")
        reader = PdfReader(pdf_path)
        pages = []
        for idx, page in enumerate(reader.pages[:max_pages]):
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to read page %s: %s", idx, exc)
        text = "\n".join(pages)
        return textwrap.shorten(text, width=4000, placeholder=" ...")
