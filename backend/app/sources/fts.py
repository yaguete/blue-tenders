"""Find a Tender (Reino Unido, sobre umbral). API OCDS, Open Government Licence.

El mismo adaptador, con otra URL, lee Contracts Finder (bajo umbral).
"""

from app.sources.ocds import OcdsSource

SEARCH_URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"


class FtsSource(OcdsSource):
    id = "fts"
    search_url = SEARCH_URL
    date_param = "updatedFrom"
    notice_base = "https://www.find-tender.service.gov.uk/Notice/"
