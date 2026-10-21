from dataclasses import dataclass
from collections.abc import Iterator
import subprocess


@dataclass
class AudioFormat:
    sample_rate: int = 24000
    channels: int = 2
    sample_width: int = 2  # 16-bit PCM


def decode_audio(source: str) -> Iterator[bytes]:
    """Decode een toegankelijke audiobron naar PCM-blokken."""
    fmt = AudioFormat()

    process = subprocess.Popen(
        [
            "ffmpeg",
            "-nostdin",
            "-v", "error",
            "-i", source,
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "-ar", str(fmt.sample_rate),
            "-ac", str(fmt.channels),
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert process.stdout is not None

    try:
        while True:
            chunk = process.stdout.read(19200)
            if not chunk:
                break
            yield chunk
    finally:
        process.kill()
        process.wait()
