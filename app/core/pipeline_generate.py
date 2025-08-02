# app/core/pipeline_generate.py
from pathlib import Path
from typing import Dict, List
import uuid

def make_track(genre: str, progression: List[str], tempo: int, options: Dict, outdir: Path) -> Dict:
    # TODO: SongMaker/useSongMaker_{genre}.py 실제 호출로 교체
    outdir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex[:8]
    midi_path = outdir / f"{genre}_demo_{job_id}.mid"
    xml_path  = outdir / f"{genre}_demo_{job_id}.xml"
    # 최소 동작용 더미 파일 생성
    midi_path.write_bytes(b"MThd\x00\x00\x00\x06\x00\x01\x00\x01\x01\xE0MTrk\x00\x00\x00\x00")
    xml_path.write_text("<score-partwise></score-partwise>")
    return {"job_id": job_id, "midi_path": str(midi_path), "xml_path": str(xml_path)}