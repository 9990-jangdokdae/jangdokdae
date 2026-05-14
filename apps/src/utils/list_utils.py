"""리스트·컬렉션 처리 유틸리티."""

import json
from typing import Any, Callable, TypeVar

import numpy as np
import pandas as pd

T = TypeVar("T")


def unique_by(items: list[T], key: Callable[[T], Any]) -> list[T]:
    """key 함수로 동일 값을 가진 항목을 제거하되 원래 순서를 유지합니다."""
    seen: set = set()
    result = []
    for item in items:
        k = key(item)
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result


def unique_strings(values: list[Any], limit: int | None = None) -> list[str]:
    """문자열 리스트에서 공백/빈 값 제거, 순서 보존 중복 제거, 개수 제한을 수행합니다."""
    cleaned = [
        value.strip()
        for value in values
        if isinstance(value, str) and value.strip()
    ]
    deduped = list(dict.fromkeys(cleaned))
    return deduped[:limit] if limit is not None else deduped


def ensure_list(value: Any) -> list[Any]:
    """어떤 타입이든 항상 list를 반환합니다. JSON 역직렬화 후 타입이 불일치할 때 씁니다."""
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
