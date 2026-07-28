FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/data/huggingface \
    TORCH_HOME=/app/data/torch

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        curl \
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -c "from pathlib import Path; raw = Path('requirements.txt').read_bytes(); encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8'; Path('/tmp/requirements.txt').write_text(raw.decode(encoding), encoding='utf-8')" \
    && python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements.txt

COPY . .

RUN mkdir -p \
        /app/data/uploads \
        /app/data/extracted \
        /app/data/fields \
        /app/data/validation \
        /app/data/assessments \
        /app/data/huggingface \
        /app/data/torch \
    && useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read()"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
