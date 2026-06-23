#!/usr/bin/env sh
set -eu

ENV_FILE="${1:-.env}"
KEY="BOTX_PROFILE_URL_TEMPLATE"
VALUE="https://xlnk.ms/open/profile/{user_huid}"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

DIRNAME=$(dirname "$ENV_FILE")
BASENAME=$(basename "$ENV_FILE")
TMP_FILE=$(mktemp "${DIRNAME}/.${BASENAME}.tmp.XXXXXX")
BACKUP_FILE=$(mktemp "${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S).XXXXXX")

cp "$ENV_FILE" "$BACKUP_FILE"

if grep -Eq "^[[:space:]]*${KEY}=" "$ENV_FILE"; then
  awk -v key="$KEY" -v value="$VALUE" '
    $0 ~ "^[[:space:]]*" key "=" {
      print key "=" value
      next
    }
    { print }
  ' "$ENV_FILE" > "$TMP_FILE"
else
  awk -v key="$KEY" -v value="$VALUE" '
    BEGIN { inserted = 0 }
    {
      print
      if (!inserted && $0 ~ "^[[:space:]]*BOTX_PROTOCOL_VERSION=") {
        print key "=" value
        inserted = 1
      }
    }
    END {
      if (!inserted) {
        print key "=" value
      }
    }
  ' "$ENV_FILE" > "$TMP_FILE"
fi

chmod --reference="$ENV_FILE" "$TMP_FILE" 2>/dev/null || chmod 600 "$TMP_FILE"
mv "$TMP_FILE" "$ENV_FILE"

echo "Updated $ENV_FILE"
echo "Backup: $BACKUP_FILE"
