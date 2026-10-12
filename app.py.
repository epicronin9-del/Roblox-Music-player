
import os
import time
from threading import Lock

from flask import Flask, jsonify, request

app = Flask(__name__)

API_TOKEN = os.environ.get("MUSIC_API_TOKEN", "")

TRACKS = {
    1: "1234567890",
    2: "1234567891",
    3: "1234567892",
    4: "1234567893",
    5: "1234567894",
    6: "1234567895",
}

state = {
    "status": "stopped",
    "track": None,
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
        "status": "online"
    })


@app.get("/health")
def health():
    return jsonify({"status": "online"})


@app.get("/tracks")
def get_tracks():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify({
        "tracks": [
            {"number": number, "audio_id": audio_id}
            for number, audio_id in TRACKS.items()
        ]
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
    action = data.get("action")

    with state_lock:
        if action == "play":
            number = data.get("track")

            if type(number) is not int or number not in TRACKS:
                return jsonify({"error": "Invalid track"}), 400

            state["track"] = number
            state["status"] = "playing"

        elif action == "pause":
            if state["track"] is None:
                return jsonify({"error": "No track selected"}), 409
            state["status"] = "paused"

        elif action == "resume":
            if state["track"] is None:
                return jsonify({"error": "No track selected"}), 409
            state["status"] = "playing"

        elif action == "stop":
            state["status"] = "stopped"
            state["track"] = None

        else:
            return jsonify({"error": "Unknown action"}), 400

        state["updated_at"] = time.time()

        return jsonify({
            "success": True,
            "state": state.copy()
        })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080"))
    )
