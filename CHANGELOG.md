# Changelog

Все существенные изменения проекта документируются в этом файле.

## [Unreleased]

### Исправлено

- Удалены неподдерживаемые параметры `pool_name`, `pool_size` и
  `pool_lifetime` из конструктора `ldap3.Server`, из-за которых любой поиск
  завершался ошибкой HTTP 500.
- Добавлен endpoint `GET /status` для служебной проверки бота со стороны
  eXpress.

### Добавлено

- **Тесты** — добавлен полный набор unit-тестов (pytest):
  - `tests/test_config.py` — тесты конфигурации
  - `tests/test_ldap_client.py` — тесты LDAP клиента и фильтров
  - `tests/test_cache.py` — тесты SQLite кэширования
  - `tests/test_formatter.py` — тесты форматирования карточек
  - `tests/test_botx_client.py` — тесты BotX HTTP клиента
  - `tests/test_main.py` — тесты эндпоинтов и обработки команд
  - 123 теста (122 passed, 1 skipped)

- **Повторное использование конфигурации LDAP** — объект `ldap3.Server`
  создаётся один раз, а соединения гарантированно закрываются после запроса.

- **Graceful Shutdown** — при остановке приложения корректно освобождаются:
  - состояние LDAP-клиента (`ldap_client.close_pool()`)
  - HTTP клиент (`await close_http_client()`)

- **HTTP Client Reuse** — `httpx.AsyncClient` создаётся один раз и переиспользуется для всех запросов

### Изменено

- **Совместимость с Python 3.8** — добавлен `from __future__ import annotations` во все модули
- **Обновлён requirements.txt** — добавлены dev-зависимости: `pytest`, `pytest-asyncio`, `pytest-cov`

### Документация

- Обновлён README.md с разделами:
  - Локальная разработка
  - Запуск тестов
  - Структура тестов
  - Архитектура (Connection Pooling, HTTP Client Reuse, Graceful Shutdown)
