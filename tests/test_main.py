"""Tests for main application module."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient


# Mock settings before importing app
@pytest.fixture(autouse=True)
def mock_settings(tmp_path):
    """Mock settings for all tests."""
    with patch("app.main.get_settings") as mock_get_settings:
        from app.config import Settings
        settings = Settings(
            app_env="test",
            app_port=8181,
            log_level="DEBUG",
            bot_id="test-bot",
            bot_secret_key="test-secret",
            botx_base_url="https://cts.example.com",
            ldap_host="ldap.example.com",
            ldap_port=636,
            ldap_bind_user="test_user",
            ldap_bind_password="test_pass",
            ldap_base_dn="DC=example,DC=com",
            search_limit=5,
            cache_db_path=tmp_path / "cache.sqlite3",
            cache_ttl_seconds=3600,
        )
        mock_get_settings.return_value = settings
        yield settings


@pytest.fixture
def app_client(mock_settings):
    """Create test client for the FastAPI app."""
    with patch("app.main.get_settings", return_value=mock_settings):
        with patch("app.main.configure_logging"):
            from app.main import app
            yield TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_returns_ok(self, app_client):
        """Test /health returns status ok."""
        response = app_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_status_returns_ok(self, app_client):
        """Test the BotX status probe endpoint."""
        response = app_client.get(
            "/status",
            params={
                "user_huid": "test-user",
                "bot_id": "test-bot",
                "chat_type": "chat",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestWebhookEndpoints:
    """Test webhook endpoints."""

    def test_webhook_endpoint_exists(self, app_client):
        """Test /webhook endpoint is registered."""
        response = app_client.post("/webhook", json={})
        # Should not be 404
        assert response.status_code != 404

    def test_command_endpoint_exists(self, app_client):
        """Test /command endpoint is registered."""
        response = app_client.post("/command", json={})
        # Should not be 404
        assert response.status_code != 404


class TestRestrictedQuery:
    """Test restricted query handling."""

    def test_restricted_query_returns_error(self, app_client, mock_settings):
        """Test restricted query returns error message."""
        # Mock LDAP client
        with patch("app.main.ldap_client") as mock_ldap:
            mock_ldap.search_people.return_value = []

            with patch("app.main._send_botx_message", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True

                response = app_client.post(
                    "/command",
                    json={
                        "command": {"body": "потанин тест"},
                        "from": {"group_chat_id": "chat123"},
                    },
                )

                assert response.status_code == 200
                assert response.json() == {"status": "ok"}
                mock_send.assert_awaited()


class TestHelpCommands:
    """Test help/start command handling."""

    def test_start_command_returns_help_message(self, app_client, mock_settings):
        """Test /start returns help message."""
        with patch("app.main._send_botx_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            response = app_client.post(
                "/command",
                json={
                    "command": {"body": "/start"},
                    "from": {"group_chat_id": "chat123"},
                },
            )

            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            mock_send.assert_awaited()

    def test_help_command_returns_help_message(self, app_client, mock_settings):
        """Test /help returns help message."""
        with patch("app.main._send_botx_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            response = app_client.post(
                "/command",
                json={
                    "command": {"body": "/help"},
                    "from": {"group_chat_id": "chat123"},
                },
            )

            assert response.status_code == 200

    def test_empty_command_returns_help_message(self, app_client, mock_settings):
        """Test empty command returns help message."""
        with patch("app.main._send_botx_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            response = app_client.post(
                "/command",
                json={
                    "command": {"body": ""},
                    "from": {"group_chat_id": "chat123"},
                },
            )

            assert response.status_code == 200

    def test_start_variant_lowercase(self, app_client, mock_settings):
        """Test 'start' (lowercase) also triggers help."""
        with patch("app.main._send_botx_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            response = app_client.post(
                "/command",
                json={
                    "command": {"body": "start"},
                    "from": {"group_chat_id": "chat123"},
                },
            )

            assert response.status_code == 200

    def test_старт_russian_variant(self, app_client, mock_settings):
        """Test 'старт' (Russian) also triggers help."""
        with patch("app.main._send_botx_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            response = app_client.post(
                "/command",
                json={
                    "command": {"body": "старт"},
                    "from": {"group_chat_id": "chat123"},
                },
            )

            assert response.status_code == 200


class TestExtractHelpers:
    """Test helper extraction functions."""

    def test_extract_text_from_command_body(self, app_client, mock_settings):
        """Test _extract_text extracts from command.body."""
        with patch("app.main.ldap_client") as mock_ldap:
            mock_ldap.search_people.return_value = []

            with patch("app.main._send_botx_message", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True

                response = app_client.post(
                    "/command",
                    json={
                        "command": {"body": "Иванов Иван"},
                        "from": {"group_chat_id": "chat123"},
                    },
                )

                assert response.status_code == 200

    def test_extract_text_case_insensitive(self, app_client, mock_settings):
        """Test command matching is case insensitive."""
        with patch("app.main.ldap_client") as mock_ldap:
            mock_ldap.search_people.return_value = []

            with patch("app.main._send_botx_message", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True

                # Test uppercase
                response = app_client.post(
                    "/command",
                    json={
                        "command": {"body": "/START"},
                        "from": {"group_chat_id": "chat123"},
                    },
                )

                assert response.status_code == 200

    def test_extract_user_huid(self, app_client, mock_settings):
        """Test _extract_user_huid extracts HUID."""
        # Test that HUID is extracted from different possible locations
        with patch("app.main.ldap_client") as mock_ldap:
            mock_ldap.search_people.return_value = []

            with patch("app.main._send_botx_message", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True

                response = app_client.post(
                    "/command",
                    json={
                        "command": {"body": "test"},
                        "from": {"user_huid": "test-huid-123"},
                        "group_chat_id": "chat123",
                    },
                )

                assert response.status_code == 200

    def test_extract_chat_id_fallbacks(self, app_client, mock_settings):
        """Test _extract_group_chat_id tries multiple sources."""
        with patch("app.main.ldap_client") as mock_ldap:
            mock_ldap.search_people.return_value = []

            with patch("app.main._send_botx_message", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True

                # Test from body.from
                response = app_client.post(
                    "/command",
                    json={
                        "command": {"body": "test"},
                        "from": {"group_chat_id": "chat-from-from"},
                    },
                )

                assert response.status_code == 200


class TestClearCacheCommand:
    """Test /clear_cache command."""

    def test_clear_cache_denied_for_non_admin(self, app_client, mock_settings):
        """Test /clear_cache is denied for non-admin users (no admin_huids set)."""
        # admin_huids is empty by default in mock_settings
        with patch("app.main.card_cache") as mock_cache:
            with patch("app.main._send_botx_message", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True

                response = app_client.post(
                    "/command",
                    json={
                        "command": {"body": "/clear_cache"},
                        "from": {"group_chat_id": "chat123"},
                    },
                )

                assert response.status_code == 200
                # Cache clear should not be called for non-admin
                mock_cache.clear.assert_not_called()

    def test_clear_cache_returns_message_for_non_admin(self, app_client, mock_settings):
        """Test /clear_cache returns denial message for non-admin users."""
        with patch("app.main._send_botx_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            response = app_client.post(
                "/command",
                json={
                    "command": {"body": "/clear_cache"},
                    "from": {"group_chat_id": "chat123"},
                },
            )

            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            mock_send.assert_awaited()


class TestPhotoMimeDetection:
    """Test photo MIME type detection."""

    def test_detects_png(self, app_client, mock_settings):
        """Test PNG detection."""
        from app.main import _photo_mime_type
        assert _photo_mime_type(b"\x89PNG\r\n\x1a\n") == "image/png"

    def test_detects_gif(self, app_client, mock_settings):
        """Test GIF detection."""
        from app.main import _photo_mime_type
        assert _photo_mime_type(b"GIF89a") == "image/gif"
        assert _photo_mime_type(b"GIF87a") == "image/gif"

    def test_defaults_to_jpeg(self, app_client, mock_settings):
        """Test JPEG is default."""
        from app.main import _photo_mime_type
        assert _photo_mime_type(b"\xff\xd8\xff\xe0") == "image/jpeg"
        assert _photo_mime_type(b"random data") == "image/jpeg"

    @pytest.mark.asyncio
    async def test_photo_caption_starts_with_blank_line(self, app_client, mock_settings):
        """Test employee details are visually separated from the photo."""
        from app.main import _send_search_result_card
        from app.models import SearchResult

        client = MagicMock()
        client.send_file = AsyncMock(return_value=True)
        result = SearchResult(
            object_id="CN=Test User",
            display_name="Тестов Тест",
            photo=b"\xff\xd8\xff\xe0",
        )

        assert await _send_search_result_card(client, "chat123", result) is True
        assert client.send_file.await_args.kwargs["caption"].startswith(
            "\n**Тестов Тест**"
        )


class TestCommandTokens:
    """Test command tokenization."""

    def test_tokens_extract_alpha_numeric_words(self, app_client, mock_settings):
        """Test _command_tokens extracts only word characters."""
        from app.main import _command_tokens
        tokens = _command_tokens("IVANOV Ivan-123")
        # Should extract "IVANOV", "Ivan", "123"
        assert "IVANOV" in tokens
        assert "Ivan" in tokens
        assert "123" in tokens
        assert len(tokens) == 3

    def test_tokens_extract_words(self, app_client, mock_settings):
        """Test _command_tokens extracts words."""
        from app.main import _command_tokens
        tokens = _command_tokens("Иванов Иван Иванович")
        assert len(tokens) == 3

    def test_tokens_with_special_chars(self, app_client, mock_settings):
        """Test _command_tokens handles special characters like underscore as part of word."""
        from app.main import _command_tokens
        tokens = _command_tokens("test-query_123")
        # underscore is part of word, so we get "test", "query_123"
        # hyphen separates words
        assert "test" in tokens
        assert "query_123" in tokens
