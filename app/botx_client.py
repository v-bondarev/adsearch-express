import logging
import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

JWT_TOKEN_VERSION = 2


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _normalize_host(host: str) -> str:
    normalized = host.strip().rstrip("/")
    if normalized and not normalized.startswith(("http://", "https://")):
        normalized = f"https://{normalized}"
    return normalized


def _audience(host: str) -> str:
    return host.replace("https://", "").replace("http://", "").split("/")[0]


def _make_token(settings: Settings, cts_host: str) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": settings.bot_id,
        "aud": _audience(cts_host),
        "exp": now + 60,
        "nbf": now,
        "iat": now,
        "jti": uuid.uuid4().hex,
        "version": JWT_TOKEN_VERSION,
    }
    signing_input = ".".join(
        [
            _base64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _base64url(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        settings.bot_secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_base64url(signature)}"


class BotxClient:
    def __init__(self, settings: Settings, cts_host: str) -> None:
        self.settings = settings
        self.host = _normalize_host(cts_host or settings.botx_base_url)
        self.endpoint = f"{self.host}/api/v4/botx/notifications/direct/sync"

    async def send_text(self, chat_id: str, text: str, recipients: list[str] | None = None) -> bool:
        payload: dict[str, Any] = {
            "group_chat_id": chat_id,
            "recipients": recipients,
            "notification": {
                "status": "ok",
                "body": text,
            },
        }
        return await self._post(payload)

    async def send_error(self, chat_id: str, text: str, recipients: list[str] | None = None) -> bool:
        payload: dict[str, Any] = {
            "group_chat_id": chat_id,
            "recipients": recipients,
            "notification": {
                "status": "error",
                "body": text,
            },
        }
        return await self._post(payload)

    async def _post(self, payload: dict[str, Any]) -> bool:
        if not self.host:
            logger.error("BotX send skipped: host is not configured")
            return False
        if not self.settings.bot_id or not self.settings.bot_secret_key:
            logger.error("BotX send skipped: bot credentials are not configured")
            return False

        headers = {
            "Authorization": f"Bearer {_make_token(self.settings, self.host)}",
            "Content-Type": "application/json",
        }
        async with create_http_client() as client:
            try:
                response = await client.post(self.endpoint, json=payload, headers=headers)
            except httpx.RequestError as exc:
                logger.error("BotX network error: %s", exc)
                return False

        if response.status_code in {200, 202}:
            return True
        logger.error("BotX send failed: status=%s body=%s", response.status_code, response.text[:300])
        return False

    async def close(self) -> None:
        pass


def create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=15)
