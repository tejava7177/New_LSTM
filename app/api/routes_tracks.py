from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from ..core.schemas import GenerateRequest, JobResponse, StatusResponse
from ..core.pipeline_generate import make_track

# fluidsynth 래퍼(프로젝트에 있는 것 사용)
from ..core.midi_render import render_wav_with_fluidsynth

router = APIRouter()

# 개발 단계: 메모리 상태 저장 (간단 캐시)
_STATUS: dict[str, dict] = {}

# 결과 파일 저장 위치 (현재 파일: app/api/routes_tracks.py → parents[1] == app 디렉토리)
APP_DIR = Path(__file__).resolve().parents[1]   # .../app
JOBS_DIR = APP_DIR / "jobs"

@router.post("/generate", response_model=JobResponse)
def generate(req: GenerateRequest):
    # outdir는 make_track 내부에서 ensure_dir 처리하지만, 여기서도 한 번 보장해둠
    JOBS_DIR.mkdir(parents=True, exist_ok=True)

    result = make_track(req.genre, req.progression, req.tempo, req.options, JOBS_DIR)
    # result: {"job_id": "...", "midi_path": "...", "xml_path": "..."}

    wav_path = str(Path(result["midi_path"]).with_suffix(".wav"))

    _STATUS[result["job_id"]] = {
        "status": "DONE",
        "progress": 100,
        **result,
        "wav_path": wav_path,  # 아직 없을 수 있음 → 요청 시 생성
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
    midi_path = Path(info["midi_path"])
    if not midi_path.exists():
        raise HTTPException(404, "midi not found")
    return FileResponse(str(midi_path), media_type="audio/midi", filename=f"{job_id}.mid")


@router.get("/{job_id}/musicxml")
def download_xml(job_id: str):
    info = _STATUS.get(job_id)
    if not info:
        raise HTTPException(404, "job not found")
    xml_path = Path(info["xml_path"])
    if not xml_path.exists():
        raise HTTPException(404, "musicxml not found")
    # 필요하면 미디어 타입을 MusicXML로 변경 가능:
    # "application/vnd.recordare.musicxml+xml"
    return FileResponse(str(xml_path), media_type="application/xml", filename=f"{job_id}.xml")


@router.get("/{job_id}/wav")
def download_wav(job_id: str):
    info = _STATUS.get(job_id)
    if not info:
        raise HTTPException(404, "job not found")

    midi = Path(info["midi_path"])
    if not midi.exists():
        raise HTTPException(404, "midi not found")

    wav = Path(info.get("wav_path") or midi.with_suffix(".wav"))
    if not wav.exists():
        try:
            # 일부 구현은 str 경로를 기대하므로 안전하게 str로 전달
            render_wav_with_fluidsynth(str(midi), str(wav), sample_rate=48000)
        except Exception as e:
            raise HTTPException(500, f"render failed: {e!s}")

    if not wav.exists():
        raise HTTPException(500, "wav not created")

    return FileResponse(str(wav), media_type="audio/wav", filename=f"{job_id}.wav")