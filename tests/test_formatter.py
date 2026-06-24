"""Tests for formatter module."""
import pytest
from app.formatter import (
    format_search_results,
    format_search_messages,
    format_search_result_card,
    format_employee_card,
    NOT_FOUND_MESSAGE,
    SEARCH_HEADER,
    TOO_MANY_RESULTS_MESSAGE,
)
from app.models import SearchResult, EmployeeCard


@pytest.fixture
def sample_search_result() -> SearchResult:
    """Create a sample search result."""
    return SearchResult(
        object_id="CN=Test User,OU=Employees",
        display_name="Тестов Тест Тестович",
        title="Инженер",
        department="IT",
        company="Example Corp",
        phone="1234",
        email="test@example.com",
        office="БЯ9",
        room="317",
        birthday="24 июня",
        manager="Руководитель",
        express_chat_url="https://xlnk.ms/chat/abc123",
    )


class TestFormatSearchResults:
    """Test format_search_results function."""

    def test_empty_results_returns_not_found(self):
        """Test empty results return NOT_FOUND_MESSAGE."""
        result = format_search_results([], limit=5)
        assert result == NOT_FOUND_MESSAGE

    def test_single_result(self, sample_search_result):
        """Test formatting single result."""
        result = format_search_results([sample_search_result], limit=5)
        assert SEARCH_HEADER in result
        assert sample_search_result.display_name in result

    def test_multiple_results_without_index(self, sample_search_result):
        """Test multiple results do not include ordinal numbers."""
        second_result = SearchResult(
            object_id="CN=User2",
            display_name="Пользователь Второй",
        )
        result = format_search_results([sample_search_result, second_result], limit=5)

        assert "1. " not in result
        assert "2. " not in result
        assert sample_search_result.display_name in result
        assert "Пользователь Второй" in result

    def test_respects_limit(self, sample_search_result):
        """Test result respects limit parameter."""
        results = [SearchResult(object_id=f"id{i}", display_name=f"User {i}") for i in range(10)]
        result = format_search_results(results, limit=5)

        assert TOO_MANY_RESULTS_MESSAGE in result
        # Should contain 5 users (limited)
        assert result.count("User") == 5

    def test_exact_limit_no_message(self, sample_search_result):
        """Test exact limit doesn't show too many results message."""
        results = [SearchResult(object_id=f"id{i}", display_name=f"User {i}") for i in range(5)]
        result = format_search_results(results, limit=5)

        assert TOO_MANY_RESULTS_MESSAGE not in result


class TestFormatSearchMessages:
    """Test format_search_messages function."""

    def test_empty_returns_not_found_list(self):
        """Test empty results return list with NOT_FOUND_MESSAGE."""
        result = format_search_messages([], limit=5)
        assert result == [NOT_FOUND_MESSAGE]

    def test_returns_list_of_messages(self, sample_search_result):
        """Test returns list with header and cards."""
        result = format_search_messages([sample_search_result], limit=5)

        assert isinstance(result, list)
        assert result[0] == SEARCH_HEADER
        assert any(sample_search_result.display_name in msg for msg in result)

    def test_each_card_is_separate_message(self, sample_search_result):
        """Test each result is separate message."""
        second_result = SearchResult(
            object_id="CN=User2",
            display_name="Второй Пользователь",
        )
        result = format_search_messages([sample_search_result, second_result], limit=5)

        # Should have header + 2 cards = 3 messages
        assert len(result) == 3


class TestFormatSearchResultCard:
    """Test format_search_result_card function."""

    def test_card_ignores_index(self, sample_search_result):
        """Test legacy index argument does not add an ordinal number."""
        result = format_search_result_card(sample_search_result, index=1)
        assert result.startswith(f"**{sample_search_result.display_name}**")
        assert not result.startswith("1. ")

    def test_card_without_index(self, sample_search_result):
        """Test card without index."""
        result = format_search_result_card(sample_search_result)
        assert not result.startswith("1. ")
        assert sample_search_result.display_name in result

    def test_card_hides_empty_fields(self):
        """Test card hides empty optional fields."""
        minimal_result = SearchResult(
            object_id="CN=User",
            display_name="Минимальный Пользователь",
            # No optional fields
        )
        result = format_search_result_card(minimal_result)

        # Should only have name
        lines = result.split("\n")
        assert len(lines) == 1
        assert "Минимальный Пользователь" in lines[0]

    def test_card_shows_express_link(self, sample_search_result):
        """Test card includes express chat link."""
        result = format_search_result_card(sample_search_result)
        assert "Написать в eXpress" in result
        assert sample_search_result.express_chat_url in result

    def test_card_fields_order(self, sample_search_result):
        """Test fields appear in expected order."""
        result = format_search_result_card(sample_search_result)
        lines = result.split("\n")

        # Name should be first
        assert lines[0] == f"**{sample_search_result.display_name}**"

        # Optional fields in order
        field_order = [
            ("Должность", sample_search_result.title),
            ("Подразделение", sample_search_result.department),
            ("Компания", sample_search_result.company),
            ("Внутренний телефон", sample_search_result.phone),
            ("E-mail", sample_search_result.email),
            ("Кабинет", sample_search_result.room),
            ("Офис", sample_search_result.office),
            ("День рождения", sample_search_result.birthday),
            ("Руководитель", sample_search_result.manager),
        ]

        # Check all non-empty fields are present
        for label, value in field_order:
            if value:
                assert f"{label}:**" in result

    def test_card_uses_bold_labels(self, sample_search_result):
        """Test all visible labels are bold."""
        result = format_search_result_card(sample_search_result)

        assert "**Должность:** Инженер" in result
        assert "**Подразделение:** IT" in result
        assert "**Компания:** Example Corp" in result
        assert "**☎️ Внутренний телефон:** 1234" in result
        assert "**✉️ E-mail:** test@example.com" in result
        assert "**🚪 Кабинет:** 317" in result
        assert "**🏢 Офис:** БЯ9" in result
        assert "**🎂 День рождения:** 24 июня" in result
        assert "**👤 Руководитель:** Руководитель" in result
        assert "**💬 Написать в eXpress:**" in result


class TestFormatEmployeeCard:
    """Test format_employee_card function."""

    def test_cached_card_shows_warning(self):
        """Test cached card shows warning message."""
        cached_card = EmployeeCard(
            object_id="CN=User",
            display_name="Cached User",
            from_cache=True,
        )
        result = format_employee_card(cached_card)
        assert "Поиск временно недоступен" in result
        assert "устаревший" in result

    def test_non_cached_card_no_warning(self, sample_search_result):
        """Test non-cached card doesn't show warning."""
        card = EmployeeCard(**{**sample_search_result.__dict__, "from_cache": False})
        result = format_employee_card(card)
        assert "Поиск временно недоступен" not in result


class TestEmojiInFormatting:
    """Test emoji usage in formatted output."""

    def test_phone_has_phone_emoji(self, sample_search_result):
        """Test phone field has phone emoji."""
        result = format_search_result_card(sample_search_result)
        assert "☎️" in result

    def test_email_has_envelope_emoji(self, sample_search_result):
        """Test email field has envelope emoji."""
        result = format_search_result_card(sample_search_result)
        assert "✉️" in result

    def test_room_has_door_emoji(self, sample_search_result):
        """Test room field has door emoji."""
        result = format_search_result_card(sample_search_result)
        assert "🚪" in result

    def test_office_has_building_emoji(self, sample_search_result):
        """Test office field has building emoji."""
        result = format_search_result_card(sample_search_result)
        assert "🏢" in result
