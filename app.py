
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
    version="2.1.0",
)

API_KEY = os.getenv("MUSIC_API_KEY", "").strip()

ALLOWED_HOSTS = {
    "soundcloud.com",
    "www.soundcloud.com",
    "m.soundcloud.com",
    "on.soundcloud.com",
}


class TrackRequest(BaseModel):
    url: HttpUrl


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Deplexo Audio API",
        "version": "2.1.0",
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
    if not API_KEY:
        logger.error("MUSIC_API_KEY ontbreekt.")
        raise HTTPException(
            status_code=503,
            detail="Serverconfiguratie ontbreekt.",
        )

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

    if host not in ALLOWED_HOSTS:
        raise HTTPException(
            status_code=400,
            detail="Alleen SoundCloud-links zijn toegestaan.",
        )

    # De decoder wordt bewust niet met de pagina-URL aangeroepen:
    # een SoundCloud-pagina is niet hetzelfde als een audiostream.
    logger.info("SoundCloud-link ontvangen; geen audio afgespeeld.")

    return {
        "status": "received",
        "url": url,
        "source": "SoundCloud",
        "decoder_available": False,
        "playable_in_roblox": False,
        "audio_asset_id": None,
        "message": (
            "Link ontvangen. De audiobron en Roblox-audio-uitvoer "
            "zijn nog niet gekoppeld."
        ),
    }
