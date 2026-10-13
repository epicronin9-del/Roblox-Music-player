import os
import hmac
import logging
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, HttpUrl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("deplexo")

app = FastAPI(
    title="Deplexo Audio API",
    version="2.0.0",
)

API_KEY = os.getenv("MUSIC_API_KEY", "").strip()


class TrackRequest(BaseModel):
    url: HttpUrl


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Deplexo Audio API",
        "version": "2.0.0",
    }


@app.get("/health")
def health():
    return {
        "status": "online",
        "api_key_configured": bool(API_KEY),
    }


@app.post("/track")
def track(
    request: TrackRequest,
    x_api_key: str = Header(default="", alias="x-api-key"),
):
    # Controleer of de serverconfiguratie compleet is.
    if not API_KEY:
        logger.error("API_KEY ontbreekt in de serverconfiguratie.")
        raise HTTPException(
            status_code=503,
            detail="Serverconfiguratie ontbreekt: stel API_KEY in.",
        )

    # Controleer de sleutel zonder deze te loggen.
    if not hmac.compare_digest(x_api_key.strip(), API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Ongeldige API-sleutel.",
        )

    url = str(request.url)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if parsed.scheme != "https":
        raise HTTPException(
            status_code=400,
            detail="Gebruik een HTTPS-link.",
        )

    if host not in {
        "soundcloud.com",
        "www.soundcloud.com",
        "m.soundcloud.com",
        "on.soundcloud.com",
    }:
        raise HTTPException(
            status_code=400,
            detail="Deze API accepteert momenteel alleen SoundCloud-links.",
        )

    logger.info("Track-URL ontvangen; de URL wordt niet als audio afgespeeld.")

    return {
        "status": "received",
        "url": url,
        "source": "SoundCloud",
        "playable_in_roblox": False,
        "title": None,
        "audio_asset_id": None,
        "message": (
            "Link ontvangen. Voor Roblox-weergave is een "
            "Roblox-compatibele audio-asset nodig."
        ),
    }
