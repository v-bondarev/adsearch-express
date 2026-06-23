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
    parser.add_argument("--list-ous", action="store_true", help="List organizationalUnit objects for base DN discovery.")
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
        root_dse = _print_root_dse(connection)
        search_bases = _search_bases(settings, root_dse)
        if args.list_ous:
            _print_ous(connection, search_bases, args.limit)
            return 0

        ldap_filter = args.filter or _query_filter(args.query)
        attributes: list[str] | str = ALL_ATTRIBUTES if args.all_attributes else DEFAULT_ATTRIBUTES
        for search_base in search_bases:
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


def _print_root_dse(connection: Connection) -> dict[str, Any]:
    print("\n== RootDSE")
    connection.search(
        search_base="",
        search_filter="(objectClass=*)",
        search_scope=BASE,
        attributes=["defaultNamingContext", "namingContexts", "supportedLDAPVersion"],
    )
    root_dse: dict[str, Any] = {}
    for entry in connection.entries:
        root_dse = _sanitize_entry(entry.entry_attributes_as_dict)
        print(json.dumps(root_dse, ensure_ascii=False, indent=2))
    return root_dse


def _search_bases(settings: Settings, root_dse: dict[str, Any]) -> list[str]:
    if settings.included_ous:
        return settings.included_ous
    if settings.ldap_base_dn:
        return [settings.ldap_base_dn]
    default_naming_context = root_dse.get("defaultNamingContext")
    if isinstance(default_naming_context, list) and default_naming_context:
        return [str(default_naming_context[0])]
    if isinstance(default_naming_context, str) and default_naming_context:
        return [default_naming_context]
    naming_contexts = root_dse.get("namingContexts")
    if isinstance(naming_contexts, list) and naming_contexts:
        return [str(naming_contexts[0])]
    raise SystemExit("ERROR: cannot determine search base from RootDSE. Set LDAP_BASE_DN manually.")


def _print_ous(connection: Connection, search_bases: list[str], limit: int) -> None:
    for search_base in search_bases:
        print(f"\n== Organizational units under: {search_base}")
        connection.search(
            search_base=search_base,
            search_filter="(objectClass=organizationalUnit)",
            search_scope=SUBTREE,
            attributes=["distinguishedName", "ou", "description"],
            size_limit=limit,
        )
        print(f"Returned OUs: {len(connection.entries)}")
        for index, entry in enumerate(connection.entries, start=1):
            print(f"\n-- OU {index}")
            print(json.dumps(_sanitize_entry(entry.entry_attributes_as_dict), ensure_ascii=False, indent=2))


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
