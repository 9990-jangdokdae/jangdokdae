# Issue Docent Quality 100 Review

## Goal

Issue Docent content must reach PASS on all five criteria:

- output quality
- prompt quality
- beginner difficulty
- central article reflection
- concision

This review is for the experiment branch `codex/issue-docent-quality-100-lab`.
No PR is created from this branch.

## Non-Goals

- Do not broaden a representative article into a market-wide issue just because nearby articles share a company, sector, or keyword.
- Do not solve prose quality primarily with broad forbidden-word lists or investment-advice validators.
- Do not use Pydantic to judge whether prose is financially advisable; use it only for structural and narrow format constraints.
- Do not preserve every detail from a source article when it weakens the central issue, beginner readability, or concision.
- Do not treat this document as a fixed checklist. If dry-run output fails the five criteria, revise prompts, schemas, graph boundaries, or review tooling and repeat.

## Current Review Evidence

Dry-run command:

```bash
LLM_THINKING_LEVEL=low LLM_TIMEOUT_SECONDS=120 LLM_TRANSPORT_MAX_RETRIES=1 \
uv run python -m apps.src.issue_docent.scripts.dry_run_issue_docent_quality \
  --cluster-id 1 --cluster-id 7 --cluster-id 69 \
  --cluster-id 2 --cluster-id 5 --cluster-id 10 \
  --structured-attempts 5 \
  --cache-dir /tmp/issue_docent_quality_cache \
  --output /tmp/issue_docent_quality_100_review_current_v7.json
```

Reviewed clusters:

| Cluster | Case Type | Output | Prompt | Beginner | Central Article | Concision |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | ETF asset growth with distracting related ETF articles | PASS | PASS | PASS | PASS | PASS |
| 7 | Single-company earnings with unrelated cluster neighbors | PASS | PASS | PASS | PASS | PASS |
| 69 | Policy/rule change with mixed ETF neighbors | PASS | PASS | PASS | PASS | PASS |
| 2 | Market index move and investor flow | PASS | PASS | PASS | PASS | PASS |
| 5 | Analyst target-price report | PASS | PASS | PASS | PASS | PASS |
| 10 | Individual company stake increase | PASS | PASS | PASS | PASS | PASS |

## Review Notes

- All reviewed outputs kept `selected_article_orders` on `[0]`, so final summaries stayed grounded in the representative article.
- All reviewed outputs were one or two paragraphs.
- The latest dry-run emitted `auto_gates` PASS for all five criteria and no `auto_review_notes`.
- Manual review of the same outputs found no remaining broad-market drift, investment-benefit wording, low-priority technical catalyst leakage, title numbers, teaser number overload, article-hype wording, or disallowed section use.

## Verification Still Required Before Merge

- Run the full test suite.
- Run `git diff --check`.
- Keep the branch as branch-only work unless a PR is explicitly requested.
