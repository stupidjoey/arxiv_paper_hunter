from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - optional dependency
    fitz = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency
    PdfReader = None
try:
    from PIL import Image  # noqa: F401
    _PIL_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    _PIL_AVAILABLE = False


@dataclass
class PdfAssets:
    cover_image: Path | None
    figures: list[Path]


def extract_first_page_image(pdf_path: Path, output_dir: Path) -> Path | None:
    if fitz is None:
        logger.warning("PyMuPDF not available; skipping cover image extraction.")
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        doc = fitz.open(str(pdf_path))
        if doc.page_count < 1:
            return None
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=200)
        cover_path = output_dir / f"{pdf_path.stem}_page1.png"
        pix.save(cover_path)
        return cover_path
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to render cover image for %s: %s", pdf_path, exc)
        return None


def extract_figures(pdf_path: Path, output_dir: Path, limit: int = 3) -> list[Path]:
    if PdfReader is None:
        logger.warning("pypdf not available; skipping figure extraction.")
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    figures: list[Path] = []
    try:
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            images = getattr(page, "images", None)
            if not images:
                continue
            for image in images:
                if len(figures) >= limit:
                    return figures
                ext = getattr(image, "extension", "bin")
                name = getattr(image, "name", "image")
                safe_name = name.replace("/", "_")
                fig_path = output_dir / f"{pdf_path.stem}_{safe_name}.{ext}"
                try:
                    with open(fig_path, "wb") as fh:
                        fh.write(image.data)
                    figures.append(fig_path)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Failed to save figure %s: %s", fig_path, exc)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to extract figures for %s: %s", pdf_path, exc)
    return figures
