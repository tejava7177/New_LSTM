# app/api/routes_audio.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import uuid

router = APIRouter()

# 프로젝트 루트/recordings
RECORD_DIR = Path(__file__).resolve().parents[2] / "recordings"
RECORD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload")
async def upload_audio(audio: UploadFile = File(...)):
    if not audio.content_type.startswith("audio/"):
        raise HTTPException(400, "invalid file type")
    ext = "." + (audio.filename.split(".")[-1] if audio.filename and "." in audio.filename else "webm")
    file_id = f"{uuid.uuid4().hex}{ext}"
    dest = RECORD_DIR / file_id
    dest.write_bytes(await audio.read())
    return {"id": file_id, "url": f"/api/audio/{file_id}"}

@router.get("/{file_id}")
def get_audio(file_id: str):   # ← 여기 str 로 수정
    path = RECORD_DIR / file_id
    if not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path)