from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SearchResult:
    object_id: str
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
    photo: Optional[bytes] = None
    object_type: Optional[str] = None


@dataclass(frozen=True)
class EmployeeCard:
    object_id: str
    display_name: str
    title: Optional[str] = None
    department: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    office: Optional[str] = None
    room: Optional[str] = None
    birthday: Optional[str] = None
    manager: Optional[str] = None
    express_chat_url: Optional[str] = None
    photo: Optional[bytes] = None
    object_type: Optional[str] = None
    from_cache: bool = False
