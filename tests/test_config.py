"""Tests for config module."""
import pytest
from pathlib import Path
from app.config import Settings, get_settings


class TestSettings:
    """Test Settings configuration."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = Settings()
        assert settings.app_env == "local"
        assert settings.app_port == 8181
        assert settings.log_level == "INFO"
        assert settings.search_limit == 5
        assert settings.cache_ttl_seconds == 86400

    def test_admin_huids_parsing(self, test_settings):
        """Test admin_huids property parses comma-separated values."""
        settings = Settings(bot_admin_huids="uuid1, uuid2,uuid3")
        assert settings.admin_huids == {"uuid1", "uuid2", "uuid3"}

    def test_admin_huids_empty(self):
        """Test admin_huids returns empty set when not set."""
        settings = Settings()
        assert settings.admin_huids == set()

    def test_admin_alert_chat_ids_parsing(self):
        """Test admin_alert_chat_ids property parses comma-separated values."""
        settings = Settings(bot_admin_alert_chat_ids="chat1, chat2")
        assert settings.admin_alert_chat_ids == ["chat1", "chat2"]

    def test_included_ous_parsing(self):
        """Test included_ous property parses semicolon-separated values."""
        settings = Settings(ldap_included_ous="OU=Employees,DC=example,DC=com;OU=Contacts,DC=example,DC=com")
        assert settings.included_ous == ["OU=Employees,DC=example,DC=com", "OU=Contacts,DC=example,DC=com"]

    def test_excluded_ous_parsing(self):
        """Test excluded_ous property parses semicolon-separated values."""
        settings = Settings(ldap_excluded_ous="OU=Disabled,DC=example,DC=com;OU=Temp")
        assert settings.excluded_ous == ["OU=Disabled,DC=example,DC=com", "OU=Temp"]

    def test_ldap_password_from_direct_value(self):
        """Test ldap_password returns direct value when no password file."""
        settings = Settings(ldap_bind_password="direct_password")
        assert settings.ldap_password == "direct_password"

    def test_ldap_password_from_file(self, tmp_path: Path):
        """Test ldap_password reads from file when configured."""
        password_file = tmp_path / "ldap_password"
        password_file.write_text("file_password\n")
        settings = Settings(ldap_bind_password_file=password_file)
        assert settings.ldap_password == "file_password"

    def test_ldap_password_diagnostics(self):
        """Test ldap_password_diagnostics returns correct info."""
        settings = Settings(ldap_bind_password="simple_pass")
        diagnostics = settings.ldap_password_diagnostics
        assert diagnostics["length"] == 11
        assert diagnostics["has_control_chars"] is False
        assert diagnostics["control_chars"] == []

    def test_ldap_password_diagnostics_with_control_chars(self):
        """Test ldap_password_diagnostics detects control characters."""
        settings = Settings(ldap_bind_password="pass\x00word")
        diagnostics = settings.ldap_password_diagnostics
        assert diagnostics["has_control_chars"] is True
        assert diagnostics["control_chars"] == [{"position": 4, "codepoint": 0}]

    def test_ldap_password_file_empty_to_none(self):
        """Test empty password file path becomes None."""
        settings = Settings(ldap_bind_password_file="")
        assert settings.ldap_bind_password_file is None

    def test_settings_singleton(self):
        """Test get_settings returns cached instance."""
        get_settings.cache_clear()
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
