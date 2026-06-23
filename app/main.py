import logging
import re
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any

from fastapi import FastAPI, Request

from app.botx_client import BotxClient
from app.cache import CardCache
from app.config import get_settings
from app.db import init_db
from app.formatter import (
    NOT_FOUND_MESSAGE,
    SEARCH_HEADER,
    TOO_MANY_RESULTS_MESSAGE,
    format_search_result_card,
    format_search_results,
)
from app.ldap_client import LdapClient
from app.logging_config import configure_logging
from app.models import SearchResult

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

RESTRICTED_QUERY = "потанин"
RESTRICTED_MESSAGE = "💀 Доступ к данной информации ограничен"


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
    user_display_name = _extract_user_display_name(body)
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

    if RESTRICTED_QUERY in _command_tokens(normalized_command):
        sent = await _send_botx_message(chat_id, cts_host, RESTRICTED_MESSAGE)
        admin_sent = await _notify_admins_about_restricted_query(
            chat_id,
            cts_host,
            user_display_name,
            user_huid,
            command,
        )
        return {"status": "ok", "message": RESTRICTED_MESSAGE, "sent": sent, "admin_sent": admin_sent}

    results = await _enrich_results_with_express_links(ldap_client.search_people(command), cts_host)
    message = format_search_results(results, settings.search_limit)
    sent = await _send_search_results(chat_id, cts_host, results)
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


def _command_tokens(command: str) -> set[str]:
    return set(re.findall(r"\w+", command, flags=re.UNICODE))


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


def _extract_user_display_name(body: dict[str, Any]) -> str:
    sender = body.get("from") if isinstance(body.get("from"), dict) else {}
    nested_sources = [
        sender,
        body.get("sender") if isinstance(body.get("sender"), dict) else {},
        body.get("user") if isinstance(body.get("user"), dict) else {},
        sender.get("user") if isinstance(sender.get("user"), dict) else {},
        sender.get("profile") if isinstance(sender.get("profile"), dict) else {},
    ]

    for source in nested_sources:
        display_name = _first_string(
            source,
            [
                "display_name",
                "displayName",
                "full_name",
                "fullName",
                "name",
                "user_name",
                "userName",
                "username",
                "login",
            ],
        )
        if display_name:
            return display_name

        full_name = " ".join(
            part
            for part in [
                _first_string(source, ["last_name", "lastName", "surname"]),
                _first_string(source, ["first_name", "firstName", "given_name", "givenName"]),
                _first_string(source, ["middle_name", "middleName", "patronymic"]),
            ]
            if part
        )
        if full_name:
            return full_name

    return ""


def _first_string(source: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
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


async def _send_search_results(chat_id: str, cts_host: str, results: list[SearchResult]) -> bool:
    if not chat_id:
        logger.info("BotX send skipped: group_chat_id is empty")
        return False
    if not results:
        return await _send_botx_message(chat_id, cts_host, NOT_FOUND_MESSAGE)

    client = BotxClient(settings, cts_host)
    sent_results = [await client.send_text(chat_id, SEARCH_HEADER)]
    for index, result in enumerate(results[: settings.search_limit], start=1):
        sent_results.append(await _send_search_result_card(client, chat_id, result, index))

    if len(results) > settings.search_limit:
        sent_results.append(await client.send_text(chat_id, TOO_MANY_RESULTS_MESSAGE))

    return all(sent_results)


async def _send_search_result_card(client: BotxClient, chat_id: str, result: SearchResult, index: int) -> bool:
    caption = format_search_result_card(result, index=index)
    if result.photo:
        return await client.send_file(
            chat_id,
            result.photo,
            file_name=f"{_photo_file_stem(result, index)}.{_photo_extension(result.photo)}",
            mime_type=_photo_mime_type(result.photo),
            caption=caption,
        )
    return await client.send_text(chat_id, caption)


def _photo_file_stem(result: SearchResult, index: int) -> str:
    normalized_name = re.sub(r"[^0-9A-Za-zА-Яа-яЁё_-]+", "-", result.display_name).strip("-")
    return normalized_name or f"employee-{index}"


def _photo_mime_type(photo: bytes) -> str:
    if photo.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if photo.startswith(b"GIF87a") or photo.startswith(b"GIF89a"):
        return "image/gif"
    return "image/jpeg"


def _photo_extension(photo: bytes) -> str:
    mime_type = _photo_mime_type(photo)
    if mime_type == "image/png":
        return "png"
    if mime_type == "image/gif":
        return "gif"
    return "jpg"


async def _notify_admins_about_restricted_query(
    chat_id: str,
    cts_host: str,
    user_display_name: str,
    user_huid: str,
    query: str,
) -> bool:
    if not settings.admin_huids and not settings.admin_alert_chat_ids:
        logger.warning(
            "Restricted query admin notification skipped: BOT_ADMIN_HUIDS and BOT_ADMIN_ALERT_CHAT_IDS are empty"
        )
        return False

    user_label = user_display_name or "<имя не передано eXpress>"
    huid_label = user_huid or "<unknown>"
    message = (
        "💀 Запрос ограниченной информации\n"
        f"Пользователь: {user_label}\n"
        f"HUID: {huid_label}\n"
        f"Чат: {chat_id}\n"
        f"Запрос: {query}"
    )

    if settings.admin_alert_chat_ids:
        client = BotxClient(settings, cts_host)
        sent_results = []
        for admin_chat_id in settings.admin_alert_chat_ids:
            sent_results.append(await client.send_text(admin_chat_id, message))
        return all(sent_results)

    logger.info("Restricted query admin notification uses recipients fallback")
    return await BotxClient(settings, cts_host).send_text(
        "",
        message,
        recipients=sorted(settings.admin_huids),
    )


async def _enrich_results_with_express_links(results: list[SearchResult], cts_host: str) -> list[SearchResult]:
    if not results:
        return results

    client = BotxClient(settings, cts_host)
    enriched_results = []
    for result in results:
        express_link = await _find_express_profile_link(client, result.email, cts_host)
        if express_link:
            enriched_results.append(replace(result, express_chat_url=express_link))
        else:
            enriched_results.append(result)
    return enriched_results


async def _find_express_profile_link(client: BotxClient, email: str | None, cts_host: str) -> str | None:
    if not email:
        return None
    payload = await client.get_user_by_email(email)
    if not payload:
        return None
    return _extract_express_profile_link(payload, cts_host)


def _extract_express_profile_link(payload: dict[str, Any], cts_host: str = "") -> str | None:
    user = _extract_user_payload(payload)
    link = _first_string(
        user,
        [
            "profile_url",
            "profileUrl",
            "profile_link",
            "profileLink",
            "deep_link",
            "deepLink",
            "chat_link",
            "chatLink",
            "link",
            "url",
        ],
    )
    if link:
        return link

    user_huid = _first_string(user, ["user_huid", "userHuid", "huid", "id"])
    if user_huid:
        return _build_express_profile_url(user_huid, cts_host)
    return None


def _build_express_profile_url(user_huid: str, _cts_host: str) -> str:
    if settings.botx_profile_url_template:
        return settings.botx_profile_url_template.format(user_huid=user_huid)
    return f"https://xlnk.ms/open/profile/{user_huid}"


def _extract_user_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ["result", "data", "user"]:
        value = payload.get(key)
        if isinstance(value, list):
            first_item = next((item for item in value if isinstance(item, dict)), None)
            if isinstance(first_item, dict):
                return first_item
        if isinstance(value, dict):
            nested_user = value.get("user")
            if isinstance(nested_user, dict):
                return nested_user
            return value
    return payload
