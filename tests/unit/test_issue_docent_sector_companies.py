from apps.src.services.issue_docent.sector_companies import CompanyMasterCandidate, build_sector_companies


def candidate(
    *,
    id: int,
    krx_name: str,
    dart_name: str | None,
    sector: str | None,
    market: str | None,
) -> CompanyMasterCandidate:
    return CompanyMasterCandidate(
        id=id,
        krx_name=krx_name,
        dart_name=dart_name,
        sector=sector,
        market=market,
    )


def test_build_sector_companies_prefers_krx_name_and_preserves_order():
    result = build_sector_companies(
        ["삼성전자", "현대자동차", "SK하이닉스"],
        [
            candidate(
                id=1,
                krx_name="삼성전자",
                dart_name="삼성전자",
                sector="전기·전자",
                market="KOSPI",
            ),
            candidate(
                id=2,
                krx_name="SK하이닉스",
                dart_name="SK하이닉스",
                sector="전기·전자",
                market="KOSPI",
            ),
            candidate(
                id=3,
                krx_name="현대자동차",
                dart_name="현대자동차",
                sector="운송장비·부품",
                market="KOSPI",
            ),
        ],
    )

    assert [group.sector for group in result] == ["전기·전자", "운송장비·부품"]
    assert [company.name for company in result[0].companies] == ["삼성전자", "SK하이닉스"]
    assert [company.name for company in result[1].companies] == ["현대자동차"]


def test_build_sector_companies_prefers_krx_match_before_dart_match():
    result = build_sector_companies(
        ["삼성전자"],
        [
            candidate(
                id=1,
                krx_name="삼성전자",
                dart_name="삼성전자주식회사",
                sector="전기·전자",
                market="KOSPI",
            ),
            candidate(
                id=2,
                krx_name="다른회사",
                dart_name="삼성전자",
                sector="기타",
                market="KOSDAQ",
            ),
        ],
    )

    assert result[0].sector == "전기·전자"
    assert result[0].companies[0].company_id == 1


def test_build_sector_companies_falls_back_to_dart_name():
    result = build_sector_companies(
        ["현대차"],
        [
            candidate(
                id=3,
                krx_name="현대자동차",
                dart_name="현대차",
                sector="운송장비·부품",
                market="KOSPI",
            )
        ],
    )

    assert result[0].companies[0].company_id == 3
    assert result[0].companies[0].name == "현대자동차"


def test_build_sector_companies_keeps_unmatched_names_in_null_group():
    result = build_sector_companies(["미등록회사"], [])

    assert result[0].sector is None
    assert result[0].companies[0].company_id is None
    assert result[0].companies[0].name == "미등록회사"
    assert result[0].companies[0].market is None


def test_build_sector_companies_groups_all_null_sector_companies_together():
    result = build_sector_companies(
        ["미등록회사", "섹터미정회사"],
        [
            candidate(
                id=3,
                krx_name="섹터미정회사",
                dart_name=None,
                sector=None,
                market="KOSDAQ",
            )
        ],
    )

    assert len(result) == 1
    assert result[0].sector is None
    assert [company.name for company in result[0].companies] == ["미등록회사", "섹터미정회사"]


def test_build_sector_companies_treats_duplicate_exact_matches_as_null():
    result = build_sector_companies(
        ["중복회사"],
        [
            candidate(id=1, krx_name="중복회사", dart_name=None, sector="A", market="KOSPI"),
            candidate(id=2, krx_name="중복회사", dart_name=None, sector="B", market="KOSDAQ"),
        ],
    )

    assert result[0].sector is None
    assert result[0].companies[0].company_id is None


def test_build_sector_companies_treats_duplicate_dart_matches_as_null():
    result = build_sector_companies(
        ["공통법인명"],
        [
            candidate(id=1, krx_name="회사A", dart_name="공통법인명", sector="A", market="KOSPI"),
            candidate(id=2, krx_name="회사B", dart_name="공통법인명", sector="B", market="KOSDAQ"),
        ],
    )

    assert result[0].sector is None
    assert result[0].companies[0].company_id is None


def test_build_sector_companies_returns_empty_list_without_extracted_names():
    result = build_sector_companies(
        [],
        [
            candidate(
                id=1,
                krx_name="삼성전자",
                dart_name="삼성전자",
                sector="전기·전자",
                market="KOSPI",
            )
        ],
    )

    assert result == []
