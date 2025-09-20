# app/api/routes_tracks.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from ..core.schemas import GenerateRequest, JobResponse, StatusResponse
from ..core.pipeline_generate import make_track
from ..core.midi_render import render_wav_with_fluidsynth


router = APIRouter()

# 개발 단계: 메모리 상태 저장
_STATUS: dict[str, dict] = {}

# 결과 파일 저장 위치
JOBS_DIR = Path(__file__).resolve().parents[2] / "app" / "jobs"

@router.post("/generate", response_model=JobResponse)
def generate(req: GenerateRequest):
    result = make_track(req.genre, req.progression, req.tempo, req.options, JOBS_DIR)
    # result 예시: {"job_id": "...", "midi_path": "...", "xml_path": "..."}
    # WAV 경로는 미생성 상태로 기록 (요청 시 렌더)
    _STATUS[result["job_id"]] = {
        "status":"DONE","progress":100,
        **result,
        "wav_path": str((Path(result["midi_path"]).with_suffix(".wav")))
    }
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

@router.get("/{job_id}/wav")
def download_wav(job_id: str):
    info = _STATUS.get(job_id)
    if not info:
        raise HTTPException(404, "job not found")

    midi = Path(info["midi_path"])
    wav  = Path(info.get("wav_path", midi.with_suffix(".wav")))

    if not wav.exists():
        try:
            render_wav_with_fluidsynth(midi, wav, sample_rate=48000)
        except Exception as e:
            raise HTTPException(500, f"render failed: {e!s}")

    if not wav.exists():
        raise HTTPException(500, "wav not created")
    return FileResponse(wav, media_type="audio/wav", filename=f"{job_id}.wav")