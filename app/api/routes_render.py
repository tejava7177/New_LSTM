# app/api/routes_render.py (발췌)
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Optional
import shutil, subprocess, uuid, wave, os, tempfile

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
RENDER_DIR = BASE_DIR / "renders"
RENDER_DIR.mkdir(parents=True, exist_ok=True)

def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)

def find_sf2() -> Optional[Path]:
    """
    우선순위: 환경변수(CBB_SOUNDFONT_PATH → SF2_PATH) → 프로젝트 자산 → 시스템 기본 경로
    """
    env_candidates = [
        os.environ.get("CBB_SOUNDFONT_PATH"),
        os.environ.get("SF2_PATH"),
    ]
    file_candidates = [
        BASE_DIR / "app" / "assets" / "sf2" / "GeneralUserGS.sf2",
        Path("/opt/homebrew/share/soundfonts/FluidR3_GM.sf2"),
        Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
    ]
    for c in [*env_candidates, *file_candidates]:
        if not c:
            continue
        p = Path(c)
        if p.exists():
            return p
    return None

@router.post("/midi-to-wav")
async def midi_to_wav(midi: UploadFile = File(...)):
    if not which("fluidsynth"):
        raise HTTPException(
            501,
            "fluidsynth CLI를 찾지 못했습니다. (컨테이너라면 apt-get으로 fluidsynth 설치 필요)"
        )

    sf2 = find_sf2()
    if not sf2:
        raise HTTPException(
            500,
            "SF2 사운드폰트를 찾지 못했습니다. CBB_SOUNDFONT_PATH(또는 SF2_PATH) 환경변수 설정 "
            "혹은 app/assets/sf2/GeneralUserGS.sf2 배치가 필요합니다."
        )

    with tempfile.TemporaryDirectory() as td:
        tmp_mid = Path(td) / "in.mid"
        tmp_wav = Path(td) / "out.wav"
        tmp_mid.write_bytes(await midi.read())

        cmd = [
            "fluidsynth",
            "-ni",
            "-F", str(tmp_wav),
            "-T", "wav",
            str(sf2),
            str(tmp_mid),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "fluidsynth 렌더 타임아웃(120s)")

        if proc.returncode != 0 or not tmp_wav.exists():
            detail = (proc.stderr or proc.stdout or "").strip()
            raise HTTPException(500, f"fluidsynth 렌더 실패: {detail[:4000]}")

        out_id = f"{uuid.uuid4().hex}.wav"
        out_path = RENDER_DIR / out_id
        shutil.move(str(tmp_wav), out_path)

    duration = 0.0
    try:
        with wave.open(str(out_path), "rb") as wf:
            frames = wf.getnframes()
            fr = wf.getframerate()
            duration = frames / float(fr)
    except Exception:
        # duration 계산
        duration = 0.0

    return {"id": out_id, "url": f"/api/render/{out_id}", "duration": duration}

@router.get("/{file_id}")
def get_render(file_id: str):
    path = RENDER_DIR / file_id
    if not path.exists():
        raise HTTPException(404, "not found")
    # wav만 반환하고 싶다면 media_type="audio/wav" 지정 가능
    return FileResponse(path)  # , media_type="audio/wav"