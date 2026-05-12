"""날짜/시간 처리 유틸리티."""

from datetime import datetime


def parse_datetime(value: str | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str | None:
    """ISO 8601 문자열을 지정 형식 문자열로 변환합니다. 파싱 실패 시 원본 반환."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).strftime(fmt)
    except ValueError:
        return value


def compact_to_iso_date(value: str | None) -> str | None:
    """YYYYMMDD 형식을 YYYY-MM-DD로 변환합니다. 이미 변환된 값이면 그대로 반환."""
    if not value or len(value) != 8 or "-" in value:
        return value
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"
