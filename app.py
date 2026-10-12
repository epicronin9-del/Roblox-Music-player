
import os
import re
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

API_TOKEN = os.environ.get("MUSIC_API_TOKEN", "")

# Eenvoudige serverstatus en gedeelde spelerstatus
player_state = {
    "status": "stopped",
    "current_track": None,
    "volume": 0.5,
}

# Voeg hier zelf tracks aan toe voor de /search-route.
TRACKS = []


def authorized():
    if not API_TOKEN:
        return False

    return (
        request.headers.get("Authorization")
        == f"Bearer {API_TOKEN}"
    )


def validate_soundcloud_url(url):
    if not isinstance(url, str) or len(url) > 500:
        return False

    parsed = urlparse(url)

    if parsed.scheme != "https":
        return False

    if parsed.hostname not in {
        "soundcloud.com",
        "www.soundcloud.com",
    }:
        return False

    if parsed.port is not None or parsed.username or parsed.password:
        return False

    if not re.fullmatch(r"/[\w-]+(?:/[\w-]+)*", parsed.path):
        return False

    return True


@app.get("/")
def home():
    return jsonify({
        "name": "Roblox Music Player API",
        "status": "online",
        "features": [
            "health",
            "search",
            "state",
            "command",
            "track",
        ],
    })


@app.get("/health")
def health():
    return jsonify({"status": "online"})


@app.get("/search")
def search():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    query = request.args.get("q", "").strip().lower()

    if not query:
        return jsonify({"tracks": TRACKS})

    matches = [
        track for track in TRACKS
        if query in track.get("title", "").lower()
        or query in track.get("artist", "").lower()
    ]

    return jsonify({"tracks": matches})


@app.get("/state")
def get_state():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify(player_state)


@app.post("/command")
def command():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    action = data.get("action")

    if not isinstance(action, str):
        return jsonify({"error": "Missing action"}), 400

    action = action.upper()

    if action == "PLAY":
        player_state["status"] = "playing"
        player_state["current_track"] = data.get("track")

    elif action == "PAUSE":
        player_state["status"] = "paused"

    elif action == "RESUME":
        player_state["status"] = "playing"

    elif action == "STOP":
        player_state["status"] = "stopped"
        player_state["current_track"] = None

    elif action == "VOLUME":
        volume = data.get("volume")

        if not isinstance(volume, (int, float)) or isinstance(volume, bool):
            return jsonify({"error": "Invalid volume"}), 400

        if not 0 <= volume <= 1:
            return jsonify({"error": "Volume must be between 0 and 1"}), 400

        player_state["volume"] = float(volume)

    else:
        return jsonify({"error": "Unknown action"}), 400

    return jsonify({
        "status": "ok",
        "state": player_state,
    })


@app.post("/track")
def track():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    url = data.get("url")

    if not validate_soundcloud_url(url):
        return jsonify({
            "error": "Invalid SoundCloud URL",
        }), 400

    try:
        response = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=False,
        )

        if response.status_code != 200:
            return jsonify({
                "error": "SoundCloud page unavailable",
                "status_code": response.status_code,
            }), 502

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "html.parser")

        def meta_content(property_name):
            element = soup.find(
                "meta",
                property=property_name,
            )
            return element.get("content") if element else None

        title = meta_content("og:title")
        canonical_url = meta_content("og:url") or url

        return jsonify({
            "title": title,
            "url": canonical_url,
            "source": "SoundCloud",
            "playable_in_roblox": False,
            "message": (
                "Metadata only. A Roblox-compatible audio asset "
                "is required for playback."
            ),
        })

    except requests.RequestException:
        return jsonify({
            "error": "Could not reach SoundCloud",
        }), 502


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
    )
