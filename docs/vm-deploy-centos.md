# Запуск на CentOS VM

Рабочая версия запускается на CentOS VM, у которой есть доступ к корпоративной сети, LDAPS и express.ms/BotX. Mac используется для разработки и подготовки изменений.

## Доступ к GitHub

На VM git работает через HTTPS с API-ключом/GitHub token.

Рекомендуемый вариант без токена в истории shell:

```bash
git clone https://github.com/v-bondarev/adsearch-express.git
cd adsearch-express
git config credential.helper store
git pull
```

При запросе учетных данных:

- username: `v-bondarev`
- password: API-ключ/GitHub token

После успешной аутентификации git сохранит credentials для следующих `git pull` и `git push`.

Если нужно выполнить одноразовое клонирование без сохранения credentials, можно использовать URL с токеном:

```bash
git clone https://<TOKEN>@github.com/v-bondarev/adsearch-express.git
```

Не сохранять такой URL в документации, скриптах и скриншотах.

## Подготовка окружения

1. Создать `.env` из шаблона:

```bash
cp .env.example .env
```

2. Заполнить реальные значения:

```dotenv
APP_UID=1000
APP_GID=1000

BOT_ID=
BOT_SECRET_KEY=
BOTX_BASE_URL=
BOTX_PROTOCOL_VERSION=4
BOT_ADMIN_HUIDS=

LDAP_HOST=
LDAP_PORT=636
LDAP_USE_SSL=true
LDAP_BIND_USER=
LDAP_BIND_PASSWORD=
LDAP_BIND_PASSWORD_FILE=/run/secrets/ldap_bind_password
LDAP_BIND_PASSWORD_FILE_HOST=/etc/adsearch-express/ldap_bind_password
LDAP_BASE_DN=
LDAP_INCLUDED_OUS=
LDAP_EXCLUDED_OUS=
LDAP_CA_CERT_FILE=
```

3. Пароль bind-пользователя можно хранить одним из способов:

- простой режим: заполнить `LDAP_BIND_PASSWORD` в локальном `.env`;
- предпочтительный режим для VM: положить пароль в отдельный файл на VM и смонтировать его read-only в контейнер.

Если контейнер запускается под пользователем `vbondarev`, задайте в `.env` UID/GID этого пользователя на VM:

```bash
id -u vbondarev
id -g vbondarev
```

Пример с отдельным файлом на VM:

```bash
sudo install -d -m 700 /etc/adsearch-express
sudo touch /etc/adsearch-express/ldap_bind_password
sudo chown vbondarev:vbondarev /etc/adsearch-express/ldap_bind_password
sudo chmod 600 /etc/adsearch-express/ldap_bind_password
sudoedit /etc/adsearch-express/ldap_bind_password
```

В `.env`:

```dotenv
APP_UID=1000
APP_GID=1000
INTERNAL_API_PORT=8183
INTERNAL_API_TOKEN=<длинный случайный токен>
LDAP_BIND_PASSWORD=
LDAP_BIND_PASSWORD_FILE=/run/secrets/ldap_bind_password
LDAP_BIND_PASSWORD_FILE_HOST=/etc/adsearch-express/ldap_bind_password
```

`LDAP_BIND_PASSWORD_FILE_HOST` используется Docker Compose для read-only mount с VM. `LDAP_BIND_PASSWORD_FILE` указывает путь уже внутри контейнера. Сам файл с паролем не коммитится.

4. Если LDAPS требует корпоративный CA-сертификат, положить файл сертификата на VM и указать путь в `LDAP_CA_CERT_FILE`.

## Запуск через Docker Compose

```bash
docker compose up --build -d
```

Compose запускает существующий BotX-сервис `bot` на порту `8181` и внутренний
сервис `api` на `127.0.0.1:8183`. Порт API недоступен с других машин. В
production значение `INTERNAL_API_TOKEN` обязательно.

Токен можно сгенерировать командой `openssl rand -hex 32`.

Проверка статуса:

```bash
docker compose ps
docker compose logs -f bot
curl http://127.0.0.1:${APP_PORT:-8181}/health
curl http://127.0.0.1:${INTERNAL_API_PORT:-8183}/health
```

Ожидаемый ответ health endpoint:

```json
{"status":"ok"}
```

## Обновление кода на VM

```bash
cd adsearch-express
./scripts/deploy.sh
```

Скрипт получает `main` через `git pull --ff-only`, использует Docker layer
cache и собирает новый образ до замены работающих контейнеров. После запуска он
проверяет `/health` внутри `bot` и `api` каждую секунду и завершается после
готовности обоих приложений. При ошибке выводятся последние 100 строк логов.

Слой Python-зависимостей пересобирается только при изменении
`requirements.txt` или базового образа. Изменения файлов приложения не запускают
повторную установку всех пакетов.

Таймаут ожидания по умолчанию — 30 секунд:

```bash
DEPLOY_HEALTH_TIMEOUT=60 ./scripts/deploy.sh
```

## Проверка LDAP и webhook

До завершения Этапа 0 нужно подтвердить:

- доступ VM к `LDAP_HOST:LDAP_PORT`;
- корректность bind-пользователя и base DN;
- список included/excluded OU;
- формат входящего webhook express.ms: `command.body`, `from.group_chat_id`, `from.host`, `from.user_huid`;
- endpoint исходящих сообщений BotX: `/api/v4/botx/notifications/direct/sync`;
- авторизацию исходящих сообщений старым JWT-токеном: HS256, `iss=BOT_ID`, `aud=host`, `version=2`.

Тестовые AD-запросы перечислены в [ad-test-queries.md](ad-test-queries.md).
