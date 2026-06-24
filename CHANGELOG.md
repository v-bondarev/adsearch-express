# Changelog

Все существенные изменения проекта документируются в этом файле.

## [Unreleased]

### Добавлено

- **Тесты** — добавлен полный набор unit-тестов (pytest):
  - `tests/test_config.py` — тесты конфигурации
  - `tests/test_ldap_client.py` — тесты LDAP клиента и фильтров
  - `tests/test_cache.py` — тесты SQLite кэширования
  - `tests/test_formatter.py` — тесты форматирования карточек
  - `tests/test_botx_client.py` — тесты BotX HTTP клиента
  - `tests/test_main.py` — тесты эндпоинтов и обработки команд
  - 123 теста (122 passed, 1 skipped)

- **Connection Pooling для LDAP** — сервер LDAP создаётся с пулом соединений:
  - `pool_name="adsearch_pool"`
  - `pool_size=5`
  - `pool_lifetime=3600`

- **Graceful Shutdown** — при остановке приложения корректно закрываются:
  - LDAP connection pool (`ldap_client.close_pool()`)
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
