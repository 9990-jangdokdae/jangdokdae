"""공통 유틸리티 함수 모음.

외부 API retry, JSON 직렬화 보정, DataFrame records 변환처럼 여러 모듈에서 반복해서
쓰는 작은 함수를 모았습니다.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import requests

def retry_call(
    fn: Callable[..., Any],
    *args: Any,
    retries: int = 3,
    sleep_sec: float = 1.5,
    exceptions: tuple[type[BaseException], ...] = (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        ConnectionError,
        TimeoutError,
    ),
    **kwargs: Any,
) -> Any:
    """일시적인 네트워크 오류를 재시도합니다.

    DART/KRX/Yahoo처럼 서버가 연결을 먼저 끊는 일이 있는 API 호출을 감쌀 때 씁니다.
    모든 재시도가 실패하면 마지막 예외를 그대로 다시 발생시킵니다.
    """
    last_error = None
    for i in range(retries):
        try:
            return fn(*args, **kwargs)
        except exceptions as exc:
            last_error = exc
            time.sleep(sleep_sec * (i + 1))
    raise last_error


def to_jsonable(value: Any) -> Any:
    """pandas/numpy 값을 json.dump가 처리 가능한 기본 Python 타입으로 바꿉니다."""
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
        {key: to_jsonable(value) for key, value in row.items()}
        for row in df.to_dict(orient="records")
    ]


def dump_json(data: Any, path: str | Path) -> None:
    """한글이 깨지지 않도록 ensure_ascii=False로 JSON 파일을 저장합니다."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def dedupe_strings(values: list[Any], limit: int | None = None) -> list[str]:
    """문자열 리스트에서 공백/빈 값 제거, 순서 보존 중복 제거, 개수 제한을 수행합니다."""
    cleaned = [
        value.strip()
        for value in values
        if isinstance(value, str) and value.strip()
    ]
    deduped = list(dict.fromkeys(cleaned))
    return deduped[:limit] if limit is not None else deduped


def coerce_list(value: Any) -> list[Any]:
    """pickle/json을 오가며 달라진 리스트형 값을 Python list로 맞춥니다."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return [text]
        return parsed if isinstance(parsed, list) else [parsed]
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    return [value]

