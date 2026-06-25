# Интеграция kteam-express с adsearch-express

`kteam-express` работает в Docker, поэтому `localhost` внутри его контейнера не
видит порт `8183` на VM. Для межконтейнерного доступа используется общая
внутренняя Docker-сеть.

## Сеть

Имя сети:

```text
adsearch-internal
```

Создать сеть на VM один раз:

```bash
docker network create adsearch-internal
```

Проверить:

```bash
docker network inspect adsearch-internal
```

## adsearch-express

Сервис `api` подключён к сети `adsearch-internal` с alias:

```text
adsearch-api
```

Для проверок с самой VM остаётся loopback-порт:

```text
http://127.0.0.1:8183
```

Для других контейнеров в сети нужно использовать внутренний адрес:

```text
http://adsearch-api:8000
```

После обновления `adsearch-express`:

```bash
cd /opt/adsearch-express
git pull --ff-only origin main
./scripts/deploy.sh
```

## docker-compose.yml для kteam-express

Добавить подключение к внешней сети:

```yaml
services:
  kteam-express:
    networks:
      - adsearch-internal

networks:
  adsearch-internal:
    external: true
```

Если у `kteam-express` уже есть свои сети, добавить `adsearch-internal` к
списку сетей сервиса, не удаляя существующие.

## .env для kteam-express

```env
ADSEARCH_URL=http://adsearch-api:8000
ADSEARCH_TOKEN=<тот же INTERNAL_API_TOKEN из adsearch-express>
ADSEARCH_TIMEOUT_MS=10000
```

`ADSEARCH_TOKEN` должен совпадать со значением `INTERNAL_API_TOKEN` в
`adsearch-express`.

## HTTP-контракт

Запрос:

```http
POST ${ADSEARCH_URL}/api/search
Authorization: Bearer ${ADSEARCH_TOKEN}
Content-Type: application/json
```

Тело:

```json
{
  "query": "Иванов"
}
```

Успешный ответ:

```json
{
  "results": [
    {
      "display_name": "Иванов Иван Иванович",
      "title": "Инженер",
      "department": "ИТ",
      "company": "Интеррос",
      "phone": "12-34",
      "email": "ivanov@example.ru",
      "office": "БЯ9",
      "room": "317",
      "birthday": "24 июня",
      "manager": "Петров Петр",
      "express_chat_url": "https://xlnk.ms/open/profile/..."
    }
  ],
  "has_more": false
}
```

Поля без значений приходят как `null`. Фотографии, LDAP DN и внутренние
идентификаторы не возвращаются.

## Обработка ответов

- `200` и `results` не пустой: показать карточки сотрудников.
- `200` и `results=[]`: показать `Сотрудник не найден`.
- `200` и `has_more=true`: добавить подсказку уточнить запрос.
- `401`: ошибка конфигурации токена, пользователю показать мягкое сообщение.
- `403`: показать `Доступ к данной информации ограничен`.
- `422`: показать `Введите минимум 2 символа`.
- `503`: показать `Справочник временно недоступен`.
- Timeout/network error: показать временную ошибку без stack trace.

В production-логах `kteam-express` не должен писать ФИО, email и полный JSON
ответа.

## Проверка из контейнера kteam-express

Узнать имя контейнера:

```bash
docker compose ps
```

Проверить health:

```bash
docker compose exec -T kteam-express sh -lc \
  'wget -qO- http://adsearch-api:8000/health'
```

Проверить поиск:

```bash
docker compose exec -T kteam-express sh -lc '
  wget -qO- \
    --header="Authorization: Bearer $ADSEARCH_TOKEN" \
    --header="Content-Type: application/json" \
    --post-data="{\"query\":\"Иванов\"}" \
    "$ADSEARCH_URL/api/search"
'
```

Если в образе нет `wget`, использовать любой доступный HTTP-клиент (`curl`,
Node.js/Python helper и т.п.).

## Тесты для kteam-express

Добавить тесты клиента:

1. успешный поиск;
2. пустой результат;
3. `has_more=true`;
4. `401 Unauthorized`;
5. `403 Forbidden`;
6. `422 Invalid query`;
7. `503 Directory search is temporarily unavailable`;
8. network timeout;
9. отсутствующий `ADSEARCH_TOKEN`;
10. используется `ADSEARCH_URL=http://adsearch-api:8000`, а не localhost.
