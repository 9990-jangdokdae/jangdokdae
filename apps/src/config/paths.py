"""프로젝트 경로 상수. 경로가 필요한 모든 모듈은 여기서 import합니다."""

from pathlib import Path

# local/ (저장소 루트)
REPO_ROOT = Path(__file__).resolve().parents[3]

# local/apps/
APPS_DIR = REPO_ROOT / "apps"

DATA_DIR    = APPS_DIR / "data"
PROMPTS_DIR = APPS_DIR / "src" / "prompts"
