from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List
import logging
import textwrap
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from .config import SearchConfig

logger = logging.getLogger(__name__)


@dataclass
class Author:
    name: str
    affiliation: str | None = None


@dataclass
class Paper:
    arxiv_id: str
    title: str
    summary: str
    published: str
    updated: str
    authors: List[Author]
    pdf_url: str | None
    categories: list[str]

    @property
    def first_author(self) -> str:
        return self.authors[0].name if self.authors else "unknown"


class ArxivHarvester:
    API_URL = "http://export.arxiv.org/api/query"
    NS = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    }

    def __init__(self, config: SearchConfig | None = None):
        self.config = config or SearchConfig()

    def _build_query(
        self,
        keywords: Iterable[str],
        start: date,
        end: date,
        categories: Iterable[str] | None,
    ) -> str:
        keyword_clause = " OR ".join([f'all:\"{kw}\"' for kw in keywords])
        date_clause = f"submittedDate:[{start.strftime('%Y%m%d')}0000 TO {end.strftime('%Y%m%d')}2359]"
        cat_clause = ""
        cats = [c.strip() for c in (categories or []) if c and c.strip()]
        if cats:
            cat_clause = " AND (" + " OR ".join([f"cat:{c}" for c in cats]) + ")"
        return f"({keyword_clause}) AND {date_clause}{cat_clause}"

    def search(self) -> list[Paper]:
        cfg = self.config
        start_date = cfg.since
        end_date = cfg.until
        query = self._build_query(cfg.keywords, start_date, end_date, cfg.categories)
        logger.info(
            "Searching arXiv with keywords=%s, categories=%s, date_range=%s to %s",
            cfg.keywords,
            cfg.categories,
            start_date,
            end_date,
        )

        papers: list[Paper] = []
        start = 0
        while start < cfg.max_results:
            chunk = self._fetch_chunk(query=query, start=start, max_results=cfg.page_size)
            if not chunk:
                break
            papers.extend(chunk)
            if len(chunk) < cfg.page_size:
                break
            start += cfg.page_size
        logger.info("Fetched %s papers", len(papers))
        return papers

    def _fetch_chunk(self, query: str, start: int, max_results: int) -> list[Paper]:
        params = {
            "search_query": query,
            "start": start,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        headers = {"User-Agent": "arxiv-paper-hunter/0.1"}
        response = requests.get(self.API_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return self._parse_feed(response.text)

    def _parse_feed(self, xml_text: str) -> list[Paper]:
        root = ET.fromstring(xml_text)
        papers: list[Paper] = []
        for entry in root.findall("atom:entry", self.NS):
            arxiv_id = entry.findtext("atom:id", default="", namespaces=self.NS)
            title = self._clean(entry.findtext("atom:title", default="", namespaces=self.NS))
            summary = self._clean(entry.findtext("atom:summary", default="", namespaces=self.NS))
            published = entry.findtext("atom:published", default="", namespaces=self.NS)
            updated = entry.findtext("atom:updated", default="", namespaces=self.NS)
            authors = [
                Author(
                    name=self._clean(author.findtext("atom:name", default="", namespaces=self.NS)),
                    affiliation=self._clean(
                        author.findtext("arxiv:affiliation", default="", namespaces=self.NS)
                    )
                    or None,
                )
                for author in entry.findall("atom:author", self.NS)
            ]
            pdf_url = None
            for link in entry.findall("atom:link", self.NS):
                if link.attrib.get("type") == "application/pdf":
                    pdf_url = link.attrib.get("href")
                    break
            categories = [
                link.attrib.get("term", "")
                for link in entry.findall("atom:category", self.NS)
                if link.attrib.get("term")
            ]
            papers.append(
                Paper(
                    arxiv_id=arxiv_id,
                    title=title,
                    summary=summary,
                    published=published,
                    updated=updated,
                    authors=authors,
                    pdf_url=pdf_url,
                    categories=categories,
                )
            )
        return papers

    @staticmethod
    def _clean(text: str | None) -> str:
        if not text:
            return ""
        return " ".join(textwrap.dedent(text).split())
