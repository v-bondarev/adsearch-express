from __future__ import annotations

from datetime import date
from typing import List, Optional, Union

from app.models import EmployeeCard, SearchResult

NOT_FOUND_MESSAGE = "Сотрудник не найден. Попробуйте уточнить ФИО."
SEARCH_HEADER = "Найдены сотрудники:"
TOO_MANY_RESULTS_MESSAGE = "Найдено слишком много совпадений. Напишите новый запрос с более полными данными."
MONTH_NUMBERS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


def format_search_results(results: List[SearchResult], limit: int) -> str:
    if not results:
        return NOT_FOUND_MESSAGE

    lines = [SEARCH_HEADER]
    for index, result in enumerate(results[:limit]):
        if index:
            lines.append("")
        lines.append(format_search_result_card(result))

    if len(results) > limit:
        lines.append(TOO_MANY_RESULTS_MESSAGE)

    return "\n".join(lines)


def format_search_messages(results: List[SearchResult], limit: int) -> List[str]:
    if not results:
        return [NOT_FOUND_MESSAGE]

    messages = [SEARCH_HEADER]
    messages.extend(format_search_result_card(result) for result in results[:limit])

    if len(results) > limit:
        messages.append(TOO_MANY_RESULTS_MESSAGE)

    return messages


def format_search_result_card(result: SearchResult, index: Optional[int] = None) -> str:
    return "\n".join(_format_person_fields(result))


def format_employee_card(card: EmployeeCard) -> str:
    lines = []
    if card.from_cache:
        lines.append("Поиск временно недоступен, показан возможно устаревший результат.")

    lines.extend(_format_person_fields(card))

    return "\n".join(lines)


def _format_person_fields(person: Union[SearchResult, EmployeeCard]) -> List[str]:
    lines = [f"**{person.display_name}**"]
    optional_fields = [
        ("Должность", person.title),
        ("Подразделение", person.department),
        ("Компания", person.company),
        ("☎️ Внутренний телефон", person.phone),
        ("✉️ E-mail", person.email),
        ("🚪 Кабинет", person.room),
        ("🏢 Офис", person.office),
        ("📅 День рождения", _birthday_with_celebration(person.birthday)),
        ("👤 Руководитель", person.manager),
    ]
    for label, value in optional_fields:
        if value:
            lines.append(f"**{label}:** {value}")
    if person.express_chat_url:
        lines.append(f"**💬 Написать в eXpress:** {person.express_chat_url}")
    return lines


def _birthday_with_celebration(
    birthday: Optional[str],
    today: Optional[date] = None,
) -> Optional[str]:
    if not birthday:
        return None

    parts = birthday.split()
    if len(parts) != 2:
        return birthday

    try:
        day = int(parts[0])
    except ValueError:
        return birthday

    month = MONTH_NUMBERS.get(parts[1].casefold())
    current_date = today or date.today()
    if month == current_date.month and day == current_date.day:
        return f"🎂 {birthday}"
    return birthday
