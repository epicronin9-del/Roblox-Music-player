
import os
import time
from threading import Lock
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from flask import Flask, jsonify, request

app = Flask(__name__)

API_TOKEN = os.environ.get("MUSIC_API_TOKEN", "")
SOUNDCLOUD_ACCESS_TOKEN = os.environ.get(
    "SOUNDCLOUD_ACCESS_TOKEN", ""
)

state = {
    "status": "stopped",
    "track": None,
    "title": None,
    "updated_at": time.time(),
}

state_lock = Lock()


def authorized():
    return (
        bool(API_TOKEN)
        and request.headers.get("Authorization")
        == f"Bearer {API_TOKEN}"
    )


@app.get("/")
def home():
    return jsonify({
        "name": "Roblox Music Player API",
        "status": "online",
        "features": ["health", "search", "state", "command"],
    })


@app.get("/health")
def health():
    return jsonify({"status": "online"})


@app.get("/search")
def search_soundcloud():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    query = request.args.get("q", "").strip()

    if not query:
        return jsonify({"error": "Geef een titel op via ?q=..."}), 400

    if len(query) > 150:
        return jsonify({"error": "Zoekterm is te lang"}), 400

    if not SOUNDCLOUD_ACCESS_TOKEN:
        return jsonify({
            "error": "SOUNDCLOUD_ACCESS_TOKEN is niet ingesteld"
        }), 503

    params = urlencode({
        "q": query,
        "limit": 10,
    })

    req = Request(
        f"https://api.soundcloud.com/tracks?{params}",
        headers={
            "Authorization": f"OAuth {SOUNDCLOUD_ACCESS_TOKEN}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urlopen(req, timeout=12) as response:
            import json
            payload = json.loads(response.read().decode("utf-8"))

    except HTTPError as exc:
        if exc.code == 401:
            message = "SoundCloud-token ongeldig of verlopen"
        elif exc.code == 429:
            message = "SoundCloud heeft te veel verzoeken ontvangen"
        else:
            message = f"SoundCloud API-fout: {exc.code}"

        return jsonify({"error": message}), 502

    except (URLError, TimeoutError, ValueError, OSError):
        return jsonify({
            "error": "SoundCloud kon niet worden bereikt"
        }), 502

    results = []

    for track in payload.get("collection", []):
        artist = track.get("user") or {}

        results.append({
            "title": track.get("title"),
            "artist": artist.get("username"),
            "url": track.get("permalink_url"),
            "soundcloud_id": track.get("id"),
            "duration_ms": track.get("duration"),
        })

    return jsonify({
        "query": query,
        "count": len(results),
        "results": results,
    })


@app.get("/state")
def get_state():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    with state_lock:
        return jsonify(state.copy())


@app.post("/command")
def command():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    action = str(data.get("action", "")).lower()

    with state_lock:
        if action == "play":
            # Alleen een bestaande, echte Roblox-audio-ID accepteren.
            audio_id = str(data.get("audio_id", "")).strip()

            if not audio_id.isdigit():
                return jsonify({
                    "error": "Geef een geldige Roblox-audioasset-ID op"
                }), 400

            state["track"] = audio_id
            state["title"] = str(data.get("title", ""))[:150]
            state["status"] = "playing"

        elif action == "pause":
            if state["track"] is None:
                return jsonify({"error": "Geen track geselecteerd"}), 409
            state["status"] = "paused"

        elif action == "resume":
            if state["track"] is None:
                return jsonify({"error": "Geen track geselecteerd"}), 409
            state["status"] = "playing"

        elif action == "stop":
            state["status"] = "stopped"
            state["track"] = None
            state["title"] = None

        else:
            return jsonify({"error": "Onbekende actie"}), 400

        state["updated_at"] = time.time()
        return jsonify({"success": True, "state": state.copy()})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
    )
