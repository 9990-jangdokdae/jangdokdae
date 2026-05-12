"""JSON 직렬화 및 파일 입출력 유틸리티."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def to_json_safe(value: Any) -> Any:
    """json.dump가 pandas/numpy 타입을 직접 처리하지 못하므로 기본 Python 타입으로 변환합니다."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def dataframe_to_records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    """DataFrame을 JSON 직렬화 가능한 list[dict] 형태로 변환합니다."""
    if df is None or df.empty:
        return []
    return [
        {key: to_json_safe(value) for key, value in row.items()}
        for row in df.to_dict(orient="records")
    ]


def save_json(data: Any, path: str | Path) -> None:
    """한글을 포함한 데이터를 UTF-8 JSON 파일로 저장합니다. 상위 디렉터리가 없으면 자동 생성합니다."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
