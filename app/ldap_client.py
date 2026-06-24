from __future__ import annotations

import logging
import re
import ssl
from contextlib import contextmanager
from datetime import date
from typing import Dict, Iterator, List, Optional, Tuple

from ldap3 import ALL, ALL_ATTRIBUTES, BASE, SUBTREE, Connection, Server, Tls
from ldap3.utils.conv import escape_filter_chars

from app.config import Settings
from app.models import EmployeeCard, SearchResult

logger = logging.getLogger(__name__)

PARENTHESIZED_SUFFIX_RE = re.compile(r"\s*\(([^()]*)\)\s*$")

SEARCH_ATTRIBUTES = [
    "distinguishedName",
    "objectClass",
    "cn",
    "name",
    "displayName",
    "description",
    "sn",
    "givenName",
    "extensionAttribute1",
    "extensionAttribute2",
    "extensionAttribute3",
    "extensionAttribute4",
    "title",
    "department",
    "company",
    "mail",
    "telephoneNumber",
    "mobile",
    "physicalDeliveryOfficeName",
    "manager",
    "userAccountControl",
    "thumbnailPhoto",
]

class LdapClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._server: Optional[Server] = None

    def _get_server(self) -> Server:
        """Get or create the reusable LDAP server configuration."""
        if self._server is not None:
            return self._server

        tls = None
        if self.settings.ldap_ca_cert_file:
            tls = Tls(
                ca_certs_file=self.settings.ldap_ca_cert_file,
                validate=ssl.CERT_REQUIRED,
                version=ssl.PROTOCOL_TLS_CLIENT,
            )

        self._server = Server(
            self.settings.ldap_host,
            port=self.settings.ldap_port,
            use_ssl=self.settings.ldap_use_ssl,
            get_info=ALL,
            tls=tls,
            connect_timeout=self.settings.ldap_connect_timeout_seconds,
        )
        return self._server

    @contextmanager
    def _connection(self) -> Iterator[Connection]:
        """Create a bound connection and always unbind it after use."""
        server = self._get_server()
        connection = Connection(
            server,
            user=self.settings.ldap_bind_user,
            password=self.settings.ldap_password,
            auto_bind=True,
            receive_timeout=self.settings.ldap_read_timeout_seconds,
        )
        try:
            yield connection
        finally:
            connection.unbind()

    def close_pool(self) -> None:
        """Release the cached server configuration on shutdown."""
        if self._server is not None:
            self._server = None
            logger.info("LDAP server configuration released")

    def healthcheck(self) -> bool:
        if not self.settings.ldap_host:
            logger.info("LDAP healthcheck skipped: LDAP_HOST is not configured")
            return False

        with self._connection():
            return True

    def search_people(self, query: str) -> List[SearchResult]:
        logger.info("LDAP search requested")
        normalized_query = query.strip()
        if not normalized_query:
            return []

        seen_dns: set = set()
        results: List[SearchResult] = []
        ldap_filter = _build_people_filter(normalized_query)

        with self._connection() as connection:
            for search_base in self._search_bases():
                connection.search(
                    search_base=search_base,
                    search_filter=ldap_filter,
                    search_scope=SUBTREE,
                    attributes=SEARCH_ATTRIBUTES,
                    size_limit=self.settings.search_limit + 1,
                )
                for entry in connection.entries:
                    dn = str(entry.entry_dn)
                    if dn in seen_dns or self._is_excluded_dn(dn):
                        continue
                    seen_dns.add(dn)
                    results.append(_entry_to_search_result(entry.entry_attributes_as_dict, dn))

        return sorted(results, key=_search_result_sort_key)

    def get_card(self, object_id: str) -> Optional[EmployeeCard]:
        logger.info("LDAP card lookup requested")
        with self._connection() as connection:
            connection.search(
                search_base=object_id,
                search_filter="(objectClass=*)",
                search_scope=BASE,
                attributes=SEARCH_ATTRIBUTES,
            )
            if not connection.entries:
                return None
            return _entry_to_employee_card(connection.entries[0].entry_attributes_as_dict, object_id)

    def dump_test_object_attributes(self, ldap_filter: str) -> List[Dict[str, object]]:
        with self._connection() as connection:
            connection.search(
                search_base=self.settings.ldap_base_dn,
                search_filter=ldap_filter,
                attributes=ALL_ATTRIBUTES,
            )
            return [entry.entry_attributes_as_dict for entry in connection.entries]

    def _search_bases(self) -> List[str]:
        return self.settings.included_ous or [self.settings.ldap_base_dn]

    def _is_excluded_dn(self, dn: str) -> bool:
        normalized_dn = dn.lower()
        return any(excluded.lower() in normalized_dn for excluded in self.settings.excluded_ous)


def _build_people_filter(query: str) -> str:
    name_filter = _build_name_filter(query)
    enabled_user_filter = "(!(userAccountControl:1.2.840.113556.1.4.803:=2))"
    required_card_fields_filter = "(company=*)(mail=*)"

    user_match = (
        "(&"
        "(objectClass=user)"
        "(objectCategory=person)"
        f"{enabled_user_filter}"
        f"{required_card_fields_filter}"
        f"{name_filter}"
        ")"
    )
    contact_match = (
        "(&"
        "(objectClass=contact)"
        f"{required_card_fields_filter}"
        f"{name_filter}"
        ")"
    )
    return f"(|{user_match}{contact_match})"


def _build_name_filter(query: str) -> str:
    token_filters = [_build_name_token_filter(token) for token in query.split() if token]
    if not token_filters:
        return "(cn=__empty_query__)"
    if len(token_filters) == 1:
        return token_filters[0]
    return f"(&{''.join(token_filters)})"


def _build_name_token_filter(token: str) -> str:
    escaped = escape_filter_chars(token)
    contains = f"*{escaped}*"
    starts_with = f"{escaped}*"
    return (
        "(|"
        f"(displayName={contains})"
        f"(cn={contains})"
        f"(name={contains})"
        f"(givenName={starts_with})"
        f"(extensionAttribute1={starts_with})"
        f"(extensionAttribute2={starts_with})"
        f"(extensionAttribute3={starts_with})"
        f"(sn={starts_with})"
        ")"
    )


def _entry_to_search_result(attributes: Dict[str, object], dn: str) -> SearchResult:
    card = _entry_to_employee_card(attributes, dn)
    return SearchResult(
        object_id=dn,
        display_name=card.display_name,
        title=card.title,
        department=card.department,
        company=card.company,
        phone=card.phone,
        email=card.email,
        office=card.office,
        room=card.room,
        birthday=card.birthday,
        manager=card.manager,
        photo=card.photo,
        object_type=card.object_type,
    )


def _entry_to_employee_card(attributes: Dict[str, object], dn: str) -> EmployeeCard:
    object_classes = [item.lower() for item in _get_values(attributes, "objectClass")]
    object_type = "contact" if "contact" in object_classes else "user"
    display_name, company = _split_name_and_company(_first_value(attributes, "cn") or _first_value(attributes, "name") or dn)
    existing_company = _first_value(attributes, "company")
    company = existing_company or company
    office, room = _split_office_room(_first_value(attributes, "physicalDeliveryOfficeName"))

    return EmployeeCard(
        object_id=dn,
        display_name=display_name,
        title=_first_value(attributes, "title"),
        department=_first_value(attributes, "department"),
        company=company,
        phone=_first_value(attributes, "telephoneNumber"),
        mobile=_first_value(attributes, "mobile"),
        email=_first_value(attributes, "mail"),
        office=office,
        room=room,
        birthday=_format_birthday(_first_value(attributes, "extensionAttribute4")),
        manager=_manager_display_name(_first_value(attributes, "manager")),
        photo=_first_bytes(attributes, "thumbnailPhoto"),
        object_type=object_type,
    )


def _split_name_and_company(cn: str) -> Tuple[str, Optional[str]]:
    match = PARENTHESIZED_SUFFIX_RE.search(cn)
    if not match:
        return cn.strip(), None
    name = cn[: match.start()].strip()
    company = match.group(1).strip() or None
    return name, company


def _manager_display_name(manager_dn: Optional[str]) -> Optional[str]:
    if not manager_dn:
        return None
    if not manager_dn.lower().startswith("cn="):
        return manager_dn
    cn_part = manager_dn[3:].split(",OU=", 1)[0].split(",CN=", 1)[0].split(",DC=", 1)[0]
    return cn_part.replace(r"\,", ",").strip() or None


def _split_office_room(value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not value:
        return None, None
    if "\\" not in value:
        return _normalize_office(value), None
    office, room = value.split("\\", 1)
    return _normalize_office(office), room.strip() or None


def _normalize_office(value: str) -> Optional[str]:
    normalized = value.strip().replace("-", "")
    return normalized or None


def _format_birthday(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    normalized = value.strip()
    day = month = None

    year_first = re.match(r"^\d{4}[-./]?(\d{2})[-./]?(\d{2})", normalized)
    if year_first:
        month, day = year_first.groups()
    else:
        day_first = re.match(r"^(\d{1,2})[./-](\d{1,2})(?:[./-]\d{2,4})?", normalized)
        if day_first:
            day, month = day_first.groups()

    if day is None or month is None:
        return None

    day_number = int(day)
    month_number = int(month)
    month_names = [
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    ]
    try:
        date(2000, month_number, day_number)
    except ValueError:
        return None
    return f"{day_number} {month_names[month_number - 1]}"


def _first_bytes(attributes: Dict[str, object], name: str) -> Optional[bytes]:
    values = _get_values(attributes, name)
    for value in values:
        if isinstance(value, bytes):
            return value
    return None


def _first_value(attributes: Dict[str, object], name: str) -> Optional[str]:
    values = _get_values(attributes, name)
    if not values:
        return None
    return str(values[0])


def _get_values(attributes: Dict[str, object], name: str) -> List[object]:
    value = attributes.get(name)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _search_result_sort_key(result: SearchResult) -> Tuple[int, str]:
    return (0 if result.object_type == "user" else 1, result.display_name.lower())
