from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict

from fastapi import FastAPI, Header, HTTPException, status

from app.api_models import (
    InternalSearchRequest,
    InternalSearchResponse,
    InternalSearchResult,
)
from app.botx_client import close_http_client
from app.config import get_settings
from app.ldap_client import LdapClient
from app.logging_config import configure_logging
from app.main import RESTRICTED_QUERY, _command_tokens, _enrich_results_with_express_links

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
ldap_client = LdapClient(settings)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.is_production and not settings.internal_api_token:
        raise RuntimeError("INTERNAL_API_TOKEN is required in production")
    logger.info("internal API started")
    yield
    ldap_client.close_pool()
    await close_http_client()
    logger.info("internal API stopped")


app = FastAPI(title="adsearch-express-internal-api", lifespan=lifespan)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search", response_model=InternalSearchResponse)
async def search(
    payload: InternalSearchRequest,
    authorization: str | None = Header(default=None),
) -> InternalSearchResponse:
    _authorize(authorization)
    query = payload.query.strip()
    if not 2 <= len(query) <= 150:
        raise HTTPException(status_code=422, detail="Invalid query")
    if RESTRICTED_QUERY in _command_tokens(query.casefold()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this query is restricted",
        )

    try:
        results = await asyncio.to_thread(ldap_client.search_people, query)
    except Exception:
        logger.exception("Internal directory search failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Directory search is temporarily unavailable",
        ) from None

    limited_results = results[: settings.search_limit]
    try:
        enriched_results = await _enrich_results_with_express_links(
            limited_results,
            settings.botx_base_url,
        )
    except Exception:
        logger.exception("Internal API profile enrichment failed")
        enriched_results = limited_results
    return InternalSearchResponse(
        results=[
            InternalSearchResult.from_search_result(result)
            for result in enriched_results
        ],
        has_more=len(results) > settings.search_limit,
    )


def _authorize(authorization: str | None) -> None:
    expected_token = settings.internal_api_token
    if not expected_token or not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    scheme, separator, supplied_token = authorization.partition(" ")
    if (
        not separator
        or scheme.casefold() != "bearer"
        or not secrets.compare_digest(supplied_token, expected_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
