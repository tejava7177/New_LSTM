# app/api/routes_audio.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from fastapi import Query
from datetime import datetime

from ..core.midi_render import render_wav_with_fluidsynth

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

# 2) **목록**  ← 새로 추가
@router.get("/list")
def list_audio():
    items = []
    for p in RECORD_DIR.iterdir():
        if p.is_file():
            items.append({
                "id": p.name,
                "size": p.stat().st_size,
                "created": datetime.fromtimestamp(p.stat().st_ctime).isoformat(),
            })
    # 최신순
    items.sort(key=lambda x: x["created"], reverse=True)
    return items


@router.get("/{file_id}")
def get_audio(file_id: str):   # ← 여기 str 로 수정
    path = RECORD_DIR / file_id
    if not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path)




@router.delete("/{file_id}")
def delete_audio(file_id: str):
    path = RECORD_DIR / file_id
    if not path.exists():
        raise HTTPException(404, "not found")
    path.unlink()
    return {"deleted": file_id}


@router.post("/render-midi")
async def render_uploaded_midi(file: UploadFile = File(...)):
    name = (file.filename or "input.mid").lower()
    if not (name.endswith(".mid") or name.endswith(".midi")):
        raise HTTPException(400, "MIDI file (.mid/.midi) only")

    midi_id = uuid.uuid4().hex
    midi_path = RECORD_DIR / f"{midi_id}.mid"
    midi_path.write_bytes(await file.read())

    wav_path = midi_path.with_suffix(".wav")
    try:
        render_wav_with_fluidsynth(midi_path, wav_path, sample_rate=48000)
    except Exception as e:
        raise HTTPException(500, f"render failed: {e!s}")

    # 기존 /api/audio/{file_id} 가 RECORD_DIR의 파일을 서빙하므로 재사용
    return {"wavUrl": f"/api/audio/{wav_path.name}"}