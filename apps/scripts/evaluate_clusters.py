"""클러스터링 결과 품질 평가 스크립트.

사용법:
    # 최신 실행 결과 자동 탐지
    python -m apps.scripts.evaluate_clusters

    # 특정 파일 지정
    python -m apps.scripts.evaluate_clusters --file data/20260511_230338/clusters_final.json

    # 의심 클러스터를 JSON으로 저장
    python -m apps.scripts.evaluate_clusters --save
"""

import argparse
import json
import statistics
from pathlib import Path

from apps.src.config.paths import DATA_DIR


# ── 임계값 ─────────────────────────────────────────────────────────────────
_NOISE_RATIO_WARN   = 0.35   # 노이즈(singleton) 비율 경고 기준
_COHESION_MIN       = 0.50   # 클러스터 응집도 절대 하한
_DOMINANCE_WARN     = 0.15   # 단일 클러스터 점유율 경고 기준


def _latest_cluster_file() -> Path:
    """data/ 하위 실행 디렉터리 중 가장 최근 것의 클러스터 파일을 반환합니다."""
    runs = sorted(
        (p for p in DATA_DIR.iterdir() if p.is_dir()),
        reverse=True,
    )
    for run in runs:
        for name in ("clusters_final.json", "clusters_extracted.json", "news_clusters.json"):
            candidate = run / name
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"클러스터 파일을 찾을 수 없습니다: {DATA_DIR}")


def _load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Tier 1 지표 계산 ────────────────────────────────────────────────────────

def compute_metrics(clusters: list[dict]) -> dict:
    """클러스터 목록에서 Tier 1 정량 지표를 계산합니다."""
    total_articles = sum(c["size"] for c in clusters)
    singletons = [c for c in clusters if c["is_singleton"]]
    multi     = [c for c in clusters if not c["is_singleton"]]

    # 응집도: 클러스터별 similarity_to_centroid 평균의 평균
    cohesions = [
        statistics.mean(a["similarity_to_centroid"] for a in c["articles"])
        for c in multi
    ]
    mean_cohesion = statistics.mean(cohesions) if cohesions else 0.0
    cohesion_std  = statistics.stdev(cohesions) if len(cohesions) > 1 else 0.0

    sizes = [c["size"] for c in multi]
    max_size = max(sizes, default=0)

    return {
        "total_articles":   total_articles,
        "total_clusters":   len(clusters),
        "valid_clusters":   len(multi),
        "singleton_count":  len(singletons),
        "noise_ratio":      len(singletons) / total_articles if total_articles else 0.0,
        "mean_cohesion":    mean_cohesion,
        "cohesion_std":     cohesion_std,
        "max_cluster_size": max_size,
        "max_dominance":    max_size / total_articles if total_articles else 0.0,
        "mean_cluster_size": statistics.mean(sizes) if sizes else 0.0,
    }


# ── 의심 클러스터 탐지 ───────────────────────────────────────────────────────

# 제목에서 기업 관련 여부를 판단하는 키워드 (기업명 추출 누락 감지용)
_COMPANY_SIGNALS = [
    "전자", "하이닉스", "자동차", "모빌리티", "은행", "증권", "바이오",
    "에너지", "화학", "건설", "엔터", "통신", "항공", "조선", "철강",
]


def find_suspicious(clusters: list[dict], metrics: dict) -> list[dict]:
    """검수 대상 의심 클러스터를 탐지합니다.

    탐지 규칙:
        1. 낮은 응집도  — 평균 cohesion < max(0.5, 전체평균 - 1σ)
        2. 거대 클러스터 — 기사 수 > 전체의 15%
        3. 추출 누락    — companies 비어 있는데 제목에 기업 신호어 존재
        4. 키워드 부족  — keywords < 2개
    """
    cohesion_threshold = max(
        _COHESION_MIN,
        metrics["mean_cohesion"] - metrics["cohesion_std"],
    )
    total = metrics["total_articles"]

    suspicious = []
    for c in clusters:
        if c["is_singleton"]:
            continue

        cluster_cohesion = statistics.mean(
            a["similarity_to_centroid"] for a in c["articles"]
        )
        reasons: list[str] = []

        if cluster_cohesion < cohesion_threshold:
            reasons.append(
                f"낮은 응집도 ({cluster_cohesion:.3f} < {cohesion_threshold:.3f})"
            )

        if c["size"] > total * _DOMINANCE_WARN:
            reasons.append(
                f"거대 클러스터 (기사 {c['size']}개, 전체의 {c['size'] / total:.1%})"
            )

        extraction = c.get("extraction")
        if extraction is not None:
            if not extraction.get("companies"):
                joined_titles = " ".join(a["title"] for a in c["articles"])
                if any(sig in joined_titles for sig in _COMPANY_SIGNALS):
                    reasons.append("기업명 추출 누락 (제목에 기업 관련 단어 존재)")

            if len(extraction.get("keywords", [])) < 2:
                reasons.append(f"키워드 부족 ({len(extraction.get('keywords', []))}개)")

        if reasons:
            suspicious.append({
                "cluster_id":    c["cluster_id"],
                "size":          c["size"],
                "mean_cohesion": round(cluster_cohesion, 4),
                "reasons":       reasons,
                "sample_titles": [a["title"] for a in c["articles"][:3]],
                "extraction":    extraction,
            })

    return sorted(suspicious, key=lambda x: x["mean_cohesion"])


# ── 출력 ────────────────────────────────────────────────────────────────────

def _status(value: float, warn: float, *, lower_is_better: bool = True) -> str:
    bad = value > warn if lower_is_better else value < warn
    return "⚠" if bad else "✓"


def print_report(metrics: dict, suspicious: list[dict], source: Path) -> None:
    print()
    print("=" * 55)
    print(f"  클러스터 품질 평가 — {source.parent.name}/{source.name}")
    print("=" * 55)

    nr  = metrics["noise_ratio"]
    coh = metrics["mean_cohesion"]
    dom = metrics["max_dominance"]

    print(f"\n[Tier 1 지표]")
    print(f"  전체 기사 수       : {metrics['total_articles']}")
    print(f"  전체 클러스터 수   : {metrics['total_clusters']}")
    print(f"  유효 클러스터 수   : {metrics['valid_clusters']}  (size ≥ 2)")
    print(f"  Singleton 수       : {metrics['singleton_count']}")
    print()
    print(f"  노이즈 비율        : {nr:.1%}  {_status(nr, _NOISE_RATIO_WARN)}  (권장 < {_NOISE_RATIO_WARN:.0%})")
    print(f"  평균 응집도        : {coh:.3f}  {_status(coh, _COHESION_MIN, lower_is_better=False)}  (권장 > {_COHESION_MIN})")
    print(f"  최대 클러스터 점유율: {dom:.1%}  {_status(dom, _DOMINANCE_WARN)}  (권장 < {_DOMINANCE_WARN:.0%})")
    print(f"  최대 클러스터 크기  : {metrics['max_cluster_size']}개 기사")
    print(f"  평균 클러스터 크기  : {metrics['mean_cluster_size']:.1f}개 기사")

    print(f"\n[의심 클러스터] {len(suspicious)}개")
    if not suspicious:
        print("  없음 ✓")
    else:
        for s in suspicious:
            print(f"\n  cluster_id={s['cluster_id']}  size={s['size']}  cohesion={s['mean_cohesion']}")
            for r in s["reasons"]:
                print(f"    ✗ {r}")
            for t in s["sample_titles"]:
                print(f"    · {t}")

    print()


# ── 진입점 ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="클러스터링 결과 품질 평가")
    parser.add_argument(
        "--file", type=Path, default=None,
        help="평가할 클러스터 JSON 파일 경로 (기본: 최신 실행 자동 탐지)",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="의심 클러스터를 suspicious_clusters.json으로 저장",
    )
    args = parser.parse_args()

    source = args.file or _latest_cluster_file()
    clusters = _load(source)

    metrics   = compute_metrics(clusters)
    suspicious = find_suspicious(clusters, metrics)

    print_report(metrics, suspicious, source)

    if args.save:
        out_path = source.parent / "suspicious_clusters.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(suspicious, f, ensure_ascii=False, indent=2)
        print(f"저장 완료: {out_path}")


if __name__ == "__main__":
    main()
