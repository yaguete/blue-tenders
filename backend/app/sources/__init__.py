from app.sources.aides_territoires import AidesTerritoiresSource
from app.sources.bdns import BdnsSource
from app.sources.boamp import BoampSource
from app.sources.boe import BoeSource
from app.sources.contracts_finder import ContractsFinderSource
from app.sources.curated import CuratedSource
from app.sources.doffin import DoffinSource
from app.sources.eu_ft import EuFtSource
from app.sources.fts import FtsSource
from app.sources.placsp import PlacspConsultasSource, PlacspRegionalSource, PlacspSource
from app.sources.scraped import load_scraped_sources
from app.sources.ted import TedSource
from app.sources.tenderned import TendernedSource
from app.sources.watched import WatchedSource

REGISTRY = {
    s.id: s
    for s in [
        TedSource(),
        EuFtSource(),
        PlacspSource(),
        PlacspRegionalSource(),
        PlacspConsultasSource(),
        BdnsSource(),
        CuratedSource(),
        WatchedSource(),
        FtsSource(),
        ContractsFinderSource(),
        BoeSource(),
        BoampSource(),
        AidesTerritoiresSource(),
        TendernedSource(),
        DoffinSource(),
        *load_scraped_sources(),
    ]
}
