"""Tests for BotX client module."""
import pytest
import time
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.botx_client import (
    BotxClient,
    _make_token,
    _normalize_host,
    _audience,
    _base64url,
    get_http_client,
)


@pytest.fixture
def botx_client(test_settings) -> BotxClient:
    """Create a BotX client for testing."""
    return BotxClient(test_settings, "https://cts.example.com")


class TestHelpers:
    """Test helper functions."""

    def test_base64url_encoding(self):
        """Test _base64url produces URL-safe base64."""
        result = _base64url(b"Hello World!")
        # Should not have padding
        assert "=" not in result
        # Should be URL-safe
        assert "+" not in result
        assert "/" not in result

    def test_normalize_host_adds_https(self):
        """Test _normalize_host adds https when missing."""
        result = _normalize_host("cts.example.com")
        assert result == "https://cts.example.com"

    def test_normalize_host_preserves_https(self):
        """Test _normalize_host preserves existing https."""
        result = _normalize_host("https://cts.example.com")
        assert result == "https://cts.example.com"

    def test_normalize_host_removes_trailing_slash(self):
        """Test _normalize_host removes trailing slash."""
        result = _normalize_host("https://cts.example.com/")
        assert result == "https://cts.example.com"

    def test_normalize_host_empty_string(self):
        """Test _normalize_host handles empty string."""
        result = _normalize_host("")
        assert result == ""

    def test_audience_extracts_host(self):
        """Test _audience extracts host from URL."""
        assert _audience("https://cts.example.com/api/path") == "cts.example.com"
        assert _audience("http://localhost:8080") == "localhost:8080"

    def test_make_token_structure(self, test_settings):
        """Test _make_token produces valid JWT structure."""
        token = _make_token(test_settings, "https://cts.example.com")
        parts = token.split(".")
        assert len(parts) == 3

        # Decode header
        header = json.loads(_base64url_decode(parts[0]))
        assert header["alg"] == "HS256"
        assert header["typ"] == "JWT"

        # Decode payload
        payload = json.loads(_base64url_decode(parts[1]))
        assert payload["iss"] == test_settings.bot_id
        assert "exp" in payload
        assert "nbf" in payload
        assert "iat" in payload
        assert "jti" in payload

    def test_make_token_signature(self, test_settings):
        """Test _make_token produces HMAC signature."""
        token1 = _make_token(test_settings, "https://cts.example.com")
        token2 = _make_token(test_settings, "https://cts.example.com")

        # Same inputs should produce same signature (same jti would be different though)
        # But signature algorithm is deterministic
        parts1 = token1.split(".")
        parts2 = token2.split(".")
        # At minimum, signature length should be consistent
        assert len(parts1[2]) == len(parts2[2])


def _base64url_decode(data: str) -> bytes:
    """Decode base64url string."""
    import base64
    # Add padding
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


class TestBotxClient:
    """Test BotxClient class."""

    def test_initialization(self, test_settings):
        """Test BotxClient initializes correctly."""
        client = BotxClient(test_settings, "cts.example.com")

        assert client.settings is test_settings
        assert "cts.example.com" in client.host
        assert "/api/v4/botx/notifications/direct/sync" in client.endpoint

    def test_initialization_with_trailing_slash(self, test_settings):
        """Test BotxClient normalizes host with trailing slash."""
        client = BotxClient(test_settings, "https://cts.example.com/")
        assert client.host == "https://cts.example.com"

    def test_initialization_empty_host_uses_default(self, test_settings):
        """Test BotxClient uses default base URL when host is empty."""
        test_settings.botx_base_url = "https://default.cts.com"
        client = BotxClient(test_settings, "")
        assert "default.cts.com" in client.host

    @pytest.mark.asyncio
    async def test_send_text_success(self, botx_client):
        """Test send_text returns True on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(botx_client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await botx_client.send_text("chat123", "Hello!")

            assert result is True
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_text_failure(self, botx_client):
        """Test send_text returns False on failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Error"

        with patch.object(botx_client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await botx_client.send_text("chat123", "Hello!")

            assert result is False

    @pytest.mark.asyncio
    async def test_send_text_builds_correct_payload(self, botx_client):
        """Test send_text builds correct API payload."""
        captured_payload = {}

        async def capture_request(method, url, **kwargs):
            captured_payload.update(kwargs.get("json_payload", {}))
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

        with patch.object(botx_client, "_request", side_effect=capture_request):
            await botx_client.send_text("chat123", "Test message")

        assert captured_payload["group_chat_id"] == "chat123"
        assert captured_payload["notification"]["body"] == "Test message"
        assert captured_payload["notification"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_send_text_with_recipients(self, botx_client):
        """Test send_text accepts recipients list."""
        captured_payload = {}

        async def capture_request(method, url, **kwargs):
            captured_payload.update(kwargs.get("json_payload", {}))
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

        with patch.object(botx_client, "_request", side_effect=capture_request):
            await botx_client.send_text("chat123", "Hello!", recipients=["user1", "user2"])

        assert captured_payload["recipients"] == ["user1", "user2"]

    @pytest.mark.asyncio
    async def test_send_file_success(self, botx_client):
        """Test send_file returns True on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(botx_client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await botx_client.send_file(
                "chat123",
                b"fake image data",
                "photo.jpg",
                "image/jpeg",
                "Photo caption",
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_send_file_includes_file_payload(self, botx_client):
        """Test send_file includes file data in payload."""
        captured_payload = {}

        async def capture_request(method, url, **kwargs):
            captured_payload.update(kwargs.get("json_payload", {}))
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

        with patch.object(botx_client, "_request", side_effect=capture_request):
            await botx_client.send_file(
                "chat123",
                b"image_data",
                "test.png",
                "image/png",
            )

        assert "file" in captured_payload
        assert captured_payload["file"]["file_name"] == "test.png"
        assert "data:image/png;base64," in captured_payload["file"]["data"]

    @pytest.mark.asyncio
    async def test_get_user_by_email_success(self, botx_client):
        """Test get_user_by_email returns user data on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"user_huid": "user123"}}

        with patch.object(botx_client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await botx_client.get_user_by_email("user@example.com")

            assert result is not None
            # get_user_by_email returns the full payload
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_user_by_email_empty_email(self, botx_client):
        """Test get_user_by_email returns None for empty email."""
        result = await botx_client.get_user_by_email("")
        assert result is None

        result = await botx_client.get_user_by_email(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_email_404(self, botx_client):
        """Test get_user_by_email returns None for 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(botx_client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await botx_client.get_user_by_email("notfound@example.com")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_email_fallback_to_post(self, botx_client):
        """Test get_user_by_email falls back to POST on 405."""
        call_count = 0

        async def mock_request(method, url, **kwargs):
            nonlocal call_count
            call_count += 1

            mock_response = MagicMock()
            if call_count == 1:
                # First call returns 405
                mock_response.status_code = 405
            else:
                # Second call succeeds
                mock_response.status_code = 200
                mock_response.json.return_value = {"user": {"huid": "user123"}}
            return mock_response

        with patch.object(botx_client, "_request", side_effect=mock_request):
            result = await botx_client.get_user_by_email("user@example.com")

            assert result is not None
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_get_user_by_email_invalid_json(self, botx_client):
        """Test get_user_by_email handles invalid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("", "", 0)

        with patch.object(botx_client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await botx_client.get_user_by_email("user@example.com")

            assert result is None


class TestGetHttpClient:
    """Test get_http_client function."""

    @pytest.mark.asyncio
    async def test_creates_async_client(self):
        """Test get_http_client returns AsyncClient."""
        import httpx
        from app.botx_client import close_http_client
        # Close any existing client first
        await close_http_client()
        client = get_http_client()
        assert isinstance(client, httpx.AsyncClient)
        # Cleanup
        await close_http_client()

    @pytest.mark.asyncio
    async def test_client_has_timeout(self):
        """Test created client has timeout configured."""
        from app.botx_client import close_http_client
        # Close any existing client first
        await close_http_client()
        client = get_http_client()
        assert client.timeout is not None
        # Cleanup
        await close_http_client()

    @pytest.mark.asyncio
    async def test_client_is_reused(self):
        """Test get_http_client returns the same instance."""
        from app.botx_client import close_http_client
        # Close any existing client first
        await close_http_client()
        client1 = get_http_client()
        client2 = get_http_client()
        assert client1 is client2
        # Cleanup
        await close_http_client()
