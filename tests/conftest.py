"""Test fixtures and configuration."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.config import Settings


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Create test settings with temporary paths."""
    return Settings(
        app_env="test",
        app_port=8181,
        log_level="DEBUG",
        bot_id="test-bot-id",
        bot_secret_key="test-secret-key",
        botx_base_url="https://cts.example.com",
        ldap_host="ldap.example.com",
        ldap_port=636,
        ldap_use_ssl=True,
        ldap_bind_user="test_user",
        ldap_bind_password="test_password",
        ldap_base_dn="DC=example,DC=com",
        ldap_included_ous="OU=Employees,DC=example,DC=com",
        search_limit=5,
        cache_db_path=tmp_path / "cache.sqlite3",
        cache_ttl_seconds=3600,
    )


@pytest.fixture
def mock_ldap_entry():
    """Create a mock LDAP entry with common attributes."""
    entry = MagicMock()
    entry.entry_dn = "CN=Иванов Иван Иванович,OU=Employees,DC=example,DC=com"
    entry.entry_attributes_as_dict = {
        "distinguishedName": ["CN=Иванов Иван Иванович,OU=Employees,DC=example,DC=com"],
        "objectClass": ["person", "user"],
        "cn": ["Иванов Иван Иванович"],
        "name": ["Иванов Иван Иванович"],
        "displayName": ["Иванов Иван Иванович"],
        "sn": ["Иванов"],
        "givenName": ["Иван"],
        "extensionAttribute5": ["1985-06-24"],
        "title": ["Инженер"],
        "department": ["IT Department"],
        "company": ["Example Corp"],
        "mail": ["ivanov@example.com"],
        "telephoneNumber": ["1234"],
        "mobile": ["+79001234567"],
        "physicalDeliveryOfficeName": ["БЯ-9\\317"],
        "manager": ["CN=Петров Петр Петрович,OU=Employees,DC=example,DC=com"],
        "userAccountControl": [512],
        "thumbnailPhoto": [b"\x89PNG\r\n\x1a\n fake png data"],
    }
    return entry


@pytest.fixture
def mock_contact_entry():
    """Create a mock LDAP contact entry."""
    entry = MagicMock()
    entry.entry_dn = "CN=Контакт Контактович (External Corp),OU=Contacts,DC=example,DC=com"
    entry.entry_attributes_as_dict = {
        "distinguishedName": ["CN=Контакт Контактович (External Corp),OU=Contacts,DC=example,DC=com"],
        "objectClass": ["contact"],
        "cn": ["Контакт Контактович (External Corp)"],
        "name": ["Контакт Контактович"],
        "displayName": ["Контакт Контактович"],
        "sn": ["Контактович"],
        "givenName": ["Контакт"],
        "company": ["External Corp"],
        "mail": ["contact@external.com"],
        "telephoneNumber": ["5678"],
    }
    return entry


@pytest.fixture
def mock_ldap_connection(mock_ldap_entry, mock_contact_entry):
    """Create a mock LDAP connection."""
    connection = MagicMock()
    connection.entries = [mock_ldap_entry, mock_contact_entry]
    return connection
