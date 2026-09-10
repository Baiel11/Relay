from fastapi import FastAPI
from contextlib import asynccontextmanager

from backend.app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
