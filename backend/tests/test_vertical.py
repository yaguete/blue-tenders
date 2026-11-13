from app.models.tender import Tender
from app.pipeline.run import prefilter
from app.vertical import load_vertical


def test_load_blue_economy():
    v = load_vertical("blue-economy")
    assert v.id == "blue-economy"
    assert len(v.active_subsectors) == 6


def test_prefilter_excludes_noise():
    v = load_vertical("blue-economy")
    good = Tender(id="1", source_id="t", external_id="1", url="x",
                  title="Shore power installation at port terminal")
    noise = Tender(id="2", source_id="t", external_id="2", url="x",
                   title="Ultrasonic scissors for blood vessel surgery")
    assert prefilter([good, noise], v) == [good]
