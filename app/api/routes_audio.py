# app/api/routes_audio.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from datetime import datetime
from typing import Optional
import uuid
import tempfile

from ..core.midi_render import render_wav_with_fluidsynth

router = APIRouter()

# 프로젝트 루트/recordings (업로드/보관용)
RECORD_DIR = Path(__file__).resolve().parents[2] / "recordings"
RECORD_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------
# 기본 업로드/목록/다운로드
# ---------------------------
@router.post("/upload")
async def upload_audio(audio: UploadFile = File(...)):
    if not audio.content_type.startswith("audio/"):
        raise HTTPException(400, "invalid file type")
    ext = "." + (audio.filename.split(".")[-1] if audio.filename and "." in audio.filename else "webm")
    file_id = f"{uuid.uuid4().hex}{ext}"
    dest = RECORD_DIR / file_id
    dest.write_bytes(await audio.read())
    return {"id": file_id, "url": f"/api/audio/{file_id}"}


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
    items.sort(key=lambda x: x["created"], reverse=True)
    return items


@router.get("/{file_id}")
def get_audio(file_id: str):
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


# ---------------------------
# MIDI → WAV 렌더 (jobId 또는 업로드 파일)
# ---------------------------
@router.post("/render-midi")
async def render_midi(
    file: Optional[UploadFile] = File(None),
    jobId: Optional[str] = Query(default=None, description="이미 생성된 MIDI의 jobId"),
):
    """
    두 가지 모두 지원:
    - jobId 전달 → 생성된 MIDI를 서버에서 찾아 WAV 렌더
    - file 업로드(.mid/.midi)
    """
    # 1) jobId 기반 (권장 경로)
    if jobId:
        try:
            # 순환참조 피하려고 지연 임포트
            from .routes_tracks import _STATUS  # type: ignore
        except Exception:
            _STATUS = {}

        info = _STATUS.get(jobId)
        if not info:
            raise HTTPException(404, f"job not found: {jobId}")

        midi_path = Path(info["midi_path"])
        wav_path = Path(info.get("wav_path", midi_path.with_suffix(".wav")))
        try:
            render_wav_with_fluidsynth(midi_path, wav_path, sample_rate=48000)
        except Exception as e:
            raise HTTPException(500, f"render failed: {e!s}")

        # tracks 라우터의 wav 엔드포인트를 그대로 사용
        return {"wavUrl": f"/api/tracks/{jobId}/wav"}

    # 2) 업로드 기반(호환)
    if file is None:
        raise HTTPException(400, "file or jobId required")

    name = (file.filename or "input.mid").lower()
    if not (name.endswith(".mid") or name.endswith(".midi")):
        raise HTTPException(400, "MIDI file (.mid/.midi) only")

    tmpdir = Path(tempfile.gettempdir()) / f"cbb_{uuid.uuid4().hex}"
    tmpdir.mkdir(parents=True, exist_ok=True)

    midi_path = tmpdir / "input.mid"
    wav_path = tmpdir / "output.wav"
    midi_path.write_bytes(await file.read())

    try:
        render_wav_with_fluidsynth(midi_path, wav_path, sample_rate=48000)
    except Exception as e:
        raise HTTPException(500, f"render failed: {e!s}")

    # 임시 wav 파일 서빙용 엔드포인트
    return {"wavUrl": f"/api/audio/tmp/{wav_path.name}", "tmpDir": str(tmpdir)}


@router.get("/tmp/{name}")
def get_tmp_audio(name: str):
    """render-midi(업로드)용 임시 wav 파일 제공"""
    base = Path(tempfile.gettempdir())
    p = next(base.glob(f"cbb_*/{name}"), None)
    if not p or not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p, media_type="audio/wav", filename=name)