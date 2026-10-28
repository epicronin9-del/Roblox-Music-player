
import os
import hmac
import shutil
import logging
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    UploadFile,
    File,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from starlette.background import BackgroundTask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("deplexo")

app = FastAPI(
    title="Deplexo Audio API",
    version="3.0.0",
)

# Configureer deze variabele in de hostingomgeving.
# Dit is de sleutel voor Roblox -> Deplexo.
API_KEY = os.getenv("MUSIC_API_KEY", "").strip()

FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")

ALLOWED_HOSTS = {
    "soundcloud.com",
    "www.soundcloud.com",
    "m.soundcloud.com",
    "on.soundcloud.com",
}

# Limieten voor fase 1.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_AUDIO_SECONDS = 300
PCM_SAMPLE_RATE = 24000
PCM_CHANNELS = 2

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


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Deplexo Audio API",
        "version": app.version,
        "phase": "1",
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

    # Belangrijk: een pagina-URL is geen audiostream.
    # SoundCloud-resolutie wordt in een volgende stap toegevoegd.
    decoder_ready = ffmpeg_available()

    logger.info("SoundCloud-URL gevalideerd.")

    return {
        "status": "received",
        "url": url,
        "source": "SoundCloud",
        "decoder_available": decoder_ready,
        "source_resolver_available": False,
        "playable_in_roblox": False,
        "audio_asset_id": None,
        "message": (
            "URL gevalideerd. De SoundCloud-bronresolver en "
            "Roblox-audio-uitvoer zijn nog niet gekoppeld."
        ),
    }


@app.post("/decode")
async def decode(
    audio_file: UploadFile = File(...),
    x_api_key: str = Header(default="", alias="x-api-key"),
):
    """
    Upload een audiobestand dat je mag gebruiken.
    De server converteert het naar ruwe PCM en retourneert
    de PCM-data als download.

    Formaat: s16le, 24000 Hz, stereo.
    """

    require_api_key(x_api_key)

    if not ffmpeg_available():
        raise HTTPException(
            status_code=503,
            detail="FFmpeg is niet geïnstalleerd of niet beschikbaar.",
        )

    input_path = None
    output_path = None

    try:
        with tempfile.NamedTemporaryFile(
            prefix="input_",
            suffix=".audio",
            dir=TEMP_DIR,
            delete=False,
        ) as temp_input:
            input_path = Path(temp_input.name)
            total_bytes = 0

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

        fd, output_name = tempfile.mkstemp(
            prefix="pcm_",
            suffix=".pcm",
            dir=TEMP_DIR,
        )
        os.close(fd)
        output_path = Path(output_name)

        command = [
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
            "-y",
            str(output_path),
        ]

        logger.info("Audio-upload ontvangen; decoder wordt gestart.")

        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=90,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=408,
                detail="Audio-decoding duurde te lang.",
            )

        if result.returncode != 0 or not output_path.exists():
            error_text = result.stderr.decode(
                "utf-8", errors="replace"
            )[:1000]

            logger.warning("FFmpeg kon het bestand niet decoderen.")

            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Audio kon niet worden gedecodeerd.",
                    "decoder_error": error_text,
                },
            )

        if output_path.stat().st_size == 0:
            raise HTTPException(
                status_code=422,
                detail="Het bestand bevat geen decodeerbare audiotrack.",
            )

        logger.info(
            "PCM-decoding geslaagd: %s bytes.",
            output_path.stat().st_size,
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

    except Exception:
        logger.exception("Onverwachte fout tijdens audio-decoding.")

        if output_path:
            cleanup_file(output_path)

        raise HTTPException(
            status_code=500,
            detail="Interne fout tijdens audio-decoding.",
        )

    finally:
        if input_path:
            cleanup_file(input_path)

        await audio_file.close()


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
        "max_duration_seconds": MAX_AUDIO_SECONDS,
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "note": (
            "PCM-decoding is beschikbaar als FFmpeg werkt. "
            "Roblox-afspeeluitvoer is nog niet aangesloten."
        ),
    }


@app.on_event("startup")
def startup():
    logger.info("Deplexo Audio API gestart.")

    if not API_KEY:
        logger.warning("MUSIC_API_KEY ontbreekt.")

    if ffmpeg_available():
        logger.info("FFmpeg-decoder beschikbaar.")
    else:
        logger.warning(
            "FFmpeg niet gevonden. Stel FFmpeg_PATH in of "
            "installeer FFmpeg in de hostingomgeving."
        )
