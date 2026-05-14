"""뉴스 기사 클러스터링 모듈."""

import logging

import hdbscan
import numpy as np
import umap

from apps.src.exceptions.processing_exceptions import ClusterError

logger = logging.getLogger(__name__)


class NewsClusterer:
    """UMAP 차원 축소 + HDBSCAN 클러스터링.

    단독 기사(노이즈)는 버리지 않고 singleton 클러스터로 보존한다.

    Args:
        min_cluster_size: 클러스터 최소 기사 수.
        min_samples: 노이즈 판정 민감도. 낮을수록 더 많은 기사가 클러스터에 포함.
        umap_components: UMAP 축소 목표 차원.
    """

    def __init__(
        self,
        min_cluster_size: int = 2,
        min_samples: int = 1,
        umap_components: int = 5,
    ) -> None:
        """클러스터링 하이퍼파라미터(최소 클러스터 크기, 노이즈 민감도, UMAP 차원)를 초기화합니다."""
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.umap_components = umap_components

    def cluster(self, articles: list[dict]) -> list[dict]:
        """기사 목록을 클러스터링하고 결과를 반환합니다.

        Args:
            articles: embedding 필드를 포함한 기사 목록.

        Returns:
            클러스터 목록. 멀티 클러스터(size 내림차순) → singleton(published_date 순).
            각 기사에서 embedding 필드는 제거됩니다.
        """
        embeddings = np.array([a["embedding"] for a in articles], dtype=np.float32)

        reduced = self._reduce(embeddings)
        labels = self._hdbscan(reduced)

        n_noise = int((labels == -1).sum())
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

        return self._build_clusters(articles, embeddings, labels)

    def _reduce(self, embeddings: np.ndarray) -> np.ndarray:
        """UMAP으로 임베딩 차원을 umap_components로 축소합니다."""
        reducer = umap.UMAP(
            n_components=self.umap_components,
            metric="cosine",
            random_state=42,
        )
        try:
            return reducer.fit_transform(embeddings)
        except Exception as exc:
            raise ClusterError(str(exc), articles_count=len(embeddings), stage="umap") from exc

    def _hdbscan(self, embeddings: np.ndarray) -> np.ndarray:
        """HDBSCAN으로 클러스터 레이블 배열을 반환합니다. 노이즈는 -1."""
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            metric="euclidean",
        )
        try:
            return clusterer.fit_predict(embeddings)
        except Exception as exc:
            raise ClusterError(str(exc), articles_count=len(embeddings), stage="hdbscan") from exc

    def _build_clusters(
        self,
        articles: list[dict],
        embeddings: np.ndarray,
        labels: np.ndarray,
    ) -> list[dict]:
        """레이블 배열을 바탕으로 멀티 클러스터와 singleton을 조합한 클러스터 목록을 생성합니다."""
        cluster_map: dict[int, list[int]] = {}
        for i, label in enumerate(labels):
            cluster_map.setdefault(int(label), []).append(i)

        clusters: list[dict] = []
        next_id = 1

        for label, idxs in sorted(
            ((lbl, idxs) for lbl, idxs in cluster_map.items() if lbl != -1),
            key=lambda x: -len(x[1]),
        ):
            clusters.append(self._make_cluster(next_id, idxs, articles, embeddings, is_singleton=False))
            next_id += 1

        for i in (cluster_map.get(-1) or []):
            clusters.append(self._make_cluster(next_id, [i], articles, embeddings, is_singleton=True))
            next_id += 1
        return clusters

    def _make_cluster(
        self,
        cluster_id: int,
        idxs: list[int],
        articles: list[dict],
        embeddings: np.ndarray,
        is_singleton: bool,
    ) -> dict:
        """기사 인덱스 목록으로 클러스터 dict를 생성하고 centroid 유사도 기준으로 정렬합니다."""
        cluster_embeddings = embeddings[idxs]
        centroid = cluster_embeddings.mean(axis=0)
        centroid_norm = centroid / (np.linalg.norm(centroid) + 1e-10)

        cluster_articles = []
        for i in idxs:
            emb = embeddings[i]
            similarity = float(np.dot(emb, centroid_norm))
            article = dict(articles[i])
            article.pop("embedding", None)
            article["similarity_to_centroid"] = round(similarity, 4)
            cluster_articles.append(article)

        cluster_articles.sort(key=lambda a: -a["similarity_to_centroid"])

        return {
            "cluster_id": cluster_id,
            "size": len(idxs),
            "is_singleton": is_singleton,
            "articles": cluster_articles,
        }
