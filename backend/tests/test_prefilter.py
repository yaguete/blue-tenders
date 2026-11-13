"""El prefiltro solo ahorra LLM: no debe perder nada relevante ni casar por subcadenas."""

import pytest

from app.models.tender import Tender
from app.pipeline.run import prefilter
from app.vertical import load_vertical


def _tender(title: str, description: str | None = None) -> Tender:
    return Tender(
        id=title, source_id="t", external_id=title, url="x", title=title, description=description
    )


def _kept(title: str, description: str | None = None) -> bool:
    return bool(prefilter([_tender(title, description)], load_vertical("blue-economy")))


@pytest.mark.parametrize(
    "title",
    [
        "Shore power installation at port terminal",
        "Onshore power supply (OPS) for the ferry terminal",
        # Topic real HORIZON-CL5-2023-D3-02-15: el prefiltro anterior lo perdía.
        (
            "Critical technologies to improve the lifetime, efficient decommissioning and "
            "increase the circularity of offshore and onshore wind energy systems"
        ),
        "Onshore substation works for the offshore wind farm",
        "Supply of subsea cables for the interconnector",
        "Parque de eolica marina flotante",  # sin tilde
        "Suministro de energía EÓLICA MARINA",
    ],
)
def test_relevant_titles_are_kept(title):
    assert _kept(title)


@pytest.mark.parametrize(
    "title",
    [
        "Ultrasonic scissors for blood vessel surgery",
        "Pressure vessel inspection services",
        "Workshops and laptops for the regional office",  # "OPS" no es una subcadena
        "Road maintenance works",
    ],
)
def test_noise_is_dropped(title):
    assert not _kept(title)


def test_project_keywords_do_not_enter_the_call_prefilter():
    """«wind turbine» casa proyectos de CORDIS, no convocatorias: también es eólica terrestre."""
    assert not _kept("Recycling of wind turbine blades")
    vertical = load_vertical("blue-economy")
    wind = next(sub for sub in vertical.subsectors if sub.id == "offshore-wind")
    assert "wind turbine" in wind.project_keywords
    assert vertical.track_record.min_text_similarity == 0.15
    assert vertical.track_record.awards_min_text_similarity == 0.14
    assert vertical.track_record.ending_window_months == 9


@pytest.mark.parametrize(
    "title",
    [
        # alemán: compuestos, casan por prefijo
        "Skandinavienkai Travemünde - Ausbau Landstromanlage, 2. Stufe",
        "Netzanbindungssystem für den Offshore-Windpark Nordsee",
        "Verlegung von Seekabeln",
        "Beschaffung einer emissionsfreien Fähre und eines emissionsfreien Schiffes",
        # francés
        "Raccordement du parc éolien en mer de Dunkerque",
        "Fourniture et pose de câbles sous-marins",
        "Travaux d'électrification des quais du port",
        "Étude pour une ferme d'hydroliennes",
        # portugués
        "Parque eólico offshore flutuante de Viana do Castelo",
        "Instalação de cabos submarinos",
        "Eletrificação do cais do terminal de cruzeiros",
        # español
        "Suministro eléctrico a buques en el muelle de cruceros",
        "Tendido de cable submarino entre islas",
    ],
)
def test_other_languages_are_kept(title):
    assert _kept(title)


@pytest.mark.parametrize(
    "title",
    [
        "Lieferung von Strom für Landesliegenschaften",  # "Land…" no es "Landstrom"
        "Fourniture de câbles électriques pour bâtiments",
        "Manutenção de embarcações de pesca",
        "Suministro de energía eléctrica a edificios municipales",
    ],
)
def test_other_languages_noise_is_dropped(title):
    assert not _kept(title)


def test_short_prefix_is_rejected():
    from app.pipeline.run import _keyword_words

    with pytest.raises(ValueError):
        _keyword_words("ops*")


def test_keyword_in_description_counts():
    assert _kept("Lot 3", description="Works include a new offshore substation.")


def test_words_far_apart_do_not_match():
    far = "Offshore banking licence renewal for the regional office, plus a wind tunnel study"
    assert not _kept(far)
