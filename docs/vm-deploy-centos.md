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
BOT_ID=
BOT_SECRET_KEY=
BOTX_BASE_URL=
BOTX_PROTO_VERSION=
BOT_ADMIN_HUIDS=

LDAP_HOST=
LDAP_PORT=636
LDAP_USE_SSL=true
LDAP_BIND_USER=
LDAP_BIND_PASSWORD=
LDAP_BASE_DN=
LDAP_INCLUDED_OUS=
LDAP_EXCLUDED_OUS=
LDAP_CA_CERT_FILE=
```

3. Если LDAPS требует корпоративный CA-сертификат, положить файл сертификата на VM и указать путь в `LDAP_CA_CERT_FILE`.

## Запуск через Docker Compose

```bash
docker compose up --build -d
```

Проверка статуса:

```bash
docker compose ps
docker compose logs -f bot
curl http://127.0.0.1:${APP_PORT:-8000}/health
```

Ожидаемый ответ health endpoint:

```json
{"status":"ok"}
```

## Обновление кода на VM

```bash
cd adsearch-express
git pull
docker compose up --build -d
docker compose logs -f bot
```

## Проверка LDAP и webhook

До завершения Этапа 0 нужно подтвердить:

- доступ VM к `LDAP_HOST:LDAP_PORT`;
- корректность bind-пользователя и base DN;
- список included/excluded OU;
- формат входящего webhook express.ms;
- endpoint и формат исходящих сообщений BotX;
- JWT/подпись webhook, если она требуется express.ms.

Тестовые AD-запросы перечислены в [ad-test-queries.md](ad-test-queries.md).
