from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Callable, Iterable

from .config import GatekeeperConfig
from .harvester import Paper

logger = logging.getLogger(__name__)


@dataclass
class FilterOutcome:
    accepted: bool
    level: str | None = None
    company: str | None = None
    evidence: str | None = None


def compile_company_pattern(companies: Iterable[str]) -> re.Pattern[str]:
    escaped = [re.escape(c.lower()) for c in companies]
    joined = "|".join(escaped)
    return re.compile(joined, re.IGNORECASE)


class Gatekeeper:
    def __init__(self, config: GatekeeperConfig | None = None):
        self.config = config or GatekeeperConfig()
        self.pattern = compile_company_pattern(self.config.company_whitelist)

    def filter(
        self,
        paper: Paper,
        email_text: str | None = None,
        llm_checker: Callable[[Paper], bool] | None = None,
    ) -> FilterOutcome:
        # Level 1: affiliation metadata
        meta_fields = []
        for author in paper.authors:
            if author.affiliation:
                meta_fields.append(author.affiliation)
        meta_fields.append(" ".join([a.name for a in paper.authors]))
        meta_fields.append(paper.title)
        meta_fields.append(paper.summary)
        for field in meta_fields:
            match = self.pattern.search(field)
            if match:
                return FilterOutcome(
                    accepted=True, level="metadata", company=match.group(0), evidence=field
                )

        # Level 2: optional email domain scan
        if email_text:
            match = self.pattern.search(email_text)
            if match:
                return FilterOutcome(
                    accepted=True, level="email", company=match.group(0), evidence=email_text
                )

        # Level 3: LLM assisted (optional)
        if llm_checker:
            try:
                if llm_checker(paper):
                    return FilterOutcome(
                        accepted=True,
                        level="llm",
                        company=None,
                        evidence="LLM vote",
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("LLM checker failed: %s", exc)

        return FilterOutcome(accepted=False)

