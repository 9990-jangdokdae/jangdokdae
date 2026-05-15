"""장독대 FastAPI 앱 진입점."""

import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.src.api.auth import router as auth_router
from apps.src.api.issue_docent import router as issue_docent_router
from apps.src.api.users import router as user_router


def create_app() -> FastAPI:
    app = FastAPI(title="장독대 API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.environ.get("CLIENT_URL", "http://localhost:3000")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(user_router, prefix="/api/v1/user", tags=["user"])
    app.include_router(issue_docent_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
