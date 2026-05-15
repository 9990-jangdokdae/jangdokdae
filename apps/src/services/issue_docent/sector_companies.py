from collections import OrderedDict
from dataclasses import dataclass

from apps.src.schemas.issue_docent import SectorCompanies, SectorCompany


@dataclass(frozen=True)
class CompanyMasterCandidate:
    id: int
    krx_name: str
    dart_name: str | None
    sector: str | None
    market: str | None


def build_sector_companies(
    extracted_company_names: list[str],
    candidates: list[CompanyMasterCandidate],
) -> list[SectorCompanies]:
    groups: OrderedDict[str | None, list[SectorCompany]] = OrderedDict()
    for extracted_name in extracted_company_names:
        matched = _match_candidate(extracted_name, candidates)
        if matched is None:
            company = SectorCompany(company_id=None, name=extracted_name, market=None)
            sector = None
        else:
            company = SectorCompany(
                company_id=matched.id,
                name=matched.krx_name,
                market=matched.market,
            )
            sector = matched.sector
        groups.setdefault(sector, []).append(company)
    return [
        SectorCompanies(sector=sector, companies=companies)
        for sector, companies in groups.items()
    ]


def _match_candidate(
    extracted_name: str,
    candidates: list[CompanyMasterCandidate],
) -> CompanyMasterCandidate | None:
    krx_matches = [candidate for candidate in candidates if candidate.krx_name == extracted_name]
    if len(krx_matches) == 1:
        return krx_matches[0]
    if len(krx_matches) > 1:
        return None

    dart_matches = [candidate for candidate in candidates if candidate.dart_name == extracted_name]
    if len(dart_matches) == 1:
        return dart_matches[0]
    return None
