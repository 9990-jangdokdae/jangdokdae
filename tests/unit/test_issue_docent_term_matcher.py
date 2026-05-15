from apps.src.services.issue_docent.term_matcher import StockTermForMatch, match_terms


def test_match_terms_keeps_longest_overlap():
    matches = match_terms(
        "영업이익은 회사 실적에서 자주 등장한다.",
        [
            StockTermForMatch(id=1, term="영업", category="basic", definition=""),
            StockTermForMatch(id=2, term="영업이익", category="statement", definition=""),
        ],
    )

    assert [(match.term_id, match.start, match.end) for match in matches] == [(2, 0, 4)]


def test_match_terms_returns_first_match_per_term_id_only():
    matches = match_terms(
        "PER이 높다는 말과 주가수익비율이 높다는 말이 함께 나왔다.",
        [
            StockTermForMatch(
                id=1,
                term="PER",
                aliases=["주가수익비율"],
                category="valuation",
                definition="",
            )
        ],
    )

    assert len(matches) == 1
    assert matches[0].start == 0


def test_match_terms_skips_one_character_keywords():
    matches = match_terms(
        "금 가격이 올랐다.",
        [StockTermForMatch(id=1, term="금", category="asset", definition="")],
    )

    assert matches == []
