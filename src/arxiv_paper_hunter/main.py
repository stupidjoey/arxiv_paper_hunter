from __future__ import annotations

import argparse
import logging
from typing import List

from .analyst import Analyst
from .archivist import Archivist
from .config import AppConfig, SearchConfig
from .gatekeeper import Gatekeeper, FilterOutcome
from .harvester import ArxivHarvester
from .notifier import TelegramNotifier
from .pdf_assets import PdfAssets, extract_first_page_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ArXiv Industry Paper Tracker")
    parser.add_argument(
        "--keywords",
        nargs="+",
        help="Override keyword list (default: recommender-related).",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        help="ArXiv subject categories to include (e.g., cs.IR cs.LG cs.AI stat.ML cs.CL).",
    )
    parser.add_argument(
        "--no-category-filter",
        action="store_true",
        help="Disable category filtering (search across all categories).",
    )
    parser.add_argument(
        "--last-n-days",
        type=int,
        default=1,
        help="Look back n days (default: 1, i.e., yesterday).",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=500,
        help="Maximum number of papers to fetch (default: 500).",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip LLM summarization (still downloads PDFs).",
    )
    parser.add_argument(
        "--translate-abstracts",
        action="store_true",
        help="After download, translate each abstract EN->ZH via LLM and print.",
    )
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="Send abstract translation output to Telegram bot (requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID).",
    )
    parser.add_argument(
        "--use-llm-filter",
        action="store_true",
        help="Enable LLM vote as fallback industry detection.",
    )
    parser.add_argument(
        "--skip-gatekeeper",
        action="store_true",
        help="Bypass company filtering; accept all harvested papers.",
    )
    parser.add_argument(
        "--require-keyword-match",
        action="store_true",
        help="Drop papers whose title/abstract do not contain any keyword (post-filter).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after N accepted papers.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING...).",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )

    app_cfg = AppConfig()
    categories_raw = [] if args.no_category_filter else (args.categories or app_cfg.search.categories)
    categories_clean = [c.strip() for c in categories_raw if c and c.strip()]
    search_cfg = SearchConfig(
        keywords=args.keywords or app_cfg.search.keywords,
        categories=categories_clean,
        last_n_days=args.last_n_days,
        max_results=args.max_results,
        page_size=app_cfg.search.page_size,
    )
    app_cfg.search = search_cfg

    harvester = ArxivHarvester(search_cfg)
    gatekeeper = Gatekeeper(app_cfg.gatekeeper)
    archivist = Archivist(app_cfg.archivist)
    analyst = Analyst(app_cfg.analyst)
    notifier = None
    if args.telegram:
        if app_cfg.telegram.token and app_cfg.telegram.chat_id:
            notifier = TelegramNotifier(app_cfg.telegram)
        else:
            logging.error(
                "Telegram requested but TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID missing; skipping push."
            )

    papers = harvester.search()
    accepted = 0
    downloaded: list[tuple] = []
    llm_checker = (
        lambda paper: analyst.llm_vote_is_industry(
            paper, gatekeeper.config.company_whitelist
        )
        if args.use_llm_filter
        else None
    )

    def keyword_hit(paper) -> bool:
        text = f"{paper.title} {paper.summary}".lower()
        return any(kw.lower() in text for kw in app_cfg.search.keywords)

    for paper in papers:
        if args.require_keyword_match and not keyword_hit(paper):
            logging.debug("Skip (keyword miss): %s", paper.title)
            continue
        if args.skip_gatekeeper:
            outcome = FilterOutcome(accepted=True, level="skipped", company=None, evidence=None)
        else:
            outcome = gatekeeper.filter(paper, email_text=None, llm_checker=llm_checker)
        if not outcome.accepted:
            continue
        try:
            pdf_path = archivist.download_pdf(paper, outcome.company)
            asset_dir = pdf_path.parent / "images"
            cover = extract_first_page_image(pdf_path, asset_dir)
            assets = PdfAssets(cover_image=cover, figures=[])
            downloaded.append((paper, outcome, pdf_path, assets))
        except Exception as exc:
            logging.error("Failed to download %s: %s", paper.title, exc)
            continue

        accepted += 1
        if args.limit and accepted >= args.limit:
            break

    if args.no_summary:
        logging.info("Summary step skipped (--no-summary).")
    else:
        if not analyst.config.api_key:
            logging.warning("DEEPSEEK_API_KEY not set; skipping summaries.")
        for paper, outcome, pdf_path, assets in downloaded:
            if not analyst.config.api_key:
                continue
            try:
                summary = analyst.summarize_pdf(pdf_path)
                header = f"{paper.title} ({paper.arxiv_id})"
                archivist.write_summary_markdown(pdf_path, summary, header)
                logging.info("Summarized %s", paper.title)
            except Exception as exc:
                logging.error("Failed to summarize %s: %s", paper.title, exc)

    if args.translate_abstracts:
        if not analyst.config.api_key:
            logging.warning("DEEPSEEK_API_KEY not set; skipping abstract translation.")
        else:
            for paper, _, _, assets in downloaded:
                try:
                    zh = analyst.translate_abstract(paper)
                    authors_fmt = "; ".join(
                        [
                            f"{a.name}" + (f" ({a.affiliation})" if a.affiliation else "")
                            for a in paper.authors
                        ]
                    )
                    affiliations = [a.affiliation for a in paper.authors if a.affiliation]
                    affiliations_fmt = "; ".join(dict.fromkeys(affiliations)) if affiliations else "N/A"
                    categories_fmt = ", ".join(paper.categories) if paper.categories else "N/A"
                    msg = (
                        f"Title: {paper.title}\n"
                        f"arXiv: {paper.arxiv_id}\n"
                        f"Published: {paper.published or 'N/A'}\n"
                        f"Updated: {paper.updated or 'N/A'}\n"
                        f"Authors: {authors_fmt or 'N/A'}\n"
                        f"Affiliations: {affiliations_fmt}\n"
                        f"Keywords/Categories: {categories_fmt}\n"
                        f"Chinese translation:\n{zh}\n"
                        f"Cover Image: {assets.cover_image or 'N/A'}"
                    )
                    print("\n=== Abstract Translation ===")
                    print(msg)
                    print("===========================\n")
                    if notifier:
                        try:
                            notifier.send_message(msg)
                        if assets.cover_image:
                            notifier.send_photo(assets.cover_image)
                        except Exception as exc:
                            logging.error("Failed to push to Telegram: %s", exc)
                except Exception as exc:
                    logging.error("Failed to translate %s: %s", paper.title, exc)

    logging.info("Finished. Accepted %s papers.", accepted)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
