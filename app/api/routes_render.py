# app/api/routes_render.py
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
    # 우선순위: 환경변수 → 로컬 자산 → 일반 설치 경로
    cand = [
        os.environ.get("SF2_PATH"),
        BASE_DIR / "app" / "assets" / "sf2" / "GeneralUserGS.sf2",
        Path("/opt/homebrew/share/soundfonts/FluidR3_GM.sf2"),
        Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
    ]
    for c in cand:
        if not c:
            continue
        p = Path(c)
        if p.exists():
            return p
    return None

@router.post("/midi-to-wav")
async def midi_to_wav(midi: UploadFile = File(...)):
    # 브라우저에 따라 content_type이 다양해서 엄격 차단은 하지 않음
    # if midi.content_type not in (...): pass

    if not which("fluidsynth"):
        raise HTTPException(
            501,
            "fluidsynth CLI가 없습니다. 'brew install fluid-synth' 후 다시 시도하세요."
        )

    sf2 = find_sf2()
    if not sf2:
        raise HTTPException(
            500,
            "SF2 사운드폰트를 찾을 수 없습니다. SF2_PATH 환경변수 설정 또는 app/assets/sf2/ 경로에 배치하세요."
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
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not tmp_wav.exists():
            raise HTTPException(500, "fluidsynth 렌더 실패: " + (proc.stderr or proc.stdout))

        out_id = f"{uuid.uuid4().hex}.wav"
        out_path = RENDER_DIR / out_id
        shutil.move(str(tmp_wav), out_path)

    duration = 0.0
    with wave.open(str(out_path), "rb") as wf:
        frames = wf.getnframes()
        fr = wf.getframerate()
        duration = frames / float(fr)

    return {"id": out_id, "url": f"/api/render/{out_id}", "duration": duration}

@router.get("/{file_id}")
def get_render(file_id: str):
    path = RENDER_DIR / file_id
    if not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path)