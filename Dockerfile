FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Minimal OS deps (and clean up)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# Pre-install pinned numpy/pandas wheels, then the rest
RUN python -m pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir numpy==1.26.4 pandas==2.2.2 \
 && pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python","main_multi.py"]
