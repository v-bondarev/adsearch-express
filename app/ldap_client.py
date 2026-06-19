import logging
import ssl
from contextlib import contextmanager
from typing import Iterator

from ldap3 import ALL, ALL_ATTRIBUTES, Connection, Server, Tls

from app.config import Settings
from app.models import EmployeeCard, SearchResult

logger = logging.getLogger(__name__)


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
            password=self.settings.ldap_bind_password,
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
        # Final LDAP filters must be confirmed during Stage 0 with real AD data.
        logger.info("LDAP search requested")
        _ = query
        return []

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

