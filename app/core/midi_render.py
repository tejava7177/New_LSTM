# app/core/midi_render.py
from pathlib import Path
import os, subprocess

# .env 혹은 환경변수로 오버라이드 가능
DEFAULT_SF2 = Path(__file__).resolve().parents[1] / "assets" / "sf2" / "GeneralUserGS.sf2"
SF2_PATH = Path(os.environ.get("CBB_SF2", str(DEFAULT_SF2)))

def render_wav_with_fluidsynth(midi_path: Path, out_path: Path, sample_rate: int = 48000) -> Path:
    if not midi_path.exists():
        raise FileNotFoundError(f"MIDI not found: {midi_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "fluidsynth", "-ni",
        "-F", str(out_path),
        "-r", str(sample_rate),
        str(SF2_PATH),
        str(midi_path),
    ]
    # 실패 시 에러 메시지 보려고 stdout/stderr 캡처
    p = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_path