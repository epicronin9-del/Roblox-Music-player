
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
    return {"status": "online", "service": "Deplexo Audio API"}


@app.get("/health")
def health():
    return {"status": "online"}


@app.post("/track")
def get_track(
    request: TrackRequest,
    x_api_key: str = Header(default="", alias="x-api-key"),
):
    # Controleer de API-key die je bij Deplexo als environment variable instelt.
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API_KEY is niet ingesteld op de server",
        )

    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Ongeldige API-key",
        )

    url = str(request.url)

    # Dit endpoint geeft alleen metadata/status terug.
    # Een SoundCloud-link is niet automatisch afspeelbaar in Roblox.
    return {
        "status": "received",
        "url": url,
        "playable_in_roblox": False,
        "message": (
            "Link ontvangen. Gebruik voor afspelen een "
            "audioasset die door Roblox wordt ondersteund."
        ),
    }
