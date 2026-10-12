
import os
import re
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

API_TOKEN = os.environ.get("MUSIC_API_TOKEN", "")


def authorized():
    return (
        bool(API_TOKEN)
        and request.headers.get("Authorization")
        == f"Bearer {API_TOKEN}"
    )


def validate_url(url):
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

    if not re.fullmatch(r"/[\w-]+(?:/[\w-]+)*", parsed.path):
        return False

    return True


@app.get("/")
def home():
    return jsonify({
        "name": "Roblox Music Server",
        "status": "online",
    })


@app.get("/health")
def health():
    return jsonify({"status": "online"})


@app.post("/track")
def track():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    url = data.get("url")

    if not validate_url(url):
        return jsonify({
            "error": "Ongeldige SoundCloud-URL"
        }), 400

    try:
        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            allow_redirects=False,
        )

        if response.status_code != 200:
            return jsonify({
                "error": "SoundCloud-pagina is niet beschikbaar",
                "status_code": response.status_code,
            }), 502

        # Lees alleen metadata uit de openbare HTML-pagina.
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "html.parser")

        title = None
        artist = None

        og_title = soup.find(
            "meta",
            property="og:title",
        )

        if og_title:
            title = og_title.get("content")

        og_url = soup.find(
            "meta",
            property="og:url",
        )

        canonical_url = (
            og_url.get("content")
            if og_url
            else url
        )

        if title and " by " in title:
            title, artist = title.rsplit(" by ", 1)

        return jsonify({
            "title": title,
            "artist": artist,
            "url": canonical_url,
            "source": "SoundCloud",
            "playable_in_roblox": False,
            "message": (
                "Trackinformatie opgehaald. "
                "Een compatibele Roblox-audiobron is nodig om af te spelen."
            ),
        })

    except requests.RequestException:
        return jsonify({
            "error": "SoundCloud kon niet worden bereikt"
        }), 502


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
    )
