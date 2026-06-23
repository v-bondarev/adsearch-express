import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request

from app.botx_client import BotxClient
from app.cache import CardCache
from app.config import get_settings
from app.db import init_db
from app.formatter import format_search_messages, format_search_results
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
    return await _handle_command(request)


@app.post("/command")
async def command(request: Request) -> dict[str, Any]:
    return await _handle_command(request)


async def _handle_command(request: Request) -> dict[str, Any]:
    body = await request.json()
    logger.info("BotX command received")

    command = _extract_text(body)
    normalized_command = command.casefold()
    user_huid = _extract_user_huid(body)
    chat_id = _extract_group_chat_id(body)
    cts_host = _extract_cts_host(body)

    if normalized_command == "/clear_cache":
        if user_huid not in settings.admin_huids:
            logger.warning("cache clear denied")
            message = "Команда доступна только администраторам бота."
            sent = await _send_botx_message(chat_id, cts_host, message)
            return {"status": "ok", "message": message, "sent": sent}
        deleted = card_cache.clear()
        logger.info("cache cleared")
        message = f"Кеш очищен. Удалено записей: {deleted}."
        sent = await _send_botx_message(chat_id, cts_host, message)
        return {"status": "ok", "message": message, "sent": sent}

    if normalized_command in {"", "/start", "start", "старт", "/help", "help", "помощь"}:
        message = "Для поиска введите ФИО или просто фамилию"
        sent = await _send_botx_message(chat_id, cts_host, message)
        return {"status": "ok", "message": message, "sent": sent}

    results = ldap_client.search_people(command)
    message = format_search_results(results, settings.search_limit)
    sent = await _send_botx_messages(
        chat_id,
        cts_host,
        format_search_messages(results, settings.search_limit),
    )
    return {"status": "ok", "message": message, "sent": sent}


def _extract_text(body: dict[str, Any]) -> str:
    command = body.get("command") if isinstance(body.get("command"), dict) else {}
    candidates = [
        command.get("body"),
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
    sender = body.get("from") if isinstance(body.get("from"), dict) else {}
    candidates = [
        sender.get("user_huid"),
        body.get("user_huid"),
        body.get("sender", {}).get("user_huid") if isinstance(body.get("sender"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            return candidate.strip()
    return ""


def _extract_group_chat_id(body: dict[str, Any]) -> str:
    sender = body.get("from") if isinstance(body.get("from"), dict) else {}
    candidates = [
        sender.get("group_chat_id"),
        body.get("group_chat_id"),
        body.get("chat", {}).get("id") if isinstance(body.get("chat"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            return candidate.strip()
    return ""


def _extract_cts_host(body: dict[str, Any]) -> str:
    sender = body.get("from") if isinstance(body.get("from"), dict) else {}
    candidates = [
        sender.get("host"),
        body.get("host"),
        settings.botx_base_url,
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            return candidate.strip()
    return ""


async def _send_botx_message(chat_id: str, cts_host: str, message: str) -> bool:
    if not chat_id:
        logger.info("BotX send skipped: group_chat_id is empty")
        return False
    return await BotxClient(settings, cts_host).send_text(chat_id, message)


async def _send_botx_messages(chat_id: str, cts_host: str, messages: list[str]) -> bool:
    if not chat_id:
        logger.info("BotX send skipped: group_chat_id is empty")
        return False

    client = BotxClient(settings, cts_host)
    sent_results = []
    for message in messages:
        sent_results.append(await client.send_text(chat_id, message))
    return all(sent_results)
