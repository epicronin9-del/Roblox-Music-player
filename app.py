import os
import hmac

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="Roblox Music API")

# Stel API_KEY in bij de omgevingsvariabelen van je hostingdienst.
EXPECTED_API_KEY = os.getenv("API_KEY")


class TrackRequest(BaseModel):
    url: HttpUrl


def verify_api_key(x_api_key: str | None):
    if not EXPECTED_API_KEY or not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )

    if not hmac.compare_digest(x_api_key, EXPECTED_API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )


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
    host = request.url.host.lower()

    if host not in ("soundcloud.com", "www.soundcloud.com"):
        raise HTTPException(
            status_code=400,
            detail="Alleen SoundCloud-links zijn toegestaan.",
        )

    # Deze route valideert de link, maar haalt nog geen
    # SoundCloud-metadata op en levert geen audioasset.
    return {
        "message": "API-authenticatie geslaagd. Metadata-provider moet nog worden aangesloten.",
        "source": "SoundCloud",
        "playable_in_roblox": False,
        "url": url,
        "title": None,
    }
