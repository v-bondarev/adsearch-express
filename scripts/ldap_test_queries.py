#!/usr/bin/env python3
import argparse
import json
import ssl
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ldap3 import ALL, ALL_ATTRIBUTES, BASE, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException, LDAPSASLPrepError
from ldap3.utils.conv import escape_filter_chars

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import Settings

DEFAULT_ATTRIBUTES = [
    "distinguishedName",
    "objectClass",
    "objectGUID",
    "cn",
    "displayName",
    "sn",
    "givenName",
    "middleName",
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
    "jpegPhoto",
]

BINARY_ATTRIBUTES = {"objectGUID", "thumbnailPhoto", "jpegPhoto"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LDAP test queries using application .env settings.")
    parser.add_argument("--query", help="Employee/contact name or surname fragment to search.")
    parser.add_argument("--filter", help="Custom LDAP filter. Overrides --query.")
    parser.add_argument("--limit", type=int, default=5, help="Maximum entries to print per search base.")
    parser.add_argument("--all-attributes", action="store_true", help="Request all regular and operational attributes.")
    args = parser.parse_args()

    settings = Settings()
    _print_settings_summary(settings)
    _validate_settings(settings)

    try:
        connection = _connection(settings)
    except LDAPSASLPrepError as exc:
        print("\nERROR: LDAP password contains an ASCII control character.")
        print("Rewrite LDAP_BIND_PASSWORD_FILE as a single-line text file without hidden characters.")
        print(f"password_diagnostics: {settings.ldap_password_diagnostics}")
        print(f"ldap3_error: {exc}")
        return 2
    except LDAPException as exc:
        print(f"\nERROR: LDAP bind/connect failed: {type(exc).__name__}: {exc}")
        return 2

    try:
        _print_root_dse(connection)
        ldap_filter = args.filter or _query_filter(args.query)
        attributes: list[str] | str = ALL_ATTRIBUTES if args.all_attributes else DEFAULT_ATTRIBUTES
        for search_base in _search_bases(settings):
            print(f"\n== Search base: {search_base}")
            connection.search(
                search_base=search_base,
                search_filter=ldap_filter,
                search_scope=SUBTREE,
                attributes=attributes,
                size_limit=args.limit,
            )
            entries = list(_filter_excluded_entries(connection.entries, settings.excluded_ous))
            print(f"Filter: {ldap_filter}")
            print(f"Returned entries: {len(entries)}")
            for index, entry in enumerate(entries, start=1):
                print(f"\n-- Entry {index}")
                print(json.dumps(_sanitize_entry(entry.entry_attributes_as_dict), ensure_ascii=False, indent=2))
    finally:
        connection.unbind()

    return 0


def _validate_settings(settings: Settings) -> None:
    missing = []
    if not settings.ldap_host:
        missing.append("LDAP_HOST")
    if not settings.ldap_bind_user:
        missing.append("LDAP_BIND_USER")
    if not settings.ldap_password:
        missing.append("LDAP_BIND_PASSWORD or LDAP_BIND_PASSWORD_FILE")
    if not settings.ldap_base_dn and not settings.included_ous:
        missing.append("LDAP_BASE_DN or LDAP_INCLUDED_OUS")

    diagnostics = settings.ldap_password_diagnostics
    if diagnostics["has_control_chars"]:
        print("\nERROR: LDAP password contains ASCII control characters.")
        print("The password value itself is not printed; only length and positions are shown.")
        print(f"password_diagnostics: {diagnostics}")
        raise SystemExit(2)

    if missing:
        print("\nERROR: missing required LDAP settings:")
        for name in missing:
            print(f"- {name}")
        raise SystemExit(2)


def _connection(settings: Settings) -> Connection:
    tls = None
    if settings.ldap_ca_cert_file:
        tls = Tls(
            ca_certs_file=settings.ldap_ca_cert_file,
            validate=ssl.CERT_REQUIRED,
            version=ssl.PROTOCOL_TLS_CLIENT,
        )

    server = Server(
        settings.ldap_host,
        port=settings.ldap_port,
        use_ssl=settings.ldap_use_ssl,
        get_info=ALL,
        tls=tls,
        connect_timeout=settings.ldap_connect_timeout_seconds,
    )
    return Connection(
        server,
        user=settings.ldap_bind_user,
        password=settings.ldap_password,
        auto_bind=True,
        receive_timeout=settings.ldap_read_timeout_seconds,
    )


def _print_settings_summary(settings: Settings) -> None:
    print("== LDAP settings")
    print(f"host: {settings.ldap_host}")
    print(f"port: {settings.ldap_port}")
    print(f"use_ssl: {settings.ldap_use_ssl}")
    print(f"bind_user: {settings.ldap_bind_user}")
    print(f"password_source: {_password_source(settings)}")
    print(f"base_dn: {settings.ldap_base_dn}")
    print(f"included_ous: {settings.included_ous or '<none>'}")
    print(f"excluded_ous: {settings.excluded_ous or '<none>'}")
    print(f"ca_cert_file: {settings.ldap_ca_cert_file or '<system trust>'}")
    print(f"connect_timeout_seconds: {settings.ldap_connect_timeout_seconds}")
    print(f"read_timeout_seconds: {settings.ldap_read_timeout_seconds}")


def _password_source(settings: Settings) -> str:
    if settings.ldap_bind_password_file:
        return f"file:{settings.ldap_bind_password_file}"
    if settings.ldap_bind_password:
        return "LDAP_BIND_PASSWORD"
    return "<empty>"


def _print_root_dse(connection: Connection) -> None:
    print("\n== RootDSE")
    connection.search(
        search_base="",
        search_filter="(objectClass=*)",
        search_scope=BASE,
        attributes=["defaultNamingContext", "namingContexts", "supportedLDAPVersion"],
    )
    for entry in connection.entries:
        print(json.dumps(_sanitize_entry(entry.entry_attributes_as_dict), ensure_ascii=False, indent=2))


def _search_bases(settings: Settings) -> list[str]:
    return settings.included_ous or [settings.ldap_base_dn]


def _query_filter(query: str | None) -> str:
    if not query:
        return "(|(&(objectClass=user)(objectCategory=person))(objectClass=contact))"

    escaped = escape_filter_chars(query.strip())
    return (
        "(|"
        f"(&(objectClass=user)(objectCategory=person)(displayName={escaped}))"
        f"(&(objectClass=contact)(displayName={escaped}))"
        f"(&(objectClass=user)(objectCategory=person)(cn={escaped}))"
        f"(&(objectClass=contact)(cn={escaped}))"
        f"(&(objectClass=user)(objectCategory=person)(sn={escaped}*))"
        f"(&(objectClass=contact)(sn={escaped}*))"
        ")"
    )


def _filter_excluded_entries(entries: Iterable[Any], excluded_ous: list[str]) -> Iterable[Any]:
    excluded = [item.lower() for item in excluded_ous]
    for entry in entries:
        dn = str(entry.entry_dn).lower()
        if excluded and any(item.lower() in dn for item in excluded):
            continue
        yield entry


def _sanitize_entry(attributes: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in attributes.items():
        if key in BINARY_ATTRIBUTES:
            sanitized[key] = _binary_summary(value)
        else:
            sanitized[key] = value
    return sanitized


def _binary_summary(value: Any) -> str:
    if isinstance(value, list):
        sizes = [len(item) for item in value if isinstance(item, bytes)]
        return f"<binary list count={len(value)} sizes={sizes}>"
    if isinstance(value, bytes):
        return f"<binary bytes={len(value)}>"
    return "<binary>"


if __name__ == "__main__":
    raise SystemExit(main())
