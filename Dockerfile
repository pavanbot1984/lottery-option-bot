FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Minimal OS deps + trust store
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# Upgrade pip toolchain first (prevents many build issues)
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Install scientific wheels (pinned to versions with manylinux wheels)
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "main_multi.py"]
