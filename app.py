
import os
import hmac
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="Deplexo Roblox Music API")

API_KEY = os.getenv("API_KEY")


class TrackRequest(BaseModel):
    url: HttpUrl


def verify_api_key(x_api_key: str | None):
    if not API_KEY or not x_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/")
def home():
    return {"status": "online", "service": "Deplexo Music API"}


@app.get("/health")
def health():
    return {"status": "online"}


@app.post("/track")
def track_info(
    request: TrackRequest,
    x_api_key: str | None = Header(default=None),
):
    verify_api_key(x_api_key)

    url = str(request.url)
    host = (request.url.host or "").lower()

    if host not in ("soundcloud.com", "www.soundcloud.com"):
        raise HTTPException(
            status_code=400,
            detail="Gebruik een geldige SoundCloud-link."
        )

    return {
        "status": "success",
        "source": "SoundCloud",
        "url": url,
        "title": None,
        "playable_in_roblox": False,
        "message": (
            "API-authenticatie geslaagd. "
            "Metadata en Roblox-compatibele audio moeten nog worden aangesloten."
        ),
    }
