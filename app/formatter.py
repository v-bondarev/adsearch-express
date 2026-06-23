from app.models import EmployeeCard, SearchResult


def format_search_results(results: list[SearchResult], limit: int) -> str:
    if not results:
        return "Сотрудник не найден. Попробуйте уточнить ФИО."

    lines = ["Найдены сотрудники:"]
    for index, result in enumerate(results[:limit], start=1):
        if index > 1:
            lines.append("")
        lines.extend(_format_person_fields(result, prefix=f"{index}. "))

    if len(results) > limit:
        lines.append("Найдено слишком много совпадений. Напишите новый запрос с более полными данными.")

    return "\n".join(lines)


def format_employee_card(card: EmployeeCard) -> str:
    lines = []
    if card.from_cache:
        lines.append("Поиск временно недоступен, показан возможно устаревший результат.")

    lines.extend(_format_person_fields(card))

    return "\n".join(lines)


def _format_person_fields(person: SearchResult | EmployeeCard, prefix: str = "") -> list[str]:
    lines = [f"{prefix}{person.display_name}"]
    optional_fields = [
        ("Должность", person.title),
        ("Подразделение", person.department),
        ("Компания", person.company),
        ("☎️ Внутренний телефон", person.phone),
        ("✉️ E-mail", person.email),
        ("🚪 Кабинет", person.room),
        ("🏢 Офис", person.office),
        ("👤 Руководитель", person.manager),
        ("💬 Ссылка на чат в eXpress", person.express_chat_url),
    ]
    for label, value in optional_fields:
        if value:
            lines.append(f"{label}: {value}")
    return lines
