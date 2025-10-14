# === Base image ===
FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 시스템 빌드 도구(최소)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# === Python deps ===
# 1) PyTorch(CPU) 먼저
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch torchvision torchaudio

# 2) 나머지 requirements
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
    fluidsynth \
    libsndfile1 \
  && rm -rf /var/lib/apt/lists/*

# === 소스/에셋 복사 ===
COPY . /app

# === 컨테이너 기본 ENV (필요시 docker-compose에서 덮어씀) ===
ENV CBB_MODEL_JAZZ=/app/assets/model/jazz \
    CBB_MODEL_ROCK=/app/assets/model/rock \
    CBB_MODEL_POP=/app/assets/model/pop \
    CBB_DATA_DIR=/app/LSTM/cli/data \
    CBB_RECORDINGS_DIR=/recordings \
    CBB_SOUNDFONT_PATH=/app/assets/sf2/GeneralUserGS.sf2

# 산출물 폴더
RUN mkdir -p /recordings

EXPOSE 8000

# 개발/테스트는 --reload, 배포는 --reload 제거(+workers=1 권장)
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]