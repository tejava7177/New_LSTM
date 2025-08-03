# app/core/pipeline_generate.py
from pathlib import Path
from typing import Dict, List
import uuid, sys, os


# 장르별 함수 임포트
from SongMaker.useSongMaker_rock import generate_rock_track
# (추후) from useSongMaker_jazz import generate_jazz_track
# (추후) from useSongMaker_pop import generate_pop_track

def make_track(genre: str, progression: List[str], tempo: int, options: Dict, outdir: Path) -> Dict:
    """
    [역할] 장르/옵션에 맞는 생성 함수를 호출하고, 결과 파일 경로를 반환한다.
    [반환] {"job_id", "midi_path", "xml_path"}
    """
    outdir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex[:8]
    job_dir = outdir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    if genre == "rock":
        result = generate_rock_track(
            progression=progression,
            tempo=tempo,
            drum=options.get("drum", "auto"),
            gtr=options.get("gtr", "auto"),
            keys=options.get("keys", "auto"),
            keys_shell=options.get("keys_shell", False),
            point_inst=options.get("point_inst", "none"),
            point_density=options.get("point_density", "light"),
            point_key=options.get("point_key", "C"),
            out_dir=str(job_dir)
        )
    else:
        raise ValueError(f"지원되지 않는 장르: {genre}")

    return {
        "job_id": job_id,
        "midi_path": result["midi_path"],
        "xml_path": result["musicxml_path"]
    }