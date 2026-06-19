import logging

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class BotxClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_text(self, chat_id: str, text: str) -> None:
        # Endpoint and JWT format must be confirmed against this express.ms installation.
        logger.info("BotX send_text skipped until Stage 0 confirms API contract")
        _ = chat_id
        _ = text

    async def close(self) -> None:
        pass


def create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=15)

