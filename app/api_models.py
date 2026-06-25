from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models import SearchResult


class InternalSearchRequest(BaseModel):
    query: str


class InternalSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str
    title: Optional[str] = None
    department: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    office: Optional[str] = None
    room: Optional[str] = None
    birthday: Optional[str] = None
    manager: Optional[str] = None
    express_chat_url: Optional[str] = None

    @classmethod
    def from_search_result(cls, result: SearchResult) -> "InternalSearchResult":
        return cls.model_validate(result)


class InternalSearchResponse(BaseModel):
    results: List[InternalSearchResult]
    has_more: bool
