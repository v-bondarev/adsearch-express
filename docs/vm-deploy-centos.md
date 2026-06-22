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
LDAP_BIND_PASSWORD_FILE=
LDAP_BASE_DN=
LDAP_INCLUDED_OUS=
LDAP_EXCLUDED_OUS=
LDAP_CA_CERT_FILE=
```

3. Пароль bind-пользователя можно хранить одним из способов:

- простой режим: заполнить `LDAP_BIND_PASSWORD` в локальном `.env`;
- предпочтительный режим для VM: положить пароль в отдельный файл и указать путь в `LDAP_BIND_PASSWORD_FILE`.

Пример с отдельным файлом:

```bash
sudo install -d -m 700 /etc/adsearch-express
sudo touch /etc/adsearch-express/ldap_bind_password
sudo chmod 600 /etc/adsearch-express/ldap_bind_password
sudo chown root:root /etc/adsearch-express/ldap_bind_password
sudoedit /etc/adsearch-express/ldap_bind_password
```

В `.env`:

```dotenv
LDAP_BIND_PASSWORD=
LDAP_BIND_PASSWORD_FILE=/etc/adsearch-express/ldap_bind_password
```

Если указан `LDAP_BIND_PASSWORD_FILE`, приложение читает пароль из файла. Сам файл с паролем не коммитится.

4. Если LDAPS требует корпоративный CA-сертификат, положить файл сертификата на VM и указать путь в `LDAP_CA_CERT_FILE`.

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
