
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from urllib.parse import urlparse
import subprocess
import shutil

app = FastAPI(title="Deplexo Audio Engine")

SAMPLE_RATE = 24000
CHANNELS = 2
CHUNK_SIZE = 19200


class StreamRequest(BaseModel):
    source: HttpUrl


@app.get("/")
def home():
    return {
        "engine": "Deplexo Audio Engine",
        "status": "online",
        "endpoint": "/decode/stream"
    }


@app.post("/decode/stream")
def stream_pcm(request: StreamRequest):
    source = str(request.source)
    parsed = urlparse(source)

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "Alleen HTTP/HTTPS-bronnen zijn toegestaan")

    if not shutil.which("ffmpeg"):
        raise HTTPException(500, "FFmpeg is niet geïnstalleerd")

    command = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-i", source,
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ar", str(SAMPLE_RATE),
        "-ac", str(CHANNELS),
        "pipe:1"
    ]

    def generate():
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        try:
            while True:
                chunk = process.stdout.read(CHUNK_SIZE)

                if not chunk:
                    break

                yield chunk

            code = process.wait(timeout=10)

            if code != 0:
                print("FFmpeg stopte met foutcode:", code)

        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

            if process.stdout:
                process.stdout.close()

    return StreamingResponse(
        generate(),
        media_type="application/octet-stream",
        headers={
            "X-Audio-Format": "s16le",
            "X-Sample-Rate": str(SAMPLE_RATE),
            "X-Channels": str(CHANNELS),
            "Cache-Control": "no-cache"
        }
    )
