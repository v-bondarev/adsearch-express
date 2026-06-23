import logging
import ssl
from contextlib import contextmanager
from typing import Iterator

from ldap3 import ALL, ALL_ATTRIBUTES, SUBTREE, Connection, Server, Tls
from ldap3.utils.conv import escape_filter_chars

from app.config import Settings
from app.models import EmployeeCard, SearchResult

logger = logging.getLogger(__name__)

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

    @contextmanager
    def _connection(self) -> Iterator[Connection]:
        tls = None
        if self.settings.ldap_ca_cert_file:
            tls = Tls(
                ca_certs_file=self.settings.ldap_ca_cert_file,
                validate=ssl.CERT_REQUIRED,
                version=ssl.PROTOCOL_TLS_CLIENT,
            )

        server = Server(
            self.settings.ldap_host,
            port=self.settings.ldap_port,
            use_ssl=self.settings.ldap_use_ssl,
            get_info=ALL,
            tls=tls,
            connect_timeout=self.settings.ldap_connect_timeout_seconds,
        )
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

    def healthcheck(self) -> bool:
        if not self.settings.ldap_host:
            logger.info("LDAP healthcheck skipped: LDAP_HOST is not configured")
            return False

        with self._connection():
            return True

    def search_people(self, query: str) -> list[SearchResult]:
        logger.info("LDAP search requested")
        normalized_query = query.strip()
        if not normalized_query:
            return []

        seen_dns: set[str] = set()
        results: list[SearchResult] = []
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

    def get_card(self, object_id: str) -> EmployeeCard | None:
        # Final attribute mapping must be confirmed during Stage 0.
        logger.info("LDAP card lookup requested")
        _ = object_id
        return None

    def dump_test_object_attributes(self, ldap_filter: str) -> list[dict[str, object]]:
        with self._connection() as connection:
            connection.search(
                search_base=self.settings.ldap_base_dn,
                search_filter=ldap_filter,
                attributes=ALL_ATTRIBUTES,
            )
            return [entry.entry_attributes_as_dict for entry in connection.entries]

    def _search_bases(self) -> list[str]:
        return self.settings.included_ous or [self.settings.ldap_base_dn]

    def _is_excluded_dn(self, dn: str) -> bool:
        normalized_dn = dn.lower()
        return any(excluded.lower() in normalized_dn for excluded in self.settings.excluded_ous)


def _build_people_filter(query: str) -> str:
    escaped = escape_filter_chars(query)
    contains = f"*{escaped}*"
    starts_with = f"{escaped}*"
    enabled_user_filter = "(!(userAccountControl:1.2.840.113556.1.4.803:=2))"

    user_match = (
        "(&"
        "(objectClass=user)"
        "(objectCategory=person)"
        f"{enabled_user_filter}"
        "(|"
        f"(displayName={contains})"
        f"(cn={contains})"
        f"(name={contains})"
        f"(description={contains})"
        f"(mail={contains})"
        f"(sAMAccountName={contains})"
        f"(extensionAttribute1={starts_with})"
        f"(extensionAttribute2={starts_with})"
        f"(extensionAttribute3={starts_with})"
        f"(sn={starts_with})"
        ")"
        ")"
    )
    contact_match = (
        "(&"
        "(objectClass=contact)"
        "(|"
        f"(displayName={contains})"
        f"(cn={contains})"
        f"(name={contains})"
        f"(description={contains})"
        f"(mail={contains})"
        f"(sn={starts_with})"
        ")"
        ")"
    )
    return f"(|{user_match}{contact_match})"


def _entry_to_search_result(attributes: dict[str, object], dn: str) -> SearchResult:
    object_classes = [item.lower() for item in _get_values(attributes, "objectClass")]
    object_type = "contact" if "contact" in object_classes else "user"
    department = _first_value(attributes, "department") or _first_value(attributes, "company")
    return SearchResult(
        object_id=dn,
        display_name=_first_value(attributes, "displayName")
        or _first_value(attributes, "cn")
        or _first_value(attributes, "name")
        or dn,
        title=_first_value(attributes, "title"),
        department=department,
        object_type=object_type,
    )


def _first_value(attributes: dict[str, object], name: str) -> str | None:
    values = _get_values(attributes, name)
    if not values:
        return None
    return str(values[0])


def _get_values(attributes: dict[str, object], name: str) -> list[object]:
    value = attributes.get(name)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _search_result_sort_key(result: SearchResult) -> tuple[int, str]:
    return (0 if result.object_type == "user" else 1, result.display_name.lower())
