"""Lectura y escritura del asistente. Inserciones dirigidas: no reescribe la cuenta.

FileStore guarda estas listas en el JSON. SupabaseStore usa las tablas de la migración 0009.
"""

from datetime import UTC, datetime

_FILE_KEYS = (
    "document_files",
    "document_pages",
    "assistant_messages",
    "assistant_uploads",
    "assistant_upload_pages",
)


def _is_postgres(store) -> bool:
    return hasattr(store, "client")


def _file(store) -> dict:
    data = store.load()
    for key in _FILE_KEYS:
        data.setdefault(key, [])
    return data


class AssistantRecords:
    def save_document_file(self, row: dict) -> None:
        if _is_postgres(self):
            self.client.table("document_files").upsert(row).execute()
            return
        data = _file(self)
        data["document_files"] = [
            item for item in data["document_files"] if item.get("id") != row["id"]
        ]
        data["document_files"].append(row)
        self.save(data)

    def document_file(self, file_id: str) -> dict | None:
        if _is_postgres(self):
            rows = (
                self.client.table("document_files").select("*").eq("id", file_id).limit(1).execute().data
                or []
            )
            return rows[0] if rows else None
        for row in _file(self)["document_files"]:
            if row.get("id") == file_id:
                return row
        return None

    def document_file_for(self, opportunity_id: str, url: str) -> dict | None:
        key = opportunity_id or ""
        if _is_postgres(self):
            rows = (
                self.client.table("document_files")
                .select("*")
                .eq("opportunity_id", key)
                .eq("document_url", url)
                .limit(1)
                .execute()
                .data
                or []
            )
            return rows[0] if rows else None
        for row in _file(self)["document_files"]:
            if row.get("opportunity_id") == key and row.get("document_url") == url:
                return row
        return None

    def document_files_for(self, opportunity_id: str) -> list[dict]:
        key = opportunity_id or ""
        if _is_postgres(self):
            return (
                self.client.table("document_files").select("*").eq("opportunity_id", key).execute().data
                or []
            )
        return [row for row in _file(self)["document_files"] if row.get("opportunity_id") == key]

    def replace_pages(self, file_id: str, pages: list[dict]) -> None:
        rows = [
            {
                "id": f"{file_id}:{page['page']}",
                "file_id": file_id,
                "page": page["page"],
                "heading": page.get("heading"),
                "text": page["text"],
            }
            for page in pages
        ]
        if _is_postgres(self):
            self.client.table("document_pages").delete().eq("file_id", file_id).execute()
            if rows:
                self.client.table("document_pages").insert(rows).execute()
            return
        data = _file(self)
        data["document_pages"] = [
            item for item in data["document_pages"] if item.get("file_id") != file_id
        ]
        data["document_pages"].extend(rows)
        self.save(data)

    def pages_for(self, file_id: str) -> list[dict]:
        if _is_postgres(self):
            rows = (
                self.client.table("document_pages").select("*").eq("file_id", file_id).execute().data
                or []
            )
        else:
            rows = [row for row in _file(self)["document_pages"] if row.get("file_id") == file_id]
        return sorted(rows, key=lambda row: row.get("page") or 0)

    def add_message(self, row: dict) -> None:
        row.setdefault("created_at", datetime.now(UTC).isoformat())
        if _is_postgres(self):
            self.client.table("assistant_messages").insert(row).execute()
            return
        data = _file(self)
        data["assistant_messages"].append(row)
        self.save(data)

    def messages_for(self, conversation_id: str) -> list[dict]:
        if _is_postgres(self):
            rows = (
                self.client.table("assistant_messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .execute()
                .data
                or []
            )
        else:
            rows = [
                row
                for row in _file(self)["assistant_messages"]
                if row.get("conversation_id") == conversation_id
            ]
        return sorted(rows, key=lambda row: row.get("created_at") or "")

    def messages_for_user(self, user_id: str) -> list[dict]:
        if _is_postgres(self):
            return (
                self.client.table("assistant_messages").select("*").eq("user_id", user_id).execute().data
                or []
            )
        return [row for row in _file(self)["assistant_messages"] if row.get("user_id") == user_id]

    def usage_count(self, user_id: str, day: str) -> int:
        row = self._usage_row(user_id, day)
        return int(row["count"]) if row else 0

    def set_usage(self, user_id: str, day: str, count: int) -> None:
        body = {"user_id": user_id, "day": day, "count": count}
        if _is_postgres(self):
            self.client.table("app_usage").upsert({"id": f"{user_id}:{day}", "body": body}).execute()
            return
        data = _file(self)
        data["usage"] = [
            item
            for item in data["usage"]
            if not (item.get("user_id") == user_id and item.get("day") == day)
        ]
        data["usage"].append(body)
        self.save(data)

    def spent_today(self, day: str) -> float:
        total = 0.0
        if _is_postgres(self):
            rows = self.client.table("assistant_messages").select("created_at,cost_usd").execute().data or []
        else:
            rows = _file(self)["assistant_messages"]
        for row in rows:
            stamp = str(row.get("created_at") or "")
            if stamp[:10] == day and row.get("cost_usd"):
                total += float(row["cost_usd"])
        return total

    def save_upload(self, row: dict, pages: list[dict]) -> None:
        page_rows = [
            {
                "id": f"{row['id']}:{page['page']}",
                "upload_id": row["id"],
                "page": page["page"],
                "heading": page.get("heading"),
                "text": page["text"],
            }
            for page in pages
        ]
        if _is_postgres(self):
            self.client.table("assistant_uploads").insert(row).execute()
            if page_rows:
                self.client.table("assistant_upload_pages").insert(page_rows).execute()
            return
        data = _file(self)
        data["assistant_uploads"].append(row)
        data["assistant_upload_pages"].extend(page_rows)
        self.save(data)

    def upload(self, upload_id: str) -> dict | None:
        if _is_postgres(self):
            rows = (
                self.client.table("assistant_uploads").select("*").eq("id", upload_id).limit(1).execute().data
                or []
            )
            return rows[0] if rows else None
        for row in _file(self)["assistant_uploads"]:
            if row.get("id") == upload_id:
                return row
        return None

    def upload_pages(self, upload_id: str) -> list[dict]:
        if _is_postgres(self):
            rows = (
                self.client.table("assistant_upload_pages")
                .select("*")
                .eq("upload_id", upload_id)
                .execute()
                .data
                or []
            )
        else:
            rows = [
                row for row in _file(self)["assistant_upload_pages"] if row.get("upload_id") == upload_id
            ]
        return sorted(rows, key=lambda row: row.get("page") or 0)

    def uploads_for_user(self, user_id: str) -> list[dict]:
        if _is_postgres(self):
            return (
                self.client.table("assistant_uploads").select("*").eq("user_id", user_id).execute().data
                or []
            )
        return [row for row in _file(self)["assistant_uploads"] if row.get("user_id") == user_id]

    def bind_uploads(self, user_id: str, upload_ids: list[str], conversation_id: str) -> None:
        for upload_id in upload_ids:
            row = self.upload(upload_id)
            if row is None or row.get("user_id") != user_id:
                continue
            row["conversation_id"] = conversation_id
            if _is_postgres(self):
                self.client.table("assistant_uploads").update(
                    {"conversation_id": conversation_id}
                ).eq("id", upload_id).execute()
            else:
                data = _file(self)
                for item in data["assistant_uploads"]:
                    if item.get("id") == upload_id:
                        item["conversation_id"] = conversation_id
                self.save(data)

    def delete_upload(self, upload_id: str) -> None:
        if _is_postgres(self):
            self.client.table("assistant_upload_pages").delete().eq("upload_id", upload_id).execute()
            self.client.table("assistant_uploads").delete().eq("id", upload_id).execute()
            return
        data = _file(self)
        data["assistant_uploads"] = [
            row for row in data["assistant_uploads"] if row.get("id") != upload_id
        ]
        data["assistant_upload_pages"] = [
            row for row in data["assistant_upload_pages"] if row.get("upload_id") != upload_id
        ]
        self.save(data)

    def purge_expired_uploads(self, now: datetime) -> int:
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        gone = 0
        for row in list(self._all_uploads()):
            expires = datetime.fromisoformat(row["expires_at"])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if expires <= now:
                self.delete_upload(row["id"])
                gone += 1
        return gone

    def delete_user_assistant(self, user_id: str) -> None:
        for row in self.uploads_for_user(user_id):
            self.delete_upload(row["id"])
        if _is_postgres(self):
            self.client.table("assistant_messages").delete().eq("user_id", user_id).execute()
            rows = self.client.table("app_usage").select("id,body").execute().data or []
            for row in rows:
                if (row.get("body") or {}).get("user_id") == user_id:
                    self.client.table("app_usage").delete().eq("id", row["id"]).execute()
            return
        data = _file(self)
        data["assistant_messages"] = [
            row for row in data["assistant_messages"] if row.get("user_id") != user_id
        ]
        data["usage"] = [row for row in data["usage"] if row.get("user_id") != user_id]
        self.save(data)

    def _all_uploads(self) -> list[dict]:
        if _is_postgres(self):
            return self.client.table("assistant_uploads").select("*").execute().data or []
        return list(_file(self)["assistant_uploads"])

    def _usage_row(self, user_id: str, day: str) -> dict | None:
        if _is_postgres(self):
            rows = self.client.table("app_usage").select("id,body").execute().data or []
            for row in rows:
                body = row.get("body") or {}
                if body.get("user_id") == user_id and body.get("day") == day:
                    return body
            return None
        for row in _file(self)["usage"]:
            if row.get("user_id") == user_id and row.get("day") == day:
                return row
        return None
