from app.models import EmployeeCard, SearchResult


def format_search_results(results: list[SearchResult], limit: int) -> str:
    if not results:
        return "Сотрудник не найден. Попробуйте уточнить ФИО."

    lines = ["Найдены сотрудники:"]
    for index, result in enumerate(results[:limit], start=1):
        parts = [result.display_name]
        if result.title:
            parts.append(result.title)
        if result.department:
            parts.append(result.department)
        lines.append(f"{index}. " + " | ".join(parts))

    if len(results) > limit:
        lines.append("Найдено слишком много совпадений. Напишите новый запрос с более полными данными.")

    return "\n".join(lines)


def format_employee_card(card: EmployeeCard) -> str:
    lines = []
    if card.from_cache:
        lines.append("Поиск временно недоступен, показан возможно устаревший результат.")

    lines.append(card.display_name)
    optional_fields = [
        ("Должность", card.title),
        ("Подразделение", card.department),
        ("Рабочий телефон", card.phone),
        ("Мобильный телефон", card.mobile),
        ("Email", card.email),
        ("Кабинет", card.office),
        ("Руководитель", card.manager),
    ]
    for label, value in optional_fields:
        if value:
            lines.append(f"{label}: {value}")

    return "\n".join(lines)

