# app/core/pipeline_generate.py
from pathlib import Path
from typing import Tuple
import uuid

from SongMaker.useSongMaker_rock import generate_rock_track
from SongMaker.useSongMaker_jazz import generate_jazz_track
from SongMaker.useSongMaker_pop  import generate_pop_track

from mido import MidiFile, MidiTrack, MetaMessage
from .chord_markers import inject_chord_markers

# ===== 내부 유틸: 트리밍/반복 =====
def _last_sound_tick(track: MidiTrack) -> int:
    t = 0; last = 0
    for msg in track:
        t += msg.time
        if msg.is_meta:
            continue
        if msg.type == "note_on" and msg.velocity > 0:
            last = t
        elif msg.type in ("note_off",) or (msg.type == "note_on" and msg.velocity == 0):
            last = t
    return last

def _slice_track_upto(track: MidiTrack, end_tick: int) -> MidiTrack:
    acc = 0
    out = MidiTrack()
    for msg in track:
        nxt = acc + msg.time
        if msg.type == "end_of_track":
            acc = nxt
            continue
        if nxt <= end_tick:
            out.append(msg.copy())
            acc = nxt
        else:
            break
    out.append(MetaMessage("end_of_track", time=0))
    return out

def _repeat_tracks(mid: MidiFile, repeats: int) -> MidiFile:
    out = MidiFile(type=mid.type, ticks_per_beat=mid.ticks_per_beat)
    repeats = max(1, int(repeats))

    for tr in mid.tracks:
        end_tick = _last_sound_tick(tr)

        if end_tick <= 0:
            base = MidiTrack()
            acc = 0
            for msg in tr:
                acc += msg.time
                if acc == 0 and msg.is_meta and msg.type != "end_of_track":
                    base.append(msg.copy())
            base.append(MetaMessage("end_of_track", time=0))
            out.tracks.append(base)
            continue

        chunk = _slice_track_upto(tr, end_tick)
        rep = MidiTrack()
        for msg in chunk:
            if msg.type != "end_of_track":
                rep.append(msg.copy())
        for _ in range(repeats - 1):
            for msg in chunk:
                if msg.type != "end_of_track":
                    rep.append(msg.copy())
        rep.append(MetaMessage("end_of_track", time=0))
        out.tracks.append(rep)

    return out

def _postprocess_midi_repeat_and_trim(midi_path: Path, repeats: int) -> None:
    mid = MidiFile(str(midi_path))
    processed = _repeat_tracks(mid, repeats=max(1, int(repeats)))
    processed.save(str(midi_path))

def _read_first_time_signature(midi_path: Path) -> Tuple[int, int]:
    mid = MidiFile(str(midi_path))
    for tr in mid.tracks:
        acc = 0
        for msg in tr:
            acc += msg.time
            if msg.is_meta and msg.type == "time_signature":
                return (msg.numerator, msg.denominator)
    return (4, 4)

# ===== 공개 엔트리포인트 =====
def make_track(genre, progression, tempo, options, outdir):
    """
    1) SongMaker로 기본 트랙 생성
    2) 실제 소리구간 기준으로 트리밍 후 repeats회 반복
    3) 코드 마커(현재/다음 코드 HUD용) 삽입
    """
    outdir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex[:8]
    job_dir = outdir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    opts = options or {}
    repeats = int(opts.get("repeats", 6))
    bars_per_chord = int(opts.get("bars_per_chord", 1))

    if genre == "rock":
        result = generate_rock_track(
            progression=progression, tempo=tempo,
            drum=opts.get("drum","auto"),
            gtr=opts.get("gtr","auto"),
            keys=opts.get("keys","auto"),
            keys_shell=opts.get("keys_shell", False),
            point_inst=opts.get("point_inst","none"),
            point_density=opts.get("point_density","light"),
            point_key=opts.get("point_key","C"),
            out_dir=str(job_dir),
        )
    elif genre == "jazz":
        result = generate_jazz_track(
            progression=progression, tempo=tempo,
            drum=opts.get("drum","auto"),
            comp=opts.get("comp","auto"),
            point_inst=opts.get("point_inst","none"),
            point_density=opts.get("point_density","light"),
            point_key=opts.get("point_key","C"),
            out_dir=str(job_dir),
        )
    elif genre == "pop":
        result = generate_pop_track(
            progression=progression, tempo=tempo,
            drum=opts.get("drum","auto"),
            gtr=opts.get("gtr","auto"),
            keys=opts.get("keys","auto"),
            point_inst=opts.get("point_inst","none"),
            point_density=opts.get("point_density","light"),
            point_key=opts.get("point_key","C"),
            out_dir=str(job_dir),
        )
    else:
        raise ValueError(f"지원되지 않는 장르: {genre}")

    midi_path = Path(result["midi_path"])

    # 1~2) 트리밍 + 반복
    try:
        _postprocess_midi_repeat_and_trim(midi_path, repeats=repeats)
    except Exception:
        pass

    # 3) 코드 마커 삽입(항상 '마지막' 단계)
    try:
        time_sig = _read_first_time_signature(midi_path)
        inject_chord_markers(
            midi_path=str(midi_path),
            progression=progression,
            tempo_bpm=float(tempo),
            time_sig=time_sig,
            repeat=repeats,
            bars_per_chord=bars_per_chord,
            track_name="Chord Markers",
        )
    except Exception:
        pass

    return {
        "job_id": job_id,
        "midi_path": str(midi_path),
        "xml_path": result["musicxml_path"],
    }