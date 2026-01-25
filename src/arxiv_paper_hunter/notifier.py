from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import TelegramConfig

logger = logging.getLogger(__name__)


@dataclass
class TelegramNotifier:
    config: TelegramConfig

    def send_message(self, text: str) -> None:
        if not self.config.token or not self.config.chat_id:
            raise RuntimeError("Telegram token or chat_id missing.")
        url = f"https://api.telegram.org/bot{self.config.token}/sendMessage"
        payload = {
            "chat_id": self.config.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        resp = requests.post(url, data=payload, timeout=30)
        resp.raise_for_status()

    def send_photo(self, photo_path: Path, caption: str | None = None) -> None:
        if not self.config.token or not self.config.chat_id:
            raise RuntimeError("Telegram token or chat_id missing.")
        url = f"https://api.telegram.org/bot{self.config.token}/sendPhoto"
        data = {
            "chat_id": self.config.chat_id,
        }
        if caption:
            data["caption"] = caption
        with open(photo_path, "rb") as fh:
            files = {"photo": fh}
            resp = requests.post(url, data=data, files=files, timeout=60)
            resp.raise_for_status()
