# Тестовые запросы к Active Directory

Документ описывает набор проверок для Этапа 0. Цель этапа: подтвердить реальные LDAPS-параметры, LDAP-фильтры, доступные атрибуты и правила исключения лишних объектов до разработки основной логики.

## Проверка через приложение

Основной способ проверки на VM — запуск скрипта, который использует те же `.env`-параметры, что и приложение:

```bash
cd /opt/adsearch-express
docker compose run --rm bot python scripts/ldap_test_queries.py --query "<ФИО или часть фамилии>"
```

Скрипт использует:

- `LDAP_HOST`, `LDAP_PORT`, `LDAP_USE_SSL`;
- `LDAP_BIND_USER`;
- `LDAP_BIND_PASSWORD` или `LDAP_BIND_PASSWORD_FILE`;
- `LDAP_BASE_DN`;
- `LDAP_INCLUDED_OUS`;
- `LDAP_EXCLUDED_OUS`;
- `LDAP_CA_CERT_FILE`;
- `LDAP_CONNECT_TIMEOUT_SECONDS`;
- `LDAP_READ_TIMEOUT_SECONDS`.

Проверка только bind и базового поиска:

```bash
docker compose run --rm bot python scripts/ldap_test_queries.py
```

Если `LDAP_BASE_DN` и `LDAP_INCLUDED_OUS` еще неизвестны, скрипт сначала читает RootDSE и использует `defaultNamingContext` как временную базу поиска. Значение `defaultNamingContext` обычно и есть базовый DN домена, например `DC=example,DC=local`.

Вывести OU-кандидаты:

```bash
docker compose run --rm bot python scripts/ldap_test_queries.py --list-ous --limit 30
```

После этого можно зафиксировать в `.env`:

```dotenv
LDAP_BASE_DN=DC=example,DC=local
LDAP_INCLUDED_OUS=OU=Users,DC=example,DC=local;OU=Contacts,DC=example,DC=local
```

Для текущего домена `hci.interros.ru`, если искать нужно во всех вложенных контейнерах внутри `HCI` и `HCI_Users`, достаточно указать эти две стартовые базы. Скрипт и приложение используют subtree-поиск:

```dotenv
LDAP_BASE_DN=DC=hci,DC=interros,DC=ru
LDAP_INCLUDED_OUS=OU=HCI,DC=hci,DC=interros,DC=ru;OU=HCI_Users,DC=hci,DC=interros,DC=ru
```

Проверка конкретного LDAP-фильтра:

```bash
docker compose run --rm bot python scripts/ldap_test_queries.py \
  --filter "(&(objectClass=user)(objectCategory=person)(cn=<ФИО>))"
```

Получение всех доступных атрибутов:

```bash
docker compose run --rm bot python scripts/ldap_test_queries.py \
  --query "<ФИО>" \
  --all-attributes
```

Если сотрудник точно есть, но поиск не находит его, проверьте широкое совпадение по основным name/email/account-полям:

```bash
docker compose run --rm bot python scripts/ldap_test_queries.py \
  --query "Иванова" \
  --all-attributes \
  --limit 10
```

Скрипт не печатает пароль bind-пользователя. Бинарные атрибуты `objectGUID`, `thumbnailPhoto` и `jpegPhoto` выводятся только как краткое описание размера.

### Подтвержденные атрибуты HCI

По тестовому поиску `Иванова` подтверждено:

- `displayName`, `cn`, `name` содержат русское ФИО.
- У части users `sn` и `givenName` заполнены латиницей, например `Ivanova`/`Ekaterina`.
- Для users в `HCI_Users` русские части ФИО встречаются в Exchange extension attributes:
  `extensionAttribute1` — фамилия, `extensionAttribute2` — имя, `extensionAttribute3` — отчество.
- `title`, `department`, `company`, `mail`, `telephoneNumber`, `mobile`, `physicalDeliveryOfficeName`, `manager` подходят для карточки.
- ФИО в карточке берем из `cn`. Если в `cn` есть суффикс в скобках, скобки убираются из ФИО.
- Если `company` пустая, компания берется из суффикса в скобках у `cn`.
- `manager` хранится DN-строкой, в карточку выводится только CN руководителя.
- `physicalDeliveryOfficeName` разбивается на офис и кабинет: `БЯ-9\317` -> офис `БЯ9`, кабинет `317`.
- `thumbnailPhoto` может содержать фото пользователя.
- Отключенных users можно исключать через `userAccountControl:1.2.840.113556.1.4.803:=2`.

### Частые ошибки

Если скрипт пишет `LDAP password contains ASCII control characters` или `SASLprep error: ASCII control character present`, в файле пароля есть невидимый управляющий символ. Перезапишите файл одной строкой:

```bash
sudoedit /etc/adsearch-express/ldap_bind_password
```

В файле должен быть только пароль, без пустых строк до/после и без вставленных управляющих символов. Обычный перевод строки в конце файла допустим: приложение его срезает.

Если в summary видно `base_dn:` пустой и `included_ous: <none>`, скрипт попробует взять `defaultNamingContext` из RootDSE. После discovery лучше заполнить в `.env` минимум один из параметров:

```dotenv
LDAP_BASE_DN=DC=example,DC=local
LDAP_INCLUDED_OUS=OU=Users,DC=example,DC=local
```

Команды ниже не содержат секретов. Значения в угловых скобках нужно заменить на реальные параметры окружения.

## Переменные

```bash
export LDAP_URI="ldaps://<ldap-host>:636"
export LDAP_BASE_DN="<base-dn>"
export LDAP_BIND_DN="<bind-user>"
export LDAP_CA_CERT_FILE="<path-to-ca.pem>"
```

Пароль bind-пользователя лучше вводить интерактивно, без сохранения в истории shell:

```bash
read -s LDAP_BIND_PASSWORD
```

## Проверка LDAPS bind

```bash
LDAPTLS_CACERT="$LDAP_CA_CERT_FILE" ldapwhoami \
  -H "$LDAP_URI" \
  -D "$LDAP_BIND_DN" \
  -w "$LDAP_BIND_PASSWORD"
```

Ожидаемый результат: успешный bind без TLS-ошибок.

## Получение RootDSE

```bash
LDAPTLS_CACERT="$LDAP_CA_CERT_FILE" ldapsearch \
  -LLL \
  -H "$LDAP_URI" \
  -D "$LDAP_BIND_DN" \
  -w "$LDAP_BIND_PASSWORD" \
  -b "" \
  -s base \
  "(objectClass=*)" \
  defaultNamingContext namingContexts supportedLDAPVersion
```

Цель: подтвердить доступность сервера и базовые naming contexts.

## Получение всех атрибутов тестового пользователя

```bash
LDAPTLS_CACERT="$LDAP_CA_CERT_FILE" ldapsearch \
  -LLL \
  -H "$LDAP_URI" \
  -D "$LDAP_BIND_DN" \
  -w "$LDAP_BIND_PASSWORD" \
  -b "$LDAP_BASE_DN" \
  "(&(objectClass=user)(objectCategory=person)(cn=<ФИО тестового пользователя>))" \
  "*" "+"
```

Цель: определить реальные атрибуты для карточки сотрудника: ФИО, должность, подразделение, телефоны, email, кабинет, руководитель, фото.

## Получение всех атрибутов тестового контакта

```bash
LDAPTLS_CACERT="$LDAP_CA_CERT_FILE" ldapsearch \
  -LLL \
  -H "$LDAP_URI" \
  -D "$LDAP_BIND_DN" \
  -w "$LDAP_BIND_PASSWORD" \
  -b "$LDAP_BASE_DN" \
  "(&(objectClass=contact)(cn=<ФИО тестового контакта>))" \
  "*" "+"
```

Цель: сравнить набор атрибутов user и contact.

## Предварительный поиск по точному ФИО

```bash
LDAPTLS_CACERT="$LDAP_CA_CERT_FILE" ldapsearch \
  -LLL \
  -H "$LDAP_URI" \
  -D "$LDAP_BIND_DN" \
  -w "$LDAP_BIND_PASSWORD" \
  -b "$LDAP_BASE_DN" \
  "(|(&(objectClass=user)(objectCategory=person)(displayName=<ФИО>))(&(objectClass=contact)(displayName=<ФИО>)))" \
  distinguishedName objectGUID displayName title department mail telephoneNumber mobile physicalDeliveryOfficeName manager thumbnailPhoto
```

Цель: проверить, достаточно ли `displayName` для точного совпадения.

## Предварительный поиск по фамилии и имени

```bash
LDAPTLS_CACERT="$LDAP_CA_CERT_FILE" ldapsearch \
  -LLL \
  -H "$LDAP_URI" \
  -D "$LDAP_BIND_DN" \
  -w "$LDAP_BIND_PASSWORD" \
  -b "$LDAP_BASE_DN" \
  "(|(&(objectClass=user)(objectCategory=person)(sn=<Фамилия>)(givenName=<Имя>))(&(objectClass=contact)(sn=<Фамилия>)(givenName=<Имя>)))" \
  distinguishedName objectGUID displayName title department mail telephoneNumber mobile physicalDeliveryOfficeName manager
```

Цель: проверить атрибуты `sn` и `givenName` для поиска ФИ.

## Предварительный поиск по имени и отчеству

```bash
LDAPTLS_CACERT="$LDAP_CA_CERT_FILE" ldapsearch \
  -LLL \
  -H "$LDAP_URI" \
  -D "$LDAP_BIND_DN" \
  -w "$LDAP_BIND_PASSWORD" \
  -b "$LDAP_BASE_DN" \
  "(|(&(objectClass=user)(objectCategory=person)(givenName=<Имя>)(middleName=<Отчество>))(&(objectClass=contact)(givenName=<Имя>)(middleName=<Отчество>)))" \
  distinguishedName objectGUID displayName title department mail telephoneNumber mobile physicalDeliveryOfficeName manager
```

Цель: проверить, есть ли в AD атрибут отчества и как он называется. Если `middleName` не используется, нужно найти фактический атрибут в полной выборке.

## Предварительный поиск по части фамилии

```bash
LDAPTLS_CACERT="$LDAP_CA_CERT_FILE" ldapsearch \
  -LLL \
  -H "$LDAP_URI" \
  -D "$LDAP_BIND_DN" \
  -w "$LDAP_BIND_PASSWORD" \
  -b "$LDAP_BASE_DN" \
  "(|(&(objectClass=user)(objectCategory=person)(sn=<ЧастьФамилии>*))(&(objectClass=contact)(sn=<ЧастьФамилии>*)))" \
  distinguishedName objectGUID displayName title department mail telephoneNumber mobile physicalDeliveryOfficeName manager
```

Цель: проверить частичный поиск по фамилии и количество совпадений.

## Проверка исключения отключенных пользователей

```bash
LDAPTLS_CACERT="$LDAP_CA_CERT_FILE" ldapsearch \
  -LLL \
  -H "$LDAP_URI" \
  -D "$LDAP_BIND_DN" \
  -w "$LDAP_BIND_PASSWORD" \
  -b "$LDAP_BASE_DN" \
  "(&(objectClass=user)(objectCategory=person)(userAccountControl:1.2.840.113556.1.4.803:=2))" \
  distinguishedName displayName userAccountControl
```

Цель: подтвердить, что отключенные учетные записи можно исключать через `userAccountControl`.

## Проверка фото

```bash
LDAPTLS_CACERT="$LDAP_CA_CERT_FILE" ldapsearch \
  -LLL \
  -H "$LDAP_URI" \
  -D "$LDAP_BIND_DN" \
  -w "$LDAP_BIND_PASSWORD" \
  -b "$LDAP_BASE_DN" \
  "(&(objectClass=user)(objectCategory=person)(cn=<ФИО тестового пользователя>))" \
  thumbnailPhoto jpegPhoto
```

Цель: определить, какой атрибут содержит фото и в каком объеме приходят данные.

## Что нужно зафиксировать после тестов

- Рабочий LDAPS URI.
- Base DN и scope поиска.
- OU, которые нужно включать и исключать.
- Финальные фильтры для user и contact.
- Атрибуты для ФИО, должности, подразделения, телефонов, email, кабинета, руководителя и фото.
- Правила исключения отключенных, сервисных, технических и скрытых объектов.
- Максимальный размер фото и необходимость ресайза перед отправкой в express.ms.
