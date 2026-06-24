# adsearch-express

Бот корпоративного справочника для express.ms.

Бот ищет пользователей и контакты в Active Directory через LDAPS по ФИО или фамилии и отправляет найденных сотрудников отдельными карточками в чат express.ms.

## Возможности

- При первом открытии, `/start`, `start`, `старт`, `/help`, `help` или `помощь` бот показывает памятку: `Для поиска введите ФИО или просто фамилию`.
- Поиск по ФИО, имени, фамилии и части фамилии.
- Поиск ограничен полями имени в AD, чтобы не находить сотрудников по компании, описанию, почте или логину.
- В выдачу попадают только записи с заполненными компанией и e-mail.
- Поиск выполняется по пользователям и контактам внутри настроенных LDAP OU с учетом вложенных контейнеров.
- Выдача до 5 результатов с предложением уточнить запрос при большом количестве совпадений.
- Бот отправляет заголовок `Найдены сотрудники:`, затем отдельное сообщение-карточку для каждого сотрудника.
- Карточки выводятся без порядковых номеров; ФИО и названия полей выделяются жирным.
- Если в AD заполнен `thumbnailPhoto`, фотография отправляется вместе с карточкой, а текст визуально отделяется пустой строкой.
- Карточка сотрудника содержит доступные данные из AD: ФИО, должность, подразделение, компанию, внутренний телефон, e-mail, кабинет, офис, руководителя и ссылку на профиль в eXpress, если она есть.
- Пустые поля в карточке скрываются.
- ФИО берется из `cn`; компания берется из `company`, а если оно пустое, из скобок в `cn`.
- Кабинет и офис берутся из `physicalDeliveryOfficeName`: например `БЯ-9\317` превращается в офис `БЯ9` и кабинет `317`.
- Карточки могут кешироваться в SQLite на 24 часа.
- Административная команда `/clear_cache` очищает весь кеш.
- Доступ обычных пользователей ограничивается средствами express.ms.
- Production-логи не содержат текст поисковых запросов и персональные данные.

## Стек

- Python 3.8+
- FastAPI
- ldap3
- httpx (с переиспользованием соединений)
- SQLite
- Docker Compose
- pytest

## Документы

- [Техническое задание](docs/technical-spec.md)
- [Данные и доступы для Этапа 0](docs/stage-0-inputs.md)
- [Тестовые запросы к Active Directory](docs/ad-test-queries.md)
- [Запуск на CentOS VM](docs/vm-deploy-centos.md)

## Локальный запуск

1. Создать `.env` на основе `.env.example`.
2. Для LDAPS-пароля можно использовать переменную `LDAP_BIND_PASSWORD` или файл-секрет:

```env
LDAP_BIND_PASSWORD_FILE=/run/secrets/ldap_bind_password
LDAP_BIND_PASSWORD_FILE_HOST=/etc/adsearch-express/ldap_bind_password
```

3. Запустить приложение:

```bash
docker compose up --build
```

4. Проверить health endpoint:

```bash
curl http://127.0.0.1:${APP_PORT:-8181}/health
```

Webhook express.ms обрабатывается на `/command` и совместимом `/webhook`.
Endpoint сразу подтверждает получение команды, а LDAP-поиск и отправка
карточек выполняются в фоне. Служебная проверка eXpress доступна на `/status`.
Для исходящих сообщений используется BotX API v4 endpoint
`/api/v4/botx/notifications/direct/sync` и старый JWT-токен бота.

## Локальная разработка

### Установка зависимостей

```bash
# Основные зависимости
pip install -r requirements.txt

# Dev-зависимости (тесты)
pip install pytest pytest-asyncio pytest-cov
```

### Запуск тестов

```bash
# Все тесты
pytest tests/ -v

# С покрытием
pytest tests/ -v --cov=app --cov-report=html

# Один файл тестов
pytest tests/test_ldap_client.py -v
```

### Структура тестов

- `tests/test_config.py` — тесты конфигурации
- `tests/test_ldap_client.py` — тесты LDAP клиента и фильтров
- `tests/test_cache.py` — тесты кэширования
- `tests/test_formatter.py` — тесты форматирования карточек
- `tests/test_botx_client.py` — тесты BotX HTTP клиента
- `tests/test_main.py` — тесты эндпоинтов и обработки команд

## Пример `.env` для AD

```env
APP_PORT=8181

BOT_ID=<uuid бота>
BOT_SECRET_KEY=<secret_key бота>
BOTX_PROTOCOL_VERSION=4
BOTX_BASE_URL=<адрес CTS/BotX>
BOTX_PROFILE_URL_TEMPLATE=https://xlnk.ms/open/profile/{user_huid}

LDAP_HOST=10.0.0.10
LDAP_PORT=636
LDAP_USE_SSL=true
LDAP_BIND_USER=svc_directory_bot
LDAP_BIND_PASSWORD_FILE=/run/secrets/ldap_bind_password
LDAP_BIND_PASSWORD_FILE_HOST=/etc/adsearch-express/ldap_bind_password
LDAP_BASE_DN=DC=example,DC=local
LDAP_INCLUDED_OUS=OU=Employees,DC=example,DC=local;OU=Contacts,DC=example,DC=local
LDAP_EXCLUDED_OUS=
```

`LDAP_INCLUDED_OUS` задает верхние OU для поиска. Вложенные контейнеры внутри этих OU перечислять не нужно: поиск идет рекурсивно.

## Обновление на VM

```bash
cd /opt/adsearch-express
git pull
docker compose up --build -d
```

## Архитектура

### LDAP Connections

LDAP-клиент повторно использует конфигурацию сервера. Для каждого запроса
создаётся отдельное соединение, которое гарантированно закрывается после
завершения операции.

### Асинхронная обработка команд

`/command` и `/webhook` сразу возвращают успешный ответ. Синхронный LDAP-поиск
выполняется в отдельном worker thread, а запросы ссылок на профили eXpress
запускаются параллельно. Это не блокирует event loop и не заставляет eXpress
ждать завершения всей выдачи.

### HTTP Client Reuse

HTTP клиент (`httpx.AsyncClient`) создаётся один раз и переиспользуется для всех BotX API запросов, что снижает накладные расходы на установку TLS-соединений.

### Graceful Shutdown

При остановке приложения корректно закрываются:
- состояние LDAP-клиента
- HTTP клиент

## Репозиторий

https://github.com/v-bondarev/adsearch-express.git
