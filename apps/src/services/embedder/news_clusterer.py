"""뉴스 클러스터링 모듈.

poc.ipynb의 "임베딩 & 클러스터링" 셀을 함수화했습니다.
기사 embedding을 AgglomerativeClustering으로 이슈별 묶음으로 만들고, 각 클러스터의
중심점에 가장 가까운 기사를 대표기사로 표시합니다.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

from apps.src.services.preprocessor.news_preprocessor import normalize_news_columns

logger = logging.getLogger(__name__)


def cluster_news_embeddings(
    df: pd.DataFrame,
    embeddings: np.ndarray,
    distance_threshold: float = 0.35,
) -> pd.DataFrame:
    """embedding 배열을 기준으로 cluster_id를 부여하고 대표기사 순위를 계산합니다.

    distance_threshold가 낮을수록 더 엄격하게 묶이고, 높을수록 더 큰 클러스터가
    만들어집니다. 현재 기본값 0.35는 노트북 POC에서 사용한 값입니다.
    """
    out = normalize_news_columns(df).copy()
    logger.info("[cluster] fitting agglomerative rows=%s threshold=%s", len(out), distance_threshold)
    clustering_model = AgglomerativeClustering(
        n_clusters=None,
        metric="cosine",
        linkage="average",
        distance_threshold=distance_threshold,
    )
    out["cluster_id"] = clustering_model.fit_predict(embeddings)
    logger.info("[cluster] assigned clusters=%s", out["cluster_id"].nunique())
    return rank_articles_in_cluster(out, embeddings)


def rank_articles_in_cluster(df: pd.DataFrame, embeddings: np.ndarray) -> pd.DataFrame:
    """클러스터별 크기, 중심점 유사도, 클러스터 내 순위를 DataFrame에 추가합니다.

    rank_in_cluster == 0인 기사가 해당 클러스터의 대표기사입니다.
    """
    out = df.copy()
    out["cluster_size"] = 0
    out["rank_in_cluster"] = -1
    out["similarity_to_centroid"] = np.nan
    out["is_representative"] = False

    logger.info("[cluster] ranking clusters=%s", out["cluster_id"].nunique())
    for cid in out["cluster_id"].unique():
        cluster_idx = out[out["cluster_id"] == cid].index.to_numpy()
        cluster_size = len(cluster_idx)
        logger.info("[cluster] rank cluster_id=%s size=%s", cid, cluster_size)
        out.loc[cluster_idx, "cluster_size"] = cluster_size

        cluster_embeddings = embeddings[cluster_idx]
        centroid = np.mean(cluster_embeddings, axis=0).reshape(1, -1)
        sims = cosine_similarity(centroid, cluster_embeddings)[0]
        sorted_local_indices = np.argsort(sims)[::-1]

        for rank, local_idx in enumerate(sorted_local_indices):
            global_idx = cluster_idx[local_idx]
            out.loc[global_idx, "rank_in_cluster"] = rank
            out.loc[global_idx, "similarity_to_centroid"] = sims[local_idx]

        representative_global_idx = cluster_idx[sorted_local_indices[0]]
        out.loc[representative_global_idx, "is_representative"] = True

    return out


def select_representative_articles(df: pd.DataFrame) -> pd.DataFrame:
    """클러스터 대표기사만 반환합니다."""
    return df[df["is_representative"]].copy()


def summarize_top_clusters(
    df: pd.DataFrame,
    top_n_clusters: int = 5,
    top_k_articles: int = 5,
    min_cluster_size: int = 2,
) -> pd.DataFrame:
    """상위 클러스터의 대표/주요 기사 목록만 요약 DataFrame으로 반환합니다."""
    valid = (
        df[["cluster_id", "cluster_size"]]
        .drop_duplicates()
        .query("cluster_size >= @min_cluster_size")
        .sort_values("cluster_size", ascending=False)
        .head(top_n_clusters)
    )
    top_cluster_ids = valid["cluster_id"].tolist()

    rows = []
    for cid in top_cluster_ids:
        cluster_articles = (
            df[df["cluster_id"] == cid]
            .sort_values("rank_in_cluster")
            .head(top_k_articles)
        )
        for _, row in cluster_articles.iterrows():
            rows.append({
                "cluster_id": cid,
                "cluster_size": int(row["cluster_size"]),
                "rank_in_cluster": int(row["rank_in_cluster"]),
                "article_idx": int(row.name),
                "similarity_to_centroid": float(row["similarity_to_centroid"]),
                "is_representative": bool(row["is_representative"]),
                "news_title": row["news_title"],
            })

    return pd.DataFrame(rows)


def get_top_cluster_articles(
    df: pd.DataFrame,
    top_n_clusters: int = 5,
    top_k_articles: int = 5,
    min_cluster_size: int = 2,
) -> pd.DataFrame:
    """클러스터 크기 기준 상위 N개에서 각 클러스터별 상위 K개 기사만 가져옵니다."""
    top_cluster_ids = (
        df[["cluster_id", "cluster_size"]]
        .drop_duplicates()
        .query("cluster_size >= @min_cluster_size")
        .sort_values("cluster_size", ascending=False)
        .head(top_n_clusters)["cluster_id"]
        .tolist()
    )

    return (
        df[df["cluster_id"].isin(top_cluster_ids)]
        .sort_values(
            ["cluster_size", "cluster_id", "rank_in_cluster"],
            ascending=[False, True, True],
        )
        .groupby("cluster_id", group_keys=False)
        .head(top_k_articles)
        .copy()
    )


assign_clusters = cluster_news_embeddings
add_cluster_rankings = rank_articles_in_cluster
