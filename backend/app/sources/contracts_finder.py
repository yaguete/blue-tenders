"""Contracts Finder (Reino Unido, bajo umbral). El mismo OCDS que Find a Tender.

El dominio con guion (`contracts-finder`) no resuelve. Este es el que responde.
`publishedFrom` lleva hora, igual que `updatedFrom` en Find a Tender.
"""

from app.sources.ocds import OcdsSource

SEARCH_URL = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"


class ContractsFinderSource(OcdsSource):
    id = "contracts-finder"
    search_url = SEARCH_URL
    date_param = "publishedFrom"
    notice_base = "https://www.contractsfinder.service.gov.uk/Notice/"
