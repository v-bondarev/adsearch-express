import base64
import json
import time
from pathlib import Path

from app.db import connect
from app.models import EmployeeCard


class CardCache:
    def __init__(self, db_path: Path, ttl_seconds: int) -> None:
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds

    def get(self, object_id: str) -> EmployeeCard | None:
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT payload_json, photo, cached_at FROM employee_card_cache WHERE object_id = ?",
                (object_id,),
            ).fetchone()

        if row is None:
            return None

        if int(time.time()) - row["cached_at"] > self.ttl_seconds:
            return None

        payload = json.loads(row["payload_json"])
        if row["photo"] is not None:
            payload["photo"] = base64.b64decode(row["photo"])
        payload["from_cache"] = True
        return EmployeeCard(**payload)

    def set(self, card: EmployeeCard) -> None:
        payload = {
            "object_id": card.object_id,
            "display_name": card.display_name,
            "title": card.title,
            "department": card.department,
            "company": card.company,
            "phone": card.phone,
            "mobile": card.mobile,
            "email": card.email,
            "office": card.office,
            "room": card.room,
            "manager": card.manager,
            "express_chat_url": card.express_chat_url,
            "object_type": card.object_type,
            "from_cache": False,
        }
        photo = base64.b64encode(card.photo) if card.photo else None

        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO employee_card_cache (object_id, payload_json, photo, cached_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(object_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    photo = excluded.photo,
                    cached_at = excluded.cached_at
                """,
                (card.object_id, json.dumps(payload, ensure_ascii=False), photo, int(time.time())),
            )

    def clear(self) -> int:
        with connect(self.db_path) as connection:
            cursor = connection.execute("DELETE FROM employee_card_cache")
            return cursor.rowcount
