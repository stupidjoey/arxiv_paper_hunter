from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import logging
import re
from typing import Optional

import requests

from .config import ArchivistConfig
from .harvester import Paper

logger = logging.getLogger(__name__)


def slugify(text: str, max_length: int = 80) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if len(text) > max_length:
        text = text[:max_length].rstrip("_")
    return text or "paper"


def extract_date(paper: Paper) -> str:
    for field in (paper.published, paper.updated):
        if field:
            return field.split("T")[0]
    return date.today().isoformat()


@dataclass
class Archivist:
    config: ArchivistConfig = field(default_factory=ArchivistConfig)

    def ensure_folder(self, day: str) -> Path:
        target = self.config.base_dir / day
        target.mkdir(parents=True, exist_ok=True)
        return target

    def build_pdf_path(self, paper: Paper, company: Optional[str]) -> Path:
        day = extract_date(paper)
        folder = self.ensure_folder(day)
        company_token = slugify(company) if company else "unknown"
        author_token = slugify(paper.first_author)
        title_token = slugify(paper.title)
        filename = f"{day}_{company_token}_{author_token}_{title_token}.pdf"
        return folder / filename

    def download_pdf(self, paper: Paper, company: Optional[str]) -> Path:
        if not paper.pdf_url:
            raise ValueError(f"No PDF URL for paper {paper.arxiv_id}")

        target_path = self.build_pdf_path(paper, company)
        logger.info("Downloading %s to %s", paper.pdf_url, target_path)
        with requests.get(paper.pdf_url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(target_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return target_path

    def write_summary_markdown(self, pdf_path: Path, summary: str, header: str) -> Path:
        md_path = pdf_path.with_suffix(".md")
        md_path.write_text(f"# {header}\n\n{summary}\n", encoding="utf-8")
        self._append_to_daily_summary(pdf_path.parent, header, summary)
        return md_path

    def _append_to_daily_summary(self, folder: Path, header: str, summary: str) -> None:
        summary_path = folder / "Summary.md"
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(f"## {header}\n\n{summary}\n\n---\n\n")
