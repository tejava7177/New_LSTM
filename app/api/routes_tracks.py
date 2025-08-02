# app/api/routes_tracks.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from ..core.schemas import GenerateRequest, JobResponse, StatusResponse
from ..core.pipeline_generate import make_track

router = APIRouter()

# 개발 단계: 메모리 상태 저장
_STATUS: dict[str, dict] = {}

# 결과 파일 저장 위치
JOBS_DIR = Path(__file__).resolve().parents[2] / "app" / "jobs"

@router.post("/generate", response_model=JobResponse)
def generate(req: GenerateRequest):
    result = make_track(req.genre, req.progression, req.tempo, req.options, JOBS_DIR)
    _STATUS[result["job_id"]] = {"status": "DONE", "progress": 100, **result}
    return {"jobId": result["job_id"]}

@router.get("/status/{job_id}", response_model=StatusResponse)
def status(job_id: str):
    info = _STATUS.get(job_id)
    if not info:
        raise HTTPException(404, "job not found")
    return {"status": info["status"], "progress": info["progress"]}

@router.get("/{job_id}/midi")
def download_midi(job_id: str):
    info = _STATUS.get(job_id)
    if not info:
        raise HTTPException(404, "job not found")
    return FileResponse(info["midi_path"], media_type="audio/midi", filename=f"{job_id}.mid")

@router.get("/{job_id}/musicxml")
def download_xml(job_id: str):
    info = _STATUS.get(job_id)
    if not info:
        raise HTTPException(404, "job not found")
    return FileResponse(info["xml_path"], media_type="application/xml", filename=f"{job_id}.xml")