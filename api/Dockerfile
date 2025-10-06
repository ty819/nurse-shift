FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# system deps for reportlab (fonts) and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libfreetype6 \
    libfreetype6-dev \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY api /app

EXPOSE 10000

ENV HOST=0.0.0.0 \
    PORT=10000 \
    ALLOWED_ORIGINS=*

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]


