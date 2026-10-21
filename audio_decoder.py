
from dataclasses import dataclass
from collections.abc import Iterator
import subprocess


@dataclass(frozen=True)
class AudioFormat:
    sample_rate: int = 24000
    channels: int = 2
    sample_width: int = 2


def decode_audio(source: str) -> Iterator[bytes]:
    """
    Decodeer een toegankelijke audiobron naar PCM-blokken.
    Gebruik dit niet rechtstreeks met ongecontroleerde gebruikers-URL's.
    """
    fmt = AudioFormat()

    command = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-i", source,
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ar", str(fmt.sample_rate),
        "-ac", str(fmt.channels),
        "pipe:1",
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    assert process.stdout is not None

    try:
        while True:
            chunk = process.stdout.read(19200)
            if not chunk:
                break
            yield chunk

        exit_code = process.wait(timeout=10)
        if exit_code != 0:
            raise RuntimeError(
                f"FFmpeg stopte met foutcode {exit_code}"
            )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

        process.stdout.close()
