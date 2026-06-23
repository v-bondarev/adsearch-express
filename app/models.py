from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    object_id: str
    display_name: str
    title: str | None = None
    department: str | None = None
    company: str | None = None
    object_type: str | None = None


@dataclass(frozen=True)
class EmployeeCard:
    object_id: str
    display_name: str
    title: str | None = None
    department: str | None = None
    company: str | None = None
    phone: str | None = None
    mobile: str | None = None
    email: str | None = None
    office: str | None = None
    room: str | None = None
    manager: str | None = None
    photo: bytes | None = None
    object_type: str | None = None
    from_cache: bool = False
