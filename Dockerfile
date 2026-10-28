
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV FFMPEG_PATH=/usr/bin/ffmpeg

WORKDIR /app

# Installeer FFmpeg en controleer of het werkt
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && /usr/bin/ffmpeg -version \
    && rm -rf /var/lib/apt/lists/*

# Installeer de Python-afhankelijkheden
COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/requirements.txt

# Kopieer de API-code
COPY app.py /app/app.py

EXPOSE 3000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3000"]
