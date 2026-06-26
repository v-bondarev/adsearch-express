from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.models import SearchResult


@pytest.fixture
def api_context(monkeypatch, tmp_path):
    from app import api_main

    settings = Settings(
        app_env="test",
        internal_api_token="test-internal-token",
        bot_id="test-bot",
        bot_secret_key="test-secret",
        botx_base_url="https://cts.example.com",
        ldap_host="ldap.example.com",
        ldap_bind_user="test-user",
        ldap_bind_password="test-password",
        ldap_base_dn="DC=example,DC=com",
        search_limit=2,
        cache_db_path=tmp_path / "cache.sqlite3",
    )
    ldap_client = MagicMock()
    monkeypatch.setattr(api_main, "settings", settings)
    monkeypatch.setattr(api_main, "ldap_client", ldap_client)
    api_main.photo_store.clear()
    monkeypatch.setattr(
        api_main,
        "_enrich_results_with_express_links",
        AsyncMock(side_effect=lambda results, _: results),
    )
    with TestClient(api_main.app) as client:
        yield api_main, client, ldap_client
    api_main.photo_store.clear()


def _headers(token: str = "test-internal-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _result(index: int = 1, **changes) -> SearchResult:
    values = {
        "object_id": f"CN=Employee {index},OU=Users,DC=example,DC=com",
        "display_name": f"Сотрудник {index}",
        "title": "Инженер",
        "department": "ИТ",
        "company": "Пример",
        "phone": "12-34",
        "email": f"employee{index}@example.com",
        "office": "БЯ9",
        "room": "317",
        "birthday": "24 июня",
        "manager": "Руководитель",
        "express_chat_url": "https://xlnk.ms/open/profile/test",
        "photo": b"photo bytes",
        "object_type": "user",
    }
    values.update(changes)
    return SearchResult(**values)


class TestInternalSearchApi:
    def test_search_returns_one_result(self, api_context):
        _, client, ldap_client = api_context
        ldap_client.search_people.return_value = [_result()]

        response = client.post(
            "/api/search",
            headers=_headers(),
            json={"query": "Иванов Иван"},
        )

        assert response.status_code == 200
        assert response.json()["results"][0]["display_name"] == "Сотрудник 1"
        assert response.json()["has_more"] is False

    def test_search_limits_results_and_sets_has_more(self, api_context):
        _, client, ldap_client = api_context
        ldap_client.search_people.return_value = [_result(1), _result(2), _result(3)]

        response = client.post(
            "/api/search",
            headers=_headers(),
            json={"query": "Иванов"},
        )

        assert response.status_code == 200
        assert len(response.json()["results"]) == 2
        assert response.json()["has_more"] is True

    def test_search_returns_empty_results(self, api_context):
        _, client, ldap_client = api_context
        ldap_client.search_people.return_value = []

        response = client.post(
            "/api/search",
            headers=_headers(),
            json={"query": "Неизвестный"},
        )

        assert response.status_code == 200
        assert response.json() == {"results": [], "has_more": False}

    @pytest.mark.parametrize("query", ["x", " " * 5, "x" * 151])
    def test_invalid_query_length(self, api_context, query):
        _, client, ldap_client = api_context

        response = client.post(
            "/api/search",
            headers=_headers(),
            json={"query": query},
        )

        assert response.status_code == 422
        assert response.json() == {"detail": "Invalid query"}
        ldap_client.search_people.assert_not_called()

    def test_missing_bearer_token(self, api_context):
        _, client, ldap_client = api_context

        response = client.post("/api/search", json={"query": "Иванов"})

        assert response.status_code == 401
        ldap_client.search_people.assert_not_called()

    def test_invalid_bearer_token(self, api_context):
        _, client, ldap_client = api_context

        response = client.post(
            "/api/search",
            headers=_headers("wrong-token"),
            json={"query": "Иванов"},
        )

        assert response.status_code == 401
        ldap_client.search_people.assert_not_called()

    def test_restricted_query_does_not_reach_ldap(self, api_context):
        _, client, ldap_client = api_context

        response = client.post(
            "/api/search",
            headers=_headers(),
            json={"query": "Потанин"},
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "Access to this query is restricted"}
        ldap_client.search_people.assert_not_called()

    def test_ldap_failure_returns_503(self, api_context):
        _, client, ldap_client = api_context
        ldap_client.search_people.side_effect = RuntimeError("LDAP unavailable")

        response = client.post(
            "/api/search",
            headers=_headers(),
            json={"query": "Иванов"},
        )

        assert response.status_code == 503
        assert response.json() == {
            "detail": "Directory search is temporarily unavailable"
        }

    def test_empty_fields_are_null_and_internal_fields_are_hidden(self, api_context):
        _, client, ldap_client = api_context
        ldap_client.search_people.return_value = [
            _result(
                title=None,
                department=None,
                photo=None,
            )
        ]

        response = client.post(
            "/api/search",
            headers=_headers(),
            json={"query": "Иванов"},
        )

        result = response.json()["results"][0]
        assert result["title"] is None
        assert result["department"] is None
        assert result["photo_url"] is None
        assert "photo" not in result
        assert "object_id" not in result
        assert "object_type" not in result

    def test_photo_url_is_returned_without_base64_photo(self, api_context):
        _, client, ldap_client = api_context
        photo = b"\xff\xd8\xff\xe0 test photo bytes"
        ldap_client.search_people.return_value = [_result(photo=photo)]

        response = client.post(
            "/api/search",
            headers=_headers(),
            json={"query": "Иванов"},
        )

        result = response.json()["results"][0]
        assert "photo" not in result
        assert result["photo_url"].startswith("http://testserver/api/photos/")
        assert "test photo bytes" not in response.text

        photo_response = client.get(result["photo_url"])
        assert photo_response.status_code == 200
        assert photo_response.headers["content-type"] == "image/jpeg"
        assert photo_response.content == photo

    def test_photo_url_is_null_when_photo_is_absent(self, api_context):
        _, client, ldap_client = api_context
        ldap_client.search_people.return_value = [_result(photo=None)]

        response = client.post(
            "/api/search",
            headers=_headers(),
            json={"query": "Иванов"},
        )

        assert response.status_code == 200
        assert response.json()["results"][0]["photo_url"] is None

    def test_missing_photo_token_returns_404(self, api_context):
        _, client, _ = api_context

        response = client.get("/api/photos/missing")

        assert response.status_code == 404

    def test_profile_enrichment_failure_does_not_fail_search(self, api_context):
        api_main, client, ldap_client = api_context
        ldap_client.search_people.return_value = [
            _result(express_chat_url=None)
        ]
        api_main._enrich_results_with_express_links.side_effect = RuntimeError(
            "BotX unavailable"
        )

        response = client.post(
            "/api/search",
            headers=_headers(),
            json={"query": "Иванов"},
        )

        assert response.status_code == 200
        assert response.json()["results"][0]["express_chat_url"] is None

    def test_api_app_does_not_publish_botx_routes(self, api_context):
        _, client, _ = api_context

        assert client.post("/command", json={}).status_code == 404
        assert client.post("/webhook", json={}).status_code == 404


def test_bot_app_does_not_publish_internal_api():
    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/search",
        headers=_headers(),
        json={"query": "Иванов"},
    )

    assert response.status_code == 404


def test_production_api_requires_token(monkeypatch, tmp_path):
    from app import api_main

    monkeypatch.setattr(
        api_main,
        "settings",
        Settings(
            app_env="production",
            internal_api_token="",
            cache_db_path=tmp_path / "cache.sqlite3",
        ),
    )

    with pytest.raises(RuntimeError, match="INTERNAL_API_TOKEN"):
        with TestClient(api_main.app):
            pass
