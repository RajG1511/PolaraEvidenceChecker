FROM python:3.11-slim

# ── System deps for PyMuPDF and general build tools ──
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install Python deps first (layer caching) ──
# This layer only rebuilds when requirements.txt changes,
# not when your source code changes. Big time saver.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Download the embedding model at build time ──
# This is the key trick. Without this, the first request after
# container start would block for 30-60s downloading the model.
# The HF_TOKEN arg is needed because embeddinggemma is gated.
ARG HF_TOKEN
ENV HF_TOKEN=${HF_TOKEN}

RUN python -c "\
from huggingface_hub import login; \
login(token='${HF_TOKEN}'); \
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('google/embeddinggemma-300m')"

# Clean up the token after download — don't bake credentials into the image
ENV HF_TOKEN=""

# ── Copy application code ──
COPY api/ api/
COPY polara_checker/ polara_checker/
COPY controls/ controls/
COPY pyproject.toml .

# Install your package in editable-like mode so imports resolve
RUN pip install --no-cache-dir -e .

EXPOSE 8000

# ── Healthcheck so Docker/orchestrators know we're alive ──
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# ── Start the server ──
# Workers=1 because the model is loaded in memory per worker.
# If you need concurrency, scale containers, not workers.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]