from app.models import EmployeeCard, SearchResult

NOT_FOUND_MESSAGE = "Сотрудник не найден. Попробуйте уточнить ФИО."
SEARCH_HEADER = "Найдены сотрудники:"
TOO_MANY_RESULTS_MESSAGE = "Найдено слишком много совпадений. Напишите новый запрос с более полными данными."


def format_search_results(results: list[SearchResult], limit: int) -> str:
    if not results:
        return NOT_FOUND_MESSAGE

    lines = [SEARCH_HEADER]
    for index, result in enumerate(results[:limit], start=1):
        if index > 1:
            lines.append("")
        lines.append(format_search_result_card(result, index=index))

    if len(results) > limit:
        lines.append(TOO_MANY_RESULTS_MESSAGE)

    return "\n".join(lines)


def format_search_messages(results: list[SearchResult], limit: int) -> list[str]:
    if not results:
        return [NOT_FOUND_MESSAGE]

    messages = [SEARCH_HEADER]
    messages.extend(
        format_search_result_card(result, index=index)
        for index, result in enumerate(results[:limit], start=1)
    )

    if len(results) > limit:
        messages.append(TOO_MANY_RESULTS_MESSAGE)

    return messages


def format_search_result_card(result: SearchResult, index: int | None = None) -> str:
    prefix = f"{index}. " if index is not None else ""
    return "\n".join(_format_person_fields(result, prefix=prefix))


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
    ]
    for label, value in optional_fields:
        if value:
            lines.append(f"{label}: {value}")
    if person.express_chat_url:
        lines.append(f"💬 [Написать в eXpress]({person.express_chat_url})")
    return lines
