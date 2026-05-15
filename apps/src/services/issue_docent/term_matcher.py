from dataclasses import dataclass, field


@dataclass(frozen=True)
class StockTermForMatch:
    id: int
    term: str
    aliases: list[str] = field(default_factory=list)
    category: str = ""
    definition: str = ""


@dataclass(frozen=True)
class TermMatch:
    term_id: int
    term: str
    category: str
    definition: str
    start: int
    end: int


@dataclass(frozen=True)
class _Candidate:
    term: StockTermForMatch
    keyword: str
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


def match_terms(text: str, terms: list[StockTermForMatch]) -> list[TermMatch]:
    candidates = [_first_candidate_for_term(text, term) for term in terms]
    candidates = [candidate for candidate in candidates if candidate is not None]
    candidates.sort(key=lambda candidate: (-candidate.length, candidate.start, candidate.term.id))

    accepted: list[_Candidate] = []
    for candidate in candidates:
        if any(_overlaps(candidate, other) for other in accepted):
            continue
        accepted.append(candidate)

    accepted.sort(key=lambda candidate: candidate.start)
    return [
        TermMatch(
            term_id=candidate.term.id,
            term=candidate.term.term,
            category=candidate.term.category,
            definition=candidate.term.definition,
            start=candidate.start,
            end=candidate.end,
        )
        for candidate in accepted
    ]


def _first_candidate_for_term(text: str, term: StockTermForMatch) -> _Candidate | None:
    keywords = [term.term, *term.aliases]
    candidates: list[_Candidate] = []
    haystack = text.casefold()

    for keyword in dict.fromkeys(keywords):
        if len(keyword) < 2:
            continue
        needle = keyword.casefold()
        start = haystack.find(needle)
        while start != -1:
            candidates.append(
                _Candidate(
                    term=term,
                    keyword=keyword,
                    start=start,
                    end=start + len(keyword),
                )
            )
            start = haystack.find(needle, start + len(needle))

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: (candidate.start, -candidate.length))
    return candidates[0]


def _overlaps(left: _Candidate, right: _Candidate) -> bool:
    return left.start < right.end and right.start < left.end
