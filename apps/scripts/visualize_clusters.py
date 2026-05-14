"""클러스터링 결과 시각화 스크립트.

data/날짜_시간/viz/ 폴더에 PNG 파일 3개를 생성합니다.
  - scatter.png    : TF-IDF + UMAP 2D 산점도 (클러스터별 색상)
  - sizes.png      : 클러스터별 기사 수 막대 차트
  - cohesion.png   : 클러스터별 응집도 막대 차트

사용법:
    python -m apps.scripts.visualize_clusters
    python -m apps.scripts.visualize_clusters --file data/20260511_230338/clusters_final.json
"""

import argparse
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import umap
from sklearn.feature_extraction.text import TfidfVectorizer

from apps.src.config.paths import DATA_DIR

matplotlib.use("Agg")

# ── 한글 폰트 설정 ─────────────────────────────────────────────────────────
def _setup_font() -> None:
    candidates = [
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/NanumGothic.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            fm.fontManager.addfont(path)
            prop = fm.FontProperties(fname=path)
            matplotlib.rcParams["font.family"] = prop.get_name()
            break
    matplotlib.rcParams["axes.unicode_minus"] = False


# ── 파일 탐지 ──────────────────────────────────────────────────────────────
def _latest_cluster_file() -> Path:
    runs = sorted((p for p in DATA_DIR.iterdir() if p.is_dir()), reverse=True)
    for run in runs:
        for name in ("clusters_final.json", "clusters_extracted.json", "news_clusters.json"):
            candidate = run / name
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"클러스터 파일을 찾을 수 없습니다: {DATA_DIR}")


def _load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── 2D 좌표 계산 (TF-IDF + UMAP) ──────────────────────────────────────────
def _embed_2d(articles: list[dict]) -> np.ndarray:
    """기사 제목에 TF-IDF 문자 n-gram을 적용하고 UMAP으로 2D 축소합니다."""
    titles = [a["title"] for a in articles]
    tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), max_features=3000)
    vectors = tfidf.fit_transform(titles).toarray()
    reducer = umap.UMAP(n_components=2, metric="cosine", random_state=42, n_neighbors=5)
    return reducer.fit_transform(vectors)


# ── 데이터 평탄화 ──────────────────────────────────────────────────────────
def _flatten(clusters: list[dict]) -> tuple[list[dict], list[int], list[bool]]:
    """(기사 목록, 클러스터 id 목록, singleton 여부 목록)을 반환합니다."""
    articles, cluster_ids, is_singletons = [], [], []
    for c in clusters:
        for a in c["articles"]:
            articles.append(a)
            cluster_ids.append(c["cluster_id"])
            is_singletons.append(c["is_singleton"])
    return articles, cluster_ids, is_singletons


# ── 클러스터 레이블 (keywords 있으면 사용) ─────────────────────────────────
def _cluster_label(c: dict) -> str:
    extraction = c.get("extraction")
    if extraction and extraction.get("keywords"):
        return f"#{c['cluster_id']} {extraction['keywords'][0]}"
    return f"#{c['cluster_id']}"


# ── 그래프 1: 2D 산점도 ────────────────────────────────────────────────────
def plot_scatter(clusters: list[dict], out: Path) -> None:
    articles, cluster_ids, is_singletons = _flatten(clusters)
    coords = _embed_2d(articles)

    multi_clusters = [c for c in clusters if not c["is_singleton"]]
    cmap = plt.get_cmap("tab20", max(len(multi_clusters), 1))
    id_to_color = {c["cluster_id"]: cmap(i) for i, c in enumerate(multi_clusters)}

    fig, ax = plt.subplots(figsize=(11, 8))

    # singleton 먼저 (배경)
    s_mask = np.array(is_singletons)
    if s_mask.any():
        ax.scatter(
            coords[s_mask, 0], coords[s_mask, 1],
            c="#cccccc", s=30, alpha=0.5, label="Singleton", zorder=1,
        )

    # 클러스터별 산점 + 레이블
    for c in multi_clusters:
        mask = np.array([cid == c["cluster_id"] for cid in cluster_ids])
        color = id_to_color[c["cluster_id"]]
        ax.scatter(
            coords[mask, 0], coords[mask, 1],
            c=[color], s=60, alpha=0.85, zorder=2,
        )
        cx, cy = coords[mask, 0].mean(), coords[mask, 1].mean()
        ax.annotate(
            _cluster_label(c), (cx, cy),
            fontsize=7.5, ha="center", va="bottom",
            color="black",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.6, lw=0),
        )

    ax.set_title("클러스터 2D 산점도  (TF-IDF + UMAP)", fontsize=13)
    ax.set_xlabel("UMAP-1")
    ax.set_ylabel("UMAP-2")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, linestyle="--", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out, dpi=150)
    plt.close(fig)


# ── 그래프 2: 클러스터 크기 막대 ──────────────────────────────────────────
def plot_sizes(clusters: list[dict], out: Path) -> None:
    multi = sorted([c for c in clusters if not c["is_singleton"]], key=lambda c: -c["size"])
    labels = [_cluster_label(c) for c in multi]
    sizes  = [c["size"] for c in multi]
    singleton_total = sum(c["size"] for c in clusters if c["is_singleton"])

    fig, ax = plt.subplots(figsize=(max(8, len(multi) * 0.7), 5))
    colors = plt.get_cmap("tab20")(np.linspace(0, 1, len(multi)))
    bars = ax.bar(labels, sizes, color=colors, edgecolor="white", linewidth=0.5)

    # singleton 합계를 별도 회색 막대로
    if singleton_total:
        ax.bar("Singleton\n(합계)", singleton_total, color="#cccccc", edgecolor="white")
        labels.append("Singleton\n(합계)")

    for bar, val in zip(bars, sizes):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                str(val), ha="center", va="bottom", fontsize=9)

    ax.set_title("클러스터별 기사 수", fontsize=13)
    ax.set_ylabel("기사 수")
    ax.set_xticks(range(len(ax.patches)))
    ax.set_xticklabels(
        [b.get_label() if hasattr(b, "get_label") else "" for b in ax.patches],
        rotation=30, ha="right", fontsize=8,
    )
    plt.xticks(range(len(labels)), labels, rotation=30, ha="right", fontsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(out, dpi=150)
    plt.close(fig)


# ── 그래프 3: 클러스터 응집도 ─────────────────────────────────────────────
def plot_cohesion(clusters: list[dict], out: Path) -> None:
    import statistics

    multi = [c for c in clusters if not c["is_singleton"]]
    data = sorted([
        (
            _cluster_label(c),
            statistics.mean(a["similarity_to_centroid"] for a in c["articles"]),
            c["size"],
        )
        for c in multi
    ], key=lambda x: -x[1])

    labels   = [d[0] for d in data]
    cohesions = [d[1] for d in data]
    sizes    = [d[2] for d in data]

    overall_mean = statistics.mean(cohesions) if cohesions else 0

    fig, ax = plt.subplots(figsize=(max(8, len(data) * 0.7), 5))
    colors = ["#4c9be8" if v >= overall_mean else "#e87c4c" for v in cohesions]
    bars = ax.bar(labels, cohesions, color=colors, edgecolor="white", linewidth=0.5)

    ax.axhline(overall_mean, color="#333333", linestyle="--", linewidth=1.2,
               label=f"전체 평균 {overall_mean:.3f}")
    ax.axhline(0.5, color="#cc4444", linestyle=":", linewidth=1,
               label="최소 기준 0.5")

    for bar, val in zip(bars, cohesions):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003,
                f"{val:.3f}", ha="center", va="bottom", fontsize=8)

    ax.set_title("클러스터별 응집도 (similarity_to_centroid 평균)", fontsize=13)
    ax.set_ylabel("응집도")
    ax.set_ylim(0, 1.05)
    plt.xticks(range(len(labels)), labels, rotation=30, ha="right", fontsize=8)
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(out, dpi=150)
    plt.close(fig)


# ── 진입점 ────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="클러스터링 결과 시각화")
    parser.add_argument("--file", type=Path, default=None,
                        help="클러스터 JSON 파일 경로 (기본: 최신 실행 자동 탐지)")
    args = parser.parse_args()

    _setup_font()

    source = args.file or _latest_cluster_file()
    clusters = _load(source)
    viz_dir = source.parent / "viz"
    viz_dir.mkdir(exist_ok=True)

    total = sum(c["size"] for c in clusters)
    multi_count = sum(1 for c in clusters if not c["is_singleton"])
    print(f"대상: {source.parent.name}/{source.name}  "
          f"(기사 {total}개 / 클러스터 {multi_count}개 + singleton)")

    print("scatter.png 생성 중...", end=" ", flush=True)
    plot_scatter(clusters, viz_dir / "scatter.png")
    print("완료")

    print("sizes.png 생성 중...", end=" ", flush=True)
    plot_sizes(clusters, viz_dir / "sizes.png")
    print("완료")

    print("cohesion.png 생성 중...", end=" ", flush=True)
    plot_cohesion(clusters, viz_dir / "cohesion.png")
    print("완료")

    print(f"\n저장 위치: {viz_dir}")


if __name__ == "__main__":
    main()
