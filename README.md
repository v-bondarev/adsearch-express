# adsearch-express

Бот корпоративного справочника для express.ms.

Бот ищет пользователей и контакты в Active Directory через LDAPS по ФИО или фамилии и отправляет найденных сотрудников отдельными карточками в чат express.ms.
В проект также входит локальный внутренний API для других сервисов на той же VM.

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
- Карточка сотрудника содержит доступные данные из AD: ФИО, должность, подразделение, компанию, внутренний телефон, e-mail, кабинет, офис, день рождения, руководителя и ссылку на профиль в eXpress, если она есть.
- Пустые поля в карточке скрываются.
- ФИО берется из `cn`; компания берется из `company`, а если оно пустое, из скобок в `cn`.
- Кабинет и офис берутся из `physicalDeliveryOfficeName`: например `БЯ-9\317` превращается в офис `БЯ9` и кабинет `317`.
- День рождения берётся из `extensionAttribute5` и выводится как `📅 День рождения: 24 июня`, без года. Если дата совпадает с текущим днём, перед датой показывается `🎂`.
- Карточки могут кешироваться в SQLite на 24 часа.
- Административная команда `/clear_cache` очищает весь кеш.
- Доступ обычных пользователей ограничивается средствами express.ms.
- Production-логи не содержат текст поисковых запросов и персональные данные.
- Внутренний API возвращает структурированные результаты без фотографий, LDAP DN и других внутренних идентификаторов.

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
- [Интеграция kteam-express с внутренним API](docs/kteam-express-adsearch-integration.md)

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

## Внутренний API

API запускается отдельным контейнером и публикуется только на loopback VM:

```text
http://127.0.0.1:8183/api/search
```

BotX-сервис и его порт `8181` не изменяются. API-контейнер публикует только
`GET /health` и `POST /api/search`; BotX endpoints через порт `8183`
недоступны.

Для доступа из других Docker-контейнеров API подключается к внешней сети
`adsearch-internal` с DNS alias `adsearch-api`. Внутренний адрес для контейнеров:

```text
http://adsearch-api:8000
```

Сеть создаётся на VM один раз:

```bash
docker network create --driver bridge --subnet 192.168.240.0/24 adsearch-internal
```

`scripts/deploy.sh` также создаёт эту сеть автоматически, если её ещё нет. Если
сеть уже была создана Docker с конфликтующей подсетью, например из реального
диапазона `172.23.0.0/16`, её нужно пересоздать:

```bash
docker compose down
docker network rm adsearch-internal
docker network create --driver bridge --subnet 192.168.240.0/24 adsearch-internal
./scripts/deploy.sh
```

Для доступа требуется Bearer-токен из `INTERNAL_API_TOKEN`. В production
API-контейнер не запускается с пустым токеном.

Сгенерировать токен можно на VM:

```bash
openssl rand -hex 32
```

```bash
curl -sS http://127.0.0.1:8183/api/search \
  -H "Authorization: Bearer $INTERNAL_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"Иванов"}'
```

Пример ответа:

```json
{
  "results": [
    {
      "display_name": "Иванов Иван Иванович",
      "title": "Инженер",
      "department": "ИТ",
      "company": "Пример",
      "phone": "12-34",
      "email": "ivanov@example.ru",
      "office": "БЯ9",
      "room": "317",
      "birthday": "24 июня",
      "manager": "Петров Петр",
      "express_chat_url": "https://xlnk.ms/open/profile/example"
    }
  ],
  "has_more": false
}
```

API возвращает не более `SEARCH_LIMIT` записей. Если совпадений больше,
`has_more` равен `true`. Пустые поля возвращаются как `null`. Запрещённые
запросы отклоняются до обращения к LDAP.

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
INTERNAL_API_PORT=8183
INTERNAL_API_TOKEN=<длинный случайный токен>

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
./scripts/deploy.sh
```

Скрипт выполняет fast-forward обновление из `origin/main`, собирает новый образ
с использованием Docker layer cache и обновляет контейнеры `bot` и `api`.
Старые контейнеры работают во время сборки, поэтому недоступность ограничивается
моментом их замены. Скрипт опрашивает `/health` внутри каждого контейнера и
завершается, когда оба приложения начинают отвечать.

Python-пакеты находятся в отдельном слое Dockerfile и устанавливаются повторно
только при изменении `requirements.txt` или базового образа. Обычные изменения
кода пересобирают только лёгкий слой приложения.

По умолчанию healthcheck ожидается до 30 секунд. Таймаут можно изменить:

```bash
DEPLOY_HEALTH_TIMEOUT=60 ./scripts/deploy.sh
```

Проверка `/health` внутри контейнеров принудительно обходит HTTP proxy, поэтому
корпоративные proxy-переменные не должны влиять на localhost-запросы.

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
