import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request

from app.cache import CardCache
from app.config import get_settings
from app.db import init_db
from app.formatter import format_search_results
from app.ldap_client import LdapClient
from app.logging_config import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(settings.cache_db_path)
    logger.info("application started")
    yield
    logger.info("application stopped")


app = FastAPI(title="adsearch-express", lifespan=lifespan)
ldap_client = LdapClient(settings)
card_cache = CardCache(settings.cache_db_path, settings.cache_ttl_seconds)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    body = await request.json()
    logger.info("webhook received")

    # The exact express.ms webhook shape must be confirmed during Stage 0.
    command = _extract_text(body)
    user_huid = _extract_user_huid(body)

    if command == "/clear_cache":
        if user_huid not in settings.admin_huids:
            logger.warning("cache clear denied")
            return {"ok": True, "message": "Команда доступна только администраторам бота."}
        deleted = card_cache.clear()
        logger.info("cache cleared")
        return {"ok": True, "message": f"Кеш очищен. Удалено записей: {deleted}."}

    if command in {"/start", "/help", ""}:
        return {"ok": True, "message": "Напишите ФИО или часть ФИО сотрудника для поиска."}

    results = ldap_client.search_people(command)
    return {"ok": True, "message": format_search_results(results, settings.search_limit)}


def _extract_text(body: dict[str, Any]) -> str:
    candidates = [
        body.get("text"),
        body.get("body"),
        body.get("message", {}).get("text") if isinstance(body.get("message"), dict) else None,
        body.get("data", {}).get("text") if isinstance(body.get("data"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            return candidate.strip()
    return ""


def _extract_user_huid(body: dict[str, Any]) -> str:
    candidates = [
        body.get("user_huid"),
        body.get("sender", {}).get("user_huid") if isinstance(body.get("sender"), dict) else None,
        body.get("from", {}).get("user_huid") if isinstance(body.get("from"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            return candidate.strip()
    return ""

