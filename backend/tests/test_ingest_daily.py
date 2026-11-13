from datetime import date
from pathlib import Path

from app.jobs.ingest_daily import run_one, since_for
from app.store import FileStore


def _store(tmp_path: Path) -> FileStore:
    return FileStore(tmp_path / "opportunities.json")


def test_a_failure_is_recorded_and_the_next_source_still_runs(tmp_path: Path):
    store = _store(tmp_path)

    def boom(source, since, vertical):
        del source, since, vertical
        raise RuntimeError("portal caído")

    assert run_one("ted", today=date(2026, 11, 11), execute=boom, store=store) == 1
    failed = store.load()["ingest_runs"]
    assert failed[0]["status"] == "failed"
    assert "portal" in failed[0]["message"]

    def ok(source, since, vertical):
        del source, since, vertical
        return {"raw_count": 3, "kept": 1, "indexed": 1, "unchanged": 2}

    assert run_one("eu-ft", today=date(2026, 11, 11), execute=ok, store=store) == 0
    rows = {row["source"]: row for row in store.load()["ingest_runs"]}
    assert rows["eu-ft"]["status"] == "ok"
    assert rows["ted"]["status"] == "failed"


def test_a_second_run_waits_and_a_failure_does_not_move_the_watermark(tmp_path: Path):
    store = _store(tmp_path)
    seen = []

    def ok(source, since, vertical):
        del vertical
        seen.append((source, since))
        return {"raw_count": 1, "kept": 1, "indexed": 1, "unchanged": 0}

    assert run_one("bdns", today=date(2026, 11, 10), execute=ok, store=store) == 0
    assert since_for("bdns", date(2026, 11, 12), None, store) == date(2026, 11, 8)

    def boom(source, since, vertical):
        del source, since, vertical
        raise RuntimeError("otra vez")

    assert run_one("bdns", today=date(2026, 11, 12), execute=boom, store=store) == 1
    assert since_for("bdns", date(2026, 11, 13), None, store) == date(2026, 11, 8)


def test_a_live_lock_skips_the_second_execution(tmp_path: Path):
    store = _store(tmp_path)
    calls = []

    def ok(source, since, vertical):
        del source, since, vertical
        calls.append("ran")
        # Deja el cerrojo abierto a propósito: no se llama a finish desde aquí.
        return {"raw_count": 0, "kept": 0, "indexed": 0, "unchanged": 0}

    assert run_one("placsp", today=date(2026, 11, 11), execute=ok, store=store) == 0
    # La ejecución anterior ya cerró el cerrojo. Abrimos uno a mano, reciente.
    from datetime import UTC, datetime

    assert store.begin_ingest("placsp", datetime.now(UTC))
    assert run_one("placsp", today=date(2026, 11, 11), execute=ok, store=store) == 0
    assert calls == ["ran"]


def test_a_term_search_with_zero_rows_does_not_page_ops(tmp_path: Path, monkeypatch):
    store = _store(tmp_path)
    sent = []
    monkeypatch.setattr("app.jobs.ingest_daily.report_failure", lambda *args: sent.append(args))

    def empty(source, since, vertical):
        del source, since, vertical
        return {"raw_count": 0, "kept": 0, "indexed": 0, "unchanged": 0}

    assert run_one("bdns", today=date(2026, 11, 13), execute=empty, store=store) == 0
    assert sent == []

    assert run_one("ted", today=date(2026, 11, 13), execute=empty, store=store) == 0
    assert sent and "volume 0" in sent[-1][1]
