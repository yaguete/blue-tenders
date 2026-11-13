from app.enrich.analyse import analyse
from app.jobs.fix_summaries import run
from app.models.opportunity import Analysis, AnalysisBlock, Opportunity
from app.settings import settings
from app.store import FileStore


def _opp(**kwargs) -> Opportunity:
    base = {
        "id": "1",
        "source_id": "ted",
        "external_id": "1",
        "url": "https://example.test",
        "title": "Only a title",
        "language": "en",
    }
    base.update(kwargs)
    return Opportunity(**base)


def test_a_title_only_source_does_not_call_the_model(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    called = {}
    monkeypatch.setattr("app.enrich.analyse._from_llm", lambda *args, **kwargs: called.setdefault("yes", True))
    item = _opp(description="Only a title")
    analyse(item)
    assert "yes" not in called
    assert not item.summary_en
    assert not item.analysis.summary


def test_boilerplate_is_a_thin_source(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr("app.enrich.analyse._from_llm", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("llm")))
    item = _opp(title="Supply of a lidar", description="Conforme especificaciones PCAP")
    analyse(item)
    assert not item.summary_en


def test_a_meta_summary_from_the_model_is_dropped(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    description = "Supply and installation of a scanning LiDAR to assess offshore wind potential in La Réunion."
    item = _opp(title="LiDAR", description=description, language="en")

    def fake_llm(opp, local):
        return Analysis(
            summary="The provided text is only a title, so this summary cannot cover them.",
            blocks=[AnalysisBlock(heading="Note", text="The notice does not specify the budget.", origin="generated")],
        )

    monkeypatch.setattr("app.enrich.analyse._from_llm", fake_llm)
    # La descripción es larga, así que sí se llamaría al modelo.
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    analyse(item)
    assert item.analysis.summary
    assert "provided text" not in item.analysis.summary.lower()
    assert "LiDAR" in item.analysis.summary or "lidar" in item.analysis.summary.lower() or "Réunion" in item.analysis.summary


def test_fix_summaries_dry_run_counts_and_does_not_write(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    store = FileStore(tmp_path / "opportunities.json")
    item = _opp(
        description="Only a title",
        summary_en="The text is only a title for a call concerning cables.",
    )
    item.analysis = Analysis(summary="The text is only a title.", blocks=[])
    store.upsert_opportunities([item])
    assert run(store, dry_run=True) == 1
    saved = store.get(item.id)
    assert saved.summary_en.startswith("The text is only a title")
