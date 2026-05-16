from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .api.routes.report import router as report_router
from .core.config import settings


app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(report_router)


def main() -> None:
    uvicorn.run("report_backend.main:app", host="127.0.0.1", port=8000, reload=False)
