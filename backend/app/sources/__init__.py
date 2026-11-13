from app.sources.bdns import BdnsSource
from app.sources.boamp import BoampSource
from app.sources.boe import BoeSource
from app.sources.curated import CuratedSource
from app.sources.eu_ft import EuFtSource
from app.sources.fts import FtsSource
from app.sources.placsp import PlacspRegionalSource, PlacspSource
from app.sources.ted import TedSource
from app.sources.watched import WatchedSource

REGISTRY = {
    s.id: s
    for s in [
        TedSource(),
        EuFtSource(),
        PlacspSource(),
        PlacspRegionalSource(),
        BdnsSource(),
        CuratedSource(),
        WatchedSource(),
        FtsSource(),
        BoeSource(),
        BoampSource(),
    ]
}
