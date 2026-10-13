
import os
import hmac

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="Deplexo Audio API")

API_KEY = os.getenv("API_KEY", "")


class TrackRequest(BaseModel):
    url: HttpUrl


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Deplexo Audio API",
    }


@app.get("/health")
def health():
    return {"status": "online"}


@app.post("/track")
def track(
    request: TrackRequest,
    x_api_key: str = Header(default="", alias="x-api-key"),
):
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="API_KEY is not configured",
        )

    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )

    return {
        "status": "received",
        "url": str(request.url),
        "playable_in_roblox": False,
        "message": (
            "URL received. Roblox-compatible audio "
            "is required for playback."
        ),
    }
