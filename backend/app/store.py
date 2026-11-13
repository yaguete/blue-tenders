"""Almacén. JSON local si no hay Supabase; si lo hay, Postgres y el JSON no se usa."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.assistant.records import AssistantRecords
from app.models.opportunity import NoticeKind, Opportunity
from app.settings import settings

_HISTORY_FIELDS = ("deadline_at", "status", "budget_total_eur")
_ACCOUNT = {
    "profiles": "app_profiles",
    "saved": "app_saved",
    "alerts": "app_alerts",
    "reviews": "app_reviews",
    "reports": "app_reports",
    "conversations": "app_conversations",
    "usage": "app_usage",
    "suppressions": "app_suppressions",
}

_PARTNER_EMPTY = {"orgs": [], "projects": [], "participations": [], "sources": []}


def _chunks(rows: list, size: int = 500):
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _topics(project: dict) -> list[str]:
    value = project.get("topics")
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    topic = project.get("topic")
    if isinstance(topic, str) and topic.strip():
        return [part.strip() for part in topic.split(",") if part.strip()]
    return []


def _end_year(project: dict) -> int | None:
    year = project.get("end_year")
    if isinstance(year, int):
        return year
    text = str(project.get("end_date") or "")[:4]
    return int(text) if text.isdigit() else None


def flat_participation(part: dict, org: dict, project: dict) -> dict:
    """Fila plana: lo que espera el puntuador (organización + proyecto + rol)."""
    return {
        "org_name": org.get("name") or org.get("org_name"),
        "country": org.get("country"),
        "activity_type": org.get("activity_type"),
        "pic": org.get("pic"),
        "sme": org.get("sme"),
        "demo": bool(project.get("demo")),
        "acronym": project.get("acronym"),
        "title": project.get("title"),
        "objective": project.get("objective") or "",
        "topic_title": project.get("topic_title") or "",
        "topics": _topics(project),
        "url": project.get("url"),
        "role": part.get("role"),
        "programme_id": project.get("programme_id"),
        "end_year": _end_year(project),
        "subsectors": project.get("subsectors") or [],
        "project_id": project.get("id") or part.get("project_id"),
        "cpv": project.get("cpv") or [],
    }


def _project_row(project: dict) -> dict:
    return {
        "id": project["id"],
        "source": project["source"],
        "programme_id": project.get("programme_id"),
        "topic": ",".join(_topics(project)),
        "topic_title": project.get("topic_title") or None,
        "acronym": project.get("acronym"),
        "title": project.get("title"),
        "objective": project.get("objective"),
        "end_date": project.get("end_date"),
        "subsectors": project.get("subsectors") or [],
        "url": project.get("url"),
        "demo": False,
    }


def _org_row(org: dict) -> dict:
    return {
        "id": org["id"],
        "pic": org.get("pic"),
        "name": org["name"],
        "country": org.get("country"),
        "activity_type": org.get("activity_type"),
        "sme": org.get("sme"),
    }


def _empty() -> dict:
    return {
        "opportunities": [],
        "profiles": [],
        "saved": [],
        "alerts": [],
        "reviews": [],
        "reports": [],
        "conversations": [],
        "usage": [],
        "suppressions": [],
        "ingest_runs": [],
        "field_history": [],
        "watched_snapshots": [],
        "document_files": [],
        "document_pages": [],
        "assistant_messages": [],
        "assistant_uploads": [],
        "assistant_upload_pages": [],
    }


class FileStore(AssistantRecords):
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict:
        if not self.path.exists():
            return _empty()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for key in _empty():
            data.setdefault(key, [])
        return data

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def opportunities(self) -> list[Opportunity]:
        out = []
        for row in self.load()["opportunities"]:
            out.append(Opportunity.model_validate(row))
        return out

    def upsert_opportunities(self, items: list[Opportunity]) -> int:
        data = self.load()
        by_id = {row["id"]: row for row in data["opportunities"]}
        now = datetime.now(UTC).isoformat()
        for item in items:
            row = item.model_dump(mode="json")
            previous = by_id.get(item.id)
            if previous and previous.get("content_hash") == row.get("content_hash"):
                row["analysis"] = previous.get("analysis") or row.get("analysis")
            for field in _HISTORY_FIELDS:
                old = previous.get(field) if previous else None
                if previous and old != row.get(field):
                    data["field_history"].append(
                        {
                            "opportunity_id": item.id,
                            "field": field,
                            "old_value": old,
                            "new_value": row.get(field),
                            "changed_at": now,
                        }
                    )
            by_id[item.id] = row
        data["opportunities"] = list(by_id.values())
        self.save(data)
        return len(items)

    def get(self, opportunity_id: str) -> Opportunity | None:
        for item in self.opportunities():
            if item.id == opportunity_id:
                return item
        return None

    def content_hashes(self, ids: list[str]) -> dict[str, str]:
        wanted = set(ids)
        found = {}
        for row in self.load()["opportunities"]:
            if row.get("id") in wanted and row.get("content_hash"):
                found[row["id"]] = row["content_hash"]
        return found

    def begin_ingest(self, source: str, now: datetime) -> str | None:
        data = self.load()
        for row in data["ingest_runs"]:
            if row.get("source") != source or row.get("finished_at"):
                continue
            started = datetime.fromisoformat(row["started_at"])
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            if now - started < timedelta(hours=2):
                return None
            row["finished_at"] = now.isoformat()
            row["status"] = "failed"
            row["message"] = "stale lock"
        run_id = uuid4().hex[:12]
        data["ingest_runs"].append(
            {
                "id": run_id,
                "source": source,
                "started_at": now.isoformat(),
                "finished_at": None,
                "status": "running",
            }
        )
        self.save(data)
        return run_id

    def finish_ingest(self, run_id: str, **fields) -> None:
        data = self.load()
        for row in data["ingest_runs"]:
            if row.get("id") == run_id:
                row.update(fields)
                break
        self.save(data)

    def last_ok_raw(self, source: str) -> int | None:
        best = None
        stamp = ""
        for row in self.load()["ingest_runs"]:
            if row.get("source") != source or row.get("status") != "ok":
                continue
            finished = row.get("finished_at") or ""
            if finished >= stamp and row.get("raw_count") is not None:
                stamp = finished
                best = int(row["raw_count"])
        return best

    def recent_history(self) -> list[dict]:
        return list(self.load()["field_history"])

    def last_success_until(self, source: str):
        best = None
        for row in self.load()["ingest_runs"]:
            if (
                row.get("source") == source
                and row.get("status") == "ok"
                and row.get("until")
                and (best is None or row["until"] > best)
            ):
                best = row["until"]
        return best

    def source_freshness(self) -> dict:
        latest: dict[str, dict] = {}
        for row in self.load()["ingest_runs"]:
            current = latest.get(row["source"])
            stamp = row.get("finished_at") or row.get("started_at") or ""
            if current is None or stamp > (current.get("finished_at") or current.get("started_at") or ""):
                latest[row["source"]] = {
                    "status": row.get("status"),
                    "finished_at": row.get("finished_at"),
                    "until": row.get("until"),
                }
        return latest

    def awards_for(self, call_id: str | None) -> list[dict]:
        if not call_id:
            return []
        found = []
        for item in self.opportunities():
            if item.call_id != call_id or item.notice != NoticeKind.award_notice:
                continue
            winner = next((fact.value for fact in item.facts if fact.field == "winner_name"), None)
            amount = next((fact.value for fact in item.facts if fact.field == "award_value_eur"), None)
            found.append(
                {
                    "id": item.id,
                    "title": item.title_en or item.title,
                    "winner": winner,
                    "amount_eur": amount,
                    "url": item.url,
                }
            )
        return found

    def snapshot(self, page_id: str) -> dict | None:
        for row in self.load()["watched_snapshots"]:
            if row.get("page_id") == page_id:
                return row
        return None

    def save_snapshot(self, page_id: str, text_hash: str, body: str, fetched_at: str) -> None:
        data = self.load()
        data["watched_snapshots"] = [
            row for row in data["watched_snapshots"] if row.get("page_id") != page_id
        ]
        data["watched_snapshots"].append(
            {"page_id": page_id, "text_hash": text_hash, "body": body, "fetched_at": fetched_at}
        )
        self.save(data)

    def partners_path(self) -> Path:
        return self.path.with_name("partners.json")

    def _partners(self) -> dict:
        path = self.partners_path()
        if not path.exists():
            return {key: [] for key in _PARTNER_EMPTY}
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in _PARTNER_EMPTY:
            data.setdefault(key, [])
        return data

    def _save_partners(self, data: dict) -> None:
        path = self.partners_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def track_record_sources(self) -> dict[str, dict]:
        return {row["id"]: row for row in self._partners()["sources"] if row.get("id")}

    def save_track_record_source(self, source_id: str, **meta) -> None:
        data = self._partners()
        sources = {row["id"]: row for row in data["sources"] if row.get("id")}
        current = sources.get(source_id, {"id": source_id})
        current.update(meta)
        current["id"] = source_id
        sources[source_id] = current
        data["sources"] = list(sources.values())
        self._save_partners(data)

    def replace_cordis(
        self,
        source_id: str,
        orgs: list[dict],
        projects: list[dict],
        participations: list[dict],
        meta: dict,
    ) -> None:
        data = self._partners()
        by_org = {row["id"]: row for row in data["orgs"]}
        for org in orgs:
            by_org[org["id"]] = org
        old_ids = {row["id"] for row in data["projects"] if row.get("source") == source_id}
        new_ids = {row["id"] for row in projects}
        data["projects"] = [row for row in data["projects"] if row.get("source") != source_id]
        data["projects"].extend(projects)
        drop = old_ids | new_ids
        data["participations"] = [
            row for row in data["participations"] if row.get("project_id") not in drop
        ]
        data["participations"].extend(participations)
        data["orgs"] = list(by_org.values())
        sources = {row["id"]: row for row in data["sources"] if row.get("id")}
        sources[source_id] = {"id": source_id, **meta}
        data["sources"] = list(sources.values())
        self._save_partners(data)

    def cordis_participations(self) -> list[dict]:
        data = self._partners()
        orgs = {row["id"]: row for row in data["orgs"]}
        projects = {row["id"]: row for row in data["projects"]}
        rows = []
        for part in data["participations"]:
            org = orgs.get(part.get("org_id"))
            project = projects.get(part.get("project_id"))
            if org and project:
                rows.append(flat_participation(part, org, project))
        return rows

    def award_notices(self) -> list[Opportunity]:
        return [item for item in self.opportunities() if item.notice == NoticeKind.award_notice]

    def track_record_path(self) -> Path:
        return self.path.with_name("track_record.json")

    def _track(self) -> dict:
        path = self.track_record_path()
        if not path.exists():
            return {"config_hash": None, "records": {}, "pending": []}
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("records", {})
        data.setdefault("pending", [])
        return data

    def _save_track(self, data: dict) -> None:
        path = self.track_record_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)

    def saved_track_record(self, opportunity_id: str) -> dict | None:
        return self._track()["records"].get(opportunity_id)

    def save_track_record(self, opportunity_id: str, record: dict) -> None:
        data = self._track()
        data["records"][opportunity_id] = record
        data["pending"] = [item for item in data["pending"] if item != opportunity_id]
        self._save_track(data)

    def mark_track_record_pending(self, opportunity_id: str) -> None:
        data = self._track()
        if opportunity_id not in data["pending"]:
            data["pending"].append(opportunity_id)
            self._save_track(data)

    def pending_track_records(self) -> list[str]:
        return list(self._track()["pending"])

    def track_record_config_hash(self) -> str | None:
        return self._track().get("config_hash")

    def set_track_record_config_hash(self, value: str) -> None:
        data = self._track()
        data["config_hash"] = value
        self._save_track(data)


class SupabaseStore(AssistantRecords):
    """Oportunidades y estado de cuenta en Postgres. El cron y el API comparten esas tablas."""

    def __init__(self, client=None):
        if client is None:
            from supabase import create_client

            client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        self.client = client

    def _pages(self, table: str, columns: str = "*") -> list[dict]:
        rows: list[dict] = []
        start = 0
        while True:
            response = self.client.table(table).select(columns).range(start, start + 999).execute()
            batch = response.data or []
            rows.extend(batch)
            if len(batch) < 1000:
                return rows
            start += 1000

    def opportunities(self) -> list[Opportunity]:
        return [Opportunity.model_validate(row) for row in self._pages("opportunities")]

    def upsert_opportunities(self, items: list[Opportunity]) -> int:
        if not items:
            return 0
        ids = [item.id for item in items]
        previous = {
            row["id"]: row
            for row in (
                self.client.table("opportunities")
                .select("id,content_hash,deadline_at,status,budget_total_eur,analysis")
                .in_("id", ids)
                .execute()
                .data
                or []
            )
        }
        rows = []
        history = []
        now = datetime.now(UTC).isoformat()
        for item in items:
            row = item.model_dump(mode="json")
            row.pop("raw", None)
            old = previous.get(item.id)
            if old and old.get("content_hash") == row.get("content_hash"):
                row["analysis"] = old.get("analysis") or row.get("analysis")
            if old:
                for field in _HISTORY_FIELDS:
                    if old.get(field) != row.get(field):
                        history.append(
                            {
                                "opportunity_id": item.id,
                                "field": field,
                                "old_value": old.get(field),
                                "new_value": row.get(field),
                                "changed_at": now,
                            }
                        )
            rows.append(row)
        self.client.table("opportunities").upsert(rows).execute()
        if history:
            self.client.table("field_history").insert(history).execute()
        return len(rows)

    def get(self, opportunity_id: str) -> Opportunity | None:
        response = (
            self.client.table("opportunities").select("*").eq("id", opportunity_id).limit(1).execute()
        )
        if not response.data:
            return None
        return Opportunity.model_validate(response.data[0])

    def content_hashes(self, ids: list[str]) -> dict[str, str]:
        if not ids:
            return {}
        response = (
            self.client.table("opportunities").select("id,content_hash").in_("id", ids).execute()
        )
        return {
            row["id"]: row["content_hash"]
            for row in response.data or []
            if row.get("content_hash")
        }

    def begin_ingest(self, source: str, now: datetime) -> str | None:
        open_rows = (
            self.client.table("ingest_runs")
            .select("id,started_at")
            .eq("source", source)
            .is_("finished_at", "null")
            .execute()
            .data
            or []
        )
        for row in open_rows:
            started = datetime.fromisoformat(row["started_at"])
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            if now - started < timedelta(hours=2):
                return None
            self.client.table("ingest_runs").update(
                {"finished_at": now.isoformat(), "status": "failed", "message": "stale lock"}
            ).eq("id", row["id"]).execute()
        run_id = uuid4().hex[:12]
        self.client.table("ingest_runs").insert(
            {
                "id": run_id,
                "source": source,
                "started_at": now.isoformat(),
                "status": "running",
            }
        ).execute()
        return run_id

    def finish_ingest(self, run_id: str, **fields) -> None:
        self.client.table("ingest_runs").update(fields).eq("id", run_id).execute()

    def last_ok_raw(self, source: str) -> int | None:
        rows = (
            self.client.table("ingest_runs")
            .select("raw_count")
            .eq("source", source)
            .eq("status", "ok")
            .order("finished_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows or rows[0].get("raw_count") is None:
            return None
        return int(rows[0]["raw_count"])

    def recent_history(self) -> list[dict]:
        return self._pages("field_history", "opportunity_id,field,old_value,new_value,changed_at")

    def last_success_until(self, source: str):
        rows = (
            self.client.table("ingest_runs")
            .select("until")
            .eq("source", source)
            .eq("status", "ok")
            .order("until", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows or not rows[0].get("until"):
            return None
        return rows[0]["until"]

    def source_freshness(self) -> dict:
        latest: dict[str, dict] = {}
        for row in self._pages("ingest_runs", "source,status,finished_at,started_at,until"):
            stamp = row.get("finished_at") or row.get("started_at") or ""
            current = latest.get(row["source"])
            if current is None or stamp > (current.get("finished_at") or ""):
                latest[row["source"]] = {
                    "status": row.get("status"),
                    "finished_at": row.get("finished_at"),
                    "until": row.get("until"),
                }
        return latest

    def awards_for(self, call_id: str | None) -> list[dict]:
        if not call_id:
            return []
        rows = (
            self.client.table("opportunities")
            .select("id,title,title_en,url,facts,notice")
            .eq("call_id", call_id)
            .eq("notice", "award_notice")
            .execute()
            .data
            or []
        )
        found = []
        for row in rows:
            facts = row.get("facts") or []
            winner = next((fact.get("value") for fact in facts if fact.get("field") == "winner_name"), None)
            amount = next((fact.get("value") for fact in facts if fact.get("field") == "award_value_eur"), None)
            found.append(
                {
                    "id": row["id"],
                    "title": row.get("title_en") or row.get("title"),
                    "winner": winner,
                    "amount_eur": amount,
                    "url": row.get("url"),
                }
            )
        return found

    def snapshot(self, page_id: str) -> dict | None:
        rows = (
            self.client.table("watched_snapshots").select("*").eq("page_id", page_id).limit(1).execute().data
            or []
        )
        return rows[0] if rows else None

    def save_snapshot(self, page_id: str, text_hash: str, body: str, fetched_at: str) -> None:
        self.client.table("watched_snapshots").upsert(
            {"page_id": page_id, "text_hash": text_hash, "body": body, "fetched_at": fetched_at}
        ).execute()

    def track_record_sources(self) -> dict[str, dict]:
        rows = self.client.table("partner_sources").select("*").execute().data or []
        return {row["id"]: row for row in rows if row.get("id")}

    def award_notice_count(self) -> int:
        response = (
            self.client.table("opportunities")
            .select("id", count="exact", head=True)
            .eq("notice", "award_notice")
            .limit(0)
            .execute()
        )
        return int(response.count or 0)

    def saved_track_record(self, opportunity_id: str) -> dict | None:
        rows = (
            self.client.table("opportunity_track_record")
            .select("*")
            .eq("opportunity_id", opportunity_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None

    def save_track_record(self, opportunity_id: str, record: dict) -> None:
        self.client.table("opportunity_track_record").upsert(
            {"opportunity_id": opportunity_id, "pending": False, **record}
        ).execute()
        self.client.table("opportunity_partner_matches").delete().eq("opportunity_id", opportunity_id).execute()
        matches = []
        for rank, org in enumerate(record.get("items") or []):
            matches.append(
                {
                    "opportunity_id": opportunity_id,
                    "org_id": org.get("pic") or org.get("org_name"),
                    "source": record.get("source"),
                    "rank": rank,
                    "score": org.get("score"),
                    "evidence": (org.get("projects") or [{}])[0].get("evidence"),
                    "projects": org.get("projects") or [],
                }
            )
        for batch in _chunks(matches):
            self.client.table("opportunity_partner_matches").upsert(batch).execute()

    def mark_track_record_pending(self, opportunity_id: str) -> None:
        current = self.saved_track_record(opportunity_id) or {
            "source": "cordis",
            "status": "not_loaded",
        }
        current["pending"] = True
        current["opportunity_id"] = opportunity_id
        self.client.table("opportunity_track_record").upsert(current).execute()

    def pending_track_records(self) -> list[str]:
        rows = (
            self.client.table("opportunity_track_record")
            .select("opportunity_id")
            .eq("pending", True)
            .execute()
            .data
            or []
        )
        return [row["opportunity_id"] for row in rows]

    def track_record_config_hash(self) -> str | None:
        row = self.track_record_sources().get("track-record-config") or {}
        return row.get("content_hash")

    def set_track_record_config_hash(self, value: str) -> None:
        self.save_track_record_source("track-record-config", content_hash=value)

    def save_track_record_source(self, source_id: str, **meta) -> None:
        current = self.track_record_sources().get(source_id, {"id": source_id})
        current.update(meta)
        current["id"] = source_id
        self.client.table("partner_sources").upsert(current).execute()

    def replace_cordis(
        self,
        source_id: str,
        orgs: list[dict],
        projects: list[dict],
        participations: list[dict],
        meta: dict,
    ) -> None:
        for batch in _chunks([_org_row(org) for org in orgs]):
            self.client.table("partner_orgs").upsert(batch).execute()
        for batch in _chunks([_project_row(project) for project in projects]):
            self.client.table("partner_projects").upsert(batch).execute()
        for batch in _chunks(participations):
            self.client.table("partner_participations").upsert(batch).execute()
        new_ids = {project["id"] for project in projects}
        new_pairs = {(row["org_id"], row["project_id"]) for row in participations}
        existing = self._ids_for("partner_projects", "source", source_id)
        stale = [project_id for project_id in existing if project_id not in new_ids]
        for batch in _chunks(stale):
            self.client.table("partner_projects").delete().in_("id", batch).execute()
        for project_id in new_ids:
            rows = (
                self.client.table("partner_participations")
                .select("org_id,project_id")
                .eq("project_id", project_id)
                .execute()
                .data
                or []
            )
            for row in rows:
                if (row["org_id"], row["project_id"]) in new_pairs:
                    continue
                (
                    self.client.table("partner_participations")
                    .delete()
                    .eq("org_id", row["org_id"])
                    .eq("project_id", row["project_id"])
                    .execute()
                )
        self.save_track_record_source(source_id, **meta)

    def cordis_participations(self) -> list[dict]:
        orgs = {row["id"]: row for row in self._pages("partner_orgs")}
        projects = {row["id"]: row for row in self._pages("partner_projects")}
        rows = []
        for part in self._pages("partner_participations"):
            org = orgs.get(part.get("org_id"))
            project = projects.get(part.get("project_id"))
            if org and project and org.get("name"):
                rows.append(flat_participation(part, org, project))
        return rows

    def award_notices(self) -> list[Opportunity]:
        rows: list[dict] = []
        start = 0
        while True:
            response = (
                self.client.table("opportunities")
                .select("*")
                .eq("notice", "award_notice")
                .range(start, start + 999)
                .execute()
            )
            batch = response.data or []
            rows.extend(batch)
            if len(batch) < 1000:
                break
            start += 1000
        return [Opportunity.model_validate(row) for row in rows]

    def _ids_for(self, table: str, column: str, value: str) -> list[str]:
        found = []
        start = 0
        while True:
            response = (
                self.client.table(table)
                .select("id")
                .eq(column, value)
                .range(start, start + 999)
                .execute()
            )
            batch = response.data or []
            found.extend(row["id"] for row in batch)
            if len(batch) < 1000:
                return found
            start += 1000

    def load(self) -> dict:
        data = _empty()
        for key, table in _ACCOUNT.items():
            data[key] = [row["body"] for row in self._pages(table)]
        return data

    def save(self, data: dict) -> None:
        for key, table in _ACCOUNT.items():
            id_col = "user_id" if key == "profiles" else "id"
            payload = []
            for row in data.get(key) or []:
                if key == "profiles":
                    payload.append({"user_id": row["user_id"], "body": row})
                elif key == "saved":
                    payload.append(
                        {"id": f"{row['user_id']}:{row['opportunity_id']}", "body": row}
                    )
                else:
                    payload.append({"id": row.get("id") or uuid4().hex[:12], "body": row})
            existing = [row[id_col] for row in self._pages(table, id_col)]
            if existing:
                self.client.table(table).delete().in_(id_col, existing).execute()
            if payload:
                self.client.table(table).upsert(payload).execute()


def get_store() -> FileStore | SupabaseStore:
    if settings.supabase_url and settings.supabase_service_role_key:
        return SupabaseStore()
    return FileStore(settings.data_dir / "opportunities.json")
