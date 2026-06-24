"""Tests for LDAP client module."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from ldap3 import Connection, Server

from app.ldap_client import (
    LdapClient,
    _build_people_filter,
    _build_name_filter,
    _build_name_token_filter,
    _entry_to_employee_card,
    _entry_to_search_result,
    _split_name_and_company,
    _split_office_room,
    _normalize_office,
    _manager_display_name,
    SEARCH_ATTRIBUTES,
)


class TestLdapClient:
    """Test LdapClient class."""

    def test_search_attributes_defined(self):
        """Test that SEARCH_ATTRIBUTES contains expected fields."""
        assert "cn" in SEARCH_ATTRIBUTES
        assert "displayName" in SEARCH_ATTRIBUTES
        assert "mail" in SEARCH_ATTRIBUTES
        assert "thumbnailPhoto" in SEARCH_ATTRIBUTES

    def test_client_initialization(self, test_settings):
        """Test LdapClient initializes with settings."""
        client = LdapClient(test_settings)
        assert client.settings is test_settings

    @patch("app.ldap_client.Connection")
    @patch("app.ldap_client.Server")
    def test_connection_creates_server_with_ssl(self, mock_server, mock_connection, test_settings):
        """Test connection creates Server with SSL when configured."""
        mock_conn_instance = MagicMock()
        mock_connection.return_value = mock_conn_instance

        client = LdapClient(test_settings)
        with client._connection():
            pass

        mock_server.assert_called_once()
        call_kwargs = mock_server.call_args[1]
        assert call_kwargs["use_ssl"] is True
        assert call_kwargs["port"] == 636
        assert "pool_name" not in call_kwargs
        assert "pool_size" not in call_kwargs
        assert "pool_lifetime" not in call_kwargs

    @patch("app.ldap_client.Server")
    def test_server_configuration_is_reused(self, mock_server, test_settings):
        """Test the immutable Server configuration is created only once."""
        server = MagicMock()
        mock_server.return_value = server
        client = LdapClient(test_settings)

        assert client._get_server() is server
        assert client._get_server() is server
        mock_server.assert_called_once()

    @patch("app.ldap_client.Server")
    def test_close_pool_releases_cached_server(self, mock_server, test_settings):
        """Test shutdown releases the cached Server configuration."""
        mock_server.return_value = MagicMock()
        client = LdapClient(test_settings)
        client._get_server()

        client.close_pool()

        assert client._server is None

    @patch("app.ldap_client.Connection")
    @patch("app.ldap_client.Server")
    def test_connection_with_ca_cert(self, mock_server, mock_connection, tmp_path, test_settings):
        """Test connection uses CA cert when configured."""
        ca_file = tmp_path / "ca.pem"
        ca_file.write_text("fake cert")

        test_settings.ldap_ca_cert_file = str(ca_file)
        mock_conn_instance = MagicMock()
        mock_connection.return_value = mock_conn_instance

        client = LdapClient(test_settings)
        with client._connection():
            pass

        call_kwargs = mock_server.call_args[1]
        assert call_kwargs["tls"] is not None

    @patch("app.ldap_client.Connection")
    @patch("app.ldap_client.Server")
    def test_connection_binds_with_credentials(self, mock_server, mock_connection, test_settings):
        """Test connection binds with configured credentials."""
        mock_conn_instance = MagicMock()
        mock_connection.return_value = mock_conn_instance

        client = LdapClient(test_settings)
        with client._connection():
            pass

        mock_connection.assert_called_once()
        call_kwargs = mock_connection.call_args[1]
        assert "svc_directory_bot" in str(call_kwargs["user"]) or call_kwargs["user"] == test_settings.ldap_bind_user
        assert call_kwargs["auto_bind"] is True

    @patch("app.ldap_client.Connection")
    @patch("app.ldap_client.Server")
    def test_connection_always_unbinds(self, mock_server, mock_connection, test_settings):
        """Test connection unbinds after use."""
        mock_conn_instance = MagicMock()
        mock_connection.return_value = mock_conn_instance

        client = LdapClient(test_settings)
        with client._connection():
            pass

        mock_conn_instance.unbind.assert_called_once()

    @patch("app.ldap_client.Connection")
    @patch("app.ldap_client.Server")
    def test_connection_unbinds_on_exception(self, mock_server, mock_connection, test_settings):
        """Test connection unbinds even if exception occurs."""
        mock_conn_instance = MagicMock()
        mock_connection.return_value = mock_conn_instance

        client = LdapClient(test_settings)
        with pytest.raises(RuntimeError):
            with client._connection():
                raise RuntimeError("Test exception")

        mock_conn_instance.unbind.assert_called_once()

    @patch("app.ldap_client.Connection")
    @patch("app.ldap_client.Server")
    def test_search_people_returns_empty_for_empty_query(self, mock_server, mock_connection, test_settings):
        """Test search_people returns empty list for whitespace-only query."""
        mock_conn_instance = MagicMock()
        mock_conn_instance.entries = []
        mock_connection.return_value = mock_conn_instance

        client = LdapClient(test_settings)
        results = client.search_people("   ")

        assert results == []

    @patch("app.ldap_client.Connection")
    @patch("app.ldap_client.Server")
    def test_search_people_deduplicates_by_dn(self, mock_server, mock_connection, test_settings):
        """Test search_people deduplicates entries by DN."""
        mock_entry = MagicMock()
        mock_entry.entry_dn = "CN=Test User,OU=Employees"
        mock_entry.entry_attributes_as_dict = {
            "cn": ["Test User"],
            "sn": ["User"],
            "givenName": ["Test"],
            "displayName": ["Test User"],
            "company": ["Test Corp"],
            "mail": ["test@example.com"],
            "objectClass": ["user"],
            "userAccountControl": [512],
            "title": ["Developer"],
            "department": ["IT"],
            "telephoneNumber": ["1234"],
            "physicalDeliveryOfficeName": ["Office-1"],
            "manager": ["CN=Boss,OU=Employees"],
            "thumbnailPhoto": [],
        }

        mock_conn_instance = MagicMock()
        mock_conn_instance.entries = [mock_entry, mock_entry]
        mock_connection.return_value = mock_conn_instance

        client = LdapClient(test_settings)
        results = client.search_people("Test")

        assert len(results) == 1

    @patch("app.ldap_client.Connection")
    @patch("app.ldap_client.Server")
    def test_search_people_respects_search_limit(self, mock_server, mock_connection, test_settings):
        """Test search_people uses search_limit + 1 as LDAP size limit."""
        mock_conn_instance = MagicMock()
        mock_conn_instance.entries = []
        mock_connection.return_value = mock_conn_instance

        test_settings.search_limit = 5
        client = LdapClient(test_settings)
        client.search_people("test")

        mock_conn_instance.search.assert_called()
        call_kwargs = mock_conn_instance.search.call_args[1]
        assert call_kwargs["size_limit"] == 6  # search_limit + 1


class TestBuildFilters:
    """Test LDAP filter building functions."""

    def test_build_people_filter_structure(self):
        """Test _build_people_filter returns valid LDAP filter."""
        filter_str = _build_people_filter("Иванов")
        assert filter_str.startswith("(|")
        assert filter_str.endswith(")")
        assert "(objectClass=user)" in filter_str
        assert "(objectClass=contact)" in filter_str

    def test_build_people_filter_includes_required_fields(self):
        """Test filter requires company and mail."""
        filter_str = _build_people_filter("test")
        assert "(company=*)" in filter_str
        assert "(mail=*)" in filter_str

    def test_build_people_filter_excludes_disabled_users(self):
        """Test filter excludes disabled users."""
        filter_str = _build_people_filter("test")
        assert "userAccountControl" in filter_str
        assert ":1.2.840.113556.1.4.803:=2" in filter_str  # Disabled flag

    def test_build_name_filter_single_token(self):
        """Test _build_name_filter with single token."""
        filter_str = _build_name_filter("Иванов")
        assert "Иванов" in filter_str or "*" in filter_str

    def test_build_name_filter_multiple_tokens(self):
        """Test _build_name_filter with multiple tokens."""
        filter_str = _build_name_filter("Иванов Иван")
        assert "Иванов" in filter_str
        assert "Иван" in filter_str
        # Should use AND for multiple tokens
        assert filter_str.count("&") >= 1

    def test_build_name_filter_empty_query(self):
        """Test _build_name_filter with empty query."""
        filter_str = _build_name_filter("")
        assert "cn=__empty_query__" in filter_str

    def test_build_name_token_filter_escapes_special_chars(self):
        """Test token filter escapes special LDAP characters."""
        filter_str = _build_name_token_filter("test*user")
        # Should escape asterisk
        assert "test\\2auser" in filter_str or "test*user" not in filter_str

    def test_build_name_token_filter_searches_multiple_fields(self):
        """Test token filter searches displayName, cn, sn, givenName."""
        filter_str = _build_name_token_filter("test")
        assert "displayName" in filter_str
        assert "cn" in filter_str
        assert "givenName" in filter_str
        assert "sn" in filter_str


class TestEntryConversion:
    """Test LDAP entry conversion functions."""

    def test_split_name_and_company_with_parentheses(self):
        """Test _split_name_and_company extracts company from parentheses."""
        name, company = _split_name_and_company("Иванов Иван (External Corp)")
        assert name == "Иванов Иван"
        assert company == "External Corp"

    def test_split_name_and_company_without_parentheses(self):
        """Test _split_name_and_company returns full string when no parentheses."""
        name, company = _split_name_and_company("Иванов Иван Иванович")
        assert name == "Иванов Иван Иванович"
        assert company is None

    def test_split_name_and_company_with_spaces_in_company(self):
        """Test _split_name_and_company handles spaces in company name."""
        name, company = _split_name_and_company("User Name (My Company LLC)")
        assert name == "User Name"
        assert company == "My Company LLC"

    def test_split_office_room_with_backslash(self):
        """Test _split_office_room splits on backslash."""
        office, room = _split_office_room("БЯ-9\\317")
        assert office == "БЯ9"
        assert room == "317"

    def test_split_office_room_without_backslash(self):
        """Test _split_office_room returns office only when no backslash."""
        office, room = _split_office_room("Офис-1")
        assert office == "Офис1"
        assert room is None

    def test_split_office_room_empty(self):
        """Test _split_office_room handles empty value."""
        office, room = _split_office_room(None)
        assert office is None
        assert room is None

    def test_normalize_office_removes_dashes(self):
        """Test _normalize_office removes dashes."""
        assert _normalize_office("БЯ-9") == "БЯ9"
        assert _normalize_office("Office-123") == "Office123"

    def test_normalize_office_handles_empty(self):
        """Test _normalize_office handles empty string."""
        assert _normalize_office("") is None
        assert _normalize_office("   ") is None

    def test_manager_display_name_extracts_cn(self):
        """Test _manager_display_name extracts CN from DN."""
        result = _manager_display_name("CN=Петров Петр,OU=Employees,DC=example,DC=com")
        assert result == "Петров Петр"

    def test_manager_display_name_handles_empty(self):
        """Test _manager_display_name handles None."""
        assert _manager_display_name(None) is None

    def test_manager_display_name_handles_non_cn(self):
        """Test _manager_display_name returns original for non-CN format."""
        result = _manager_display_name("SMTP:boss@example.com")
        assert result == "SMTP:boss@example.com"

    def test_manager_display_name_handles_escaped_comma(self):
        """Test _manager_display_name handles escaped commas in CN."""
        result = _manager_display_name("CN=Иванов\\, Петр,OU=Employees,DC=example,DC=com")
        assert result == "Иванов, Петр"

    def test_entry_to_employee_card_user(self, mock_ldap_entry):
        """Test _entry_to_employee_card identifies user object type."""
        card = _entry_to_employee_card(mock_ldap_entry.entry_attributes_as_dict, mock_ldap_entry.entry_dn)
        assert card.object_type == "user"
        assert card.display_name == "Иванов Иван Иванович"
        assert card.company == "Example Corp"
        assert card.email == "ivanov@example.com"

    def test_entry_to_employee_card_contact(self, mock_contact_entry):
        """Test _entry_to_employee_card identifies contact object type."""
        card = _entry_to_employee_card(mock_contact_entry.entry_attributes_as_dict, mock_contact_entry.entry_dn)
        assert card.object_type == "contact"
        assert card.company == "External Corp"

    def test_entry_to_search_result_from_card(self, mock_ldap_entry):
        """Test _entry_to_search_result creates correct structure."""
        result = _entry_to_search_result(mock_ldap_entry.entry_attributes_as_dict, mock_ldap_entry.entry_dn)
        assert result.object_id == mock_ldap_entry.entry_dn
        assert result.display_name == "Иванов Иван Иванович"
        assert result.email == "ivanov@example.com"
        assert result.photo is not None


class TestLdapClientSearchBases:
    """Test search base configuration."""

    def test_search_bases_uses_included_ous(self, test_settings):
        """Test _search_bases returns included OUs when configured."""
        test_settings.ldap_included_ous = "OU=Employees,DC=example,DC=com;OU=Contacts"
        client = LdapClient(test_settings)
        bases = client._search_bases()
        assert "OU=Employees,DC=example,DC=com" in bases
        assert "OU=Contacts" in bases

    def test_search_bases_fallback_to_base_dn(self, test_settings):
        """Test _search_bases returns base DN when no included OUs."""
        test_settings.ldap_included_ous = ""
        client = LdapClient(test_settings)
        bases = client._search_bases()
        assert bases == [test_settings.ldap_base_dn]

    def test_is_excluded_dn_matches_substring(self, test_settings):
        """Test _is_excluded_dn matches DN containing excluded string."""
        test_settings.ldap_excluded_ous = "OU=Disabled"
        client = LdapClient(test_settings)
        assert client._is_excluded_dn("CN=User,OU=Disabled,DC=example") is True
        assert client._is_excluded_dn("CN=User,OU=Active,DC=example") is False

    def test_is_excluded_dn_case_insensitive(self, test_settings):
        """Test _is_excluded_dn is case insensitive."""
        test_settings.ldap_excluded_ous = "ou=disabled"
        client = LdapClient(test_settings)
        assert client._is_excluded_dn("CN=User,OU=Disabled,DC=example") is True
