
import os
import hmac
import shutil
import logging
import subprocess
import tempfile
import threading

from pathlib import Path
from urllib.parse import urlparse

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    UploadFile,
    File,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, HttpUrl
from starlette.background import BackgroundTask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("deplexo")

app = FastAPI(
    title="Deplexo Audio API",
    version="3.1.0",
)

API_KEY = os.getenv("MUSIC_API_KEY", "").strip()
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")

ALLOWED_HOSTS = {
    "soundcloud.com",
    "www.soundcloud.com",
    "m.soundcloud.com",
    "on.soundcloud.com",
}

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_AUDIO_SECONDS = 300

PCM_SAMPLE_RATE = 24000
PCM_CHANNELS = 2
PCM_SAMPLE_WIDTH = 2
PCM_CHUNK_SIZE = 19200

TEMP_DIR = Path(tempfile.gettempdir()) / "deplexo_audio"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class TrackRequest(BaseModel):
    url: HttpUrl


def require_api_key(x_api_key: str) -> None:
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


def cleanup_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Tijdelijk bestand kon niet worden verwijderd.")


def ffmpeg_available() -> bool:
    try:
        result = subprocess.run(
            [FFMPEG_PATH, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


async def save_upload(audio_file: UploadFile) -> tuple[Path, int]:
    input_path = None
    total_bytes = 0

    try:
        with tempfile.NamedTemporaryFile(
            prefix="input_",
            suffix=".audio",
            dir=TEMP_DIR,
            delete=False,
        ) as temp_input:
            input_path = Path(temp_input.name)

            while True:
                chunk = await audio_file.read(1024 * 1024)

                if not chunk:
                    break

                total_bytes += len(chunk)

                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Bestand is groter dan 50 MB.",
                    )

                temp_input.write(chunk)

        if total_bytes == 0:
            raise HTTPException(
                status_code=400,
                detail="Het geüploade bestand is leeg.",
            )

        return input_path, total_bytes

    except Exception:
        if input_path:
            cleanup_file(input_path)
        raise

    finally:
        await audio_file.close()


def ffmpeg_command(input_path: Path) -> list[str]:
    return [
        FFMPEG_PATH,
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(input_path),
        "-map", "0:a:0",
        "-vn",
        "-t", str(MAX_AUDIO_SECONDS),
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ar", str(PCM_SAMPLE_RATE),
        "-ac", str(PCM_CHANNELS),
        "pipe:1",
    ]


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Deplexo Audio API",
        "version": app.version,
        "phase": "PCM streaming",
    }


@app.get("/health")
def health():
    return {
        "status": "online",
        "api_key_configured": bool(API_KEY),
        "decoder": "available" if ffmpeg_available() else "unavailable",
        "decoder_engine": "FFmpeg",
        "output_format": "signed 16-bit little-endian PCM",
        "sample_rate": PCM_SAMPLE_RATE,
        "channels": PCM_CHANNELS,
        "chunk_size_bytes": PCM_CHUNK_SIZE,
        "roblox_playback_connected": False,
    }


@app.post("/track")
def track(
    request: TrackRequest,
    x_api_key: str = Header(default="", alias="x-api-key"),
):
    require_api_key(x_api_key)

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

    logger.info("SoundCloud-URL gevalideerd.")

    return {
        "status": "received",
        "url": url,
        "source": "SoundCloud",
        "decoder_available": ffmpeg_available(),
        "source_resolver_available": False,
        "playable_in_roblox": False,
        "audio_asset_id": None,
        "message": (
            "URL gevalideerd. Een SoundCloud-bronresolver "
            "is nog niet aangesloten."
        ),
    }


@app.post("/decode")
async def decode(
    audio_file: UploadFile = File(...),
    x_api_key: str = Header(default="", alias="x-api-key"),
):
    require_api_key(x_api_key)

    if not ffmpeg_available():
        raise HTTPException(
            status_code=503,
            detail="FFmpeg is niet beschikbaar.",
        )

    input_path = None
    output_path = None

    try:
        input_path, _ = await save_upload(audio_file)

        fd, output_name = tempfile.mkstemp(
            prefix="pcm_",
            suffix=".pcm",
            dir=TEMP_DIR,
        )
        os.close(fd)
        output_path = Path(output_name)

        command = ffmpeg_command(input_path)[:-1] + [
            str(output_path)
        ]

        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=90,
            check=False,
        )

        if result.returncode != 0 or not output_path.exists():
            raise HTTPException(
                status_code=422,
                detail="Audio kon niet worden gedecodeerd.",
            )

        if output_path.stat().st_size == 0:
            raise HTTPException(
                status_code=422,
                detail="Geen decodeerbare audiotrack gevonden.",
            )

        return FileResponse(
            path=output_path,
            media_type="application/octet-stream",
            filename="deplexo_audio.pcm",
            headers={
                "X-Audio-Format": "s16le",
                "X-Audio-Sample-Rate": str(PCM_SAMPLE_RATE),
                "X-Audio-Channels": str(PCM_CHANNELS),
            },
            background=BackgroundTask(
                cleanup_file, output_path
            ),
        )

    except HTTPException:
        if output_path:
            cleanup_file(output_path)
        raise

    except subprocess.TimeoutExpired:
        if output_path:
            cleanup_file(output_path)
        raise HTTPException(
            status_code=408,
            detail="Audio-decoding duurde te lang.",
        )

    except Exception:
        logger.exception("Fout tijdens audio-decoding.")
        if output_path:
            cleanup_file(output_path)
        raise HTTPException(
            status_code=500,
            detail="Interne fout tijdens audio-decoding.",
        )

    finally:
        if input_path:
            cleanup_file(input_path)


@app.post("/decode/stream")
async def decode_stream(
    audio_file: UploadFile = File(...),
    x_api_key: str = Header(default="", alias="x-api-key"),
):
    """
    Ontvang een audiobestand en stream de PCM-uitvoer
    rechtstreeks vanuit FFmpeg in blokken.
    """

    require_api_key(x_api_key)

    if not ffmpeg_available():
        raise HTTPException(
            status_code=503,
            detail="FFmpeg is niet beschikbaar.",
        )

    input_path = None

    try:
        input_path, total_bytes = await save_upload(audio_file)

    except HTTPException:
        raise

    except Exception:
        logger.exception("Upload kon niet worden opgeslagen.")
        raise HTTPException(
            status_code=500,
            detail="Upload kon niet worden opgeslagen.",
        )

    logger.info(
        "PCM-stream gestart. Upload: %s bytes.",
        total_bytes,
    )

    def generate():
        process = None

        try:
            process = subprocess.Popen(
                ffmpeg_command(input_path),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )

            if process.stdout is None:
                raise RuntimeError("FFmpeg stdout ontbreekt.")

            while True:
                chunk = process.stdout.read(PCM_CHUNK_SIZE)

                if not chunk:
                    break

                yield chunk

            exit_code = process.wait(timeout=90)

            if exit_code != 0:
                logger.error(
                    "FFmpeg eindigde met code %s.",
                    exit_code,
                )

        except Exception:
            logger.exception("PCM-stream is mislukt.")

        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                    process.wait()

                if process.stdout:
                    process.stdout.close()

            cleanup_file(input_path)
            logger.info("PCM-stream beëindigd.")

    return StreamingResponse(
        generate(),
        media_type="application/octet-stream",
        headers={
            "X-Audio-Format": "s16le",
            "X-Audio-Sample-Rate": str(PCM_SAMPLE_RATE),
            "X-Audio-Channels": str(PCM_CHANNELS),
            "X-Audio-Sample-Width": str(PCM_SAMPLE_WIDTH),
            "X-Audio-Chunk-Size": str(PCM_CHUNK_SIZE),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(cleanup_file, input_path),
    )


@app.get("/decoder-info")
def decoder_info(
    x_api_key: str = Header(default="", alias="x-api-key"),
):
    require_api_key(x_api_key)

    available = ffmpeg_available()

    return {
        "decoder": "FFmpeg",
        "available": available,
        "input": "Geüpload audiobestand",
        "output": "s16le PCM",
        "sample_rate": PCM_SAMPLE_RATE,
        "channels": PCM_CHANNELS,
        "sample_width": PCM_SAMPLE_WIDTH,
        "chunk_size": PCM_CHUNK_SIZE,
        "max_duration_seconds": MAX_AUDIO_SECONDS,
        "max_upload_bytes": MAX_UPLOAD_BYTES,
    }


@app.on_event("startup")
def startup():
    logger.info("Deplexo Audio API gestart.")

    if not API_KEY:
        logger.warning("MUSIC_API_KEY ontbreekt.")

    if ffmpeg_available():
        logger.info("FFmpeg-decoder beschikbaar.")
    else:
        logger.warning("FFmpeg niet gevonden.")
