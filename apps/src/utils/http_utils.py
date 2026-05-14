"""HTTP 요청 관련 유틸리티."""

import time
from typing import Any, Callable

import requests


def with_retry(
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
    if retries < 1:
        raise ValueError(f"retries must be >= 1, got {retries}")
    last_error: BaseException = RuntimeError("unreachable")
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except exceptions as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(sleep_sec * (2 ** attempt))
    raise last_error
