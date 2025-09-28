# # app/core/pipeline_generate.py
# from pathlib import Path
# from typing import List, Tuple
# import uuid
#
# # 장르별 생성기
# from SongMaker.useSongMaker_rock import generate_rock_track
# from SongMaker.useSongMaker_jazz import generate_jazz_track
# from SongMaker.useSongMaker_pop  import generate_pop_track
#
# # MIDI 후처리
# from mido import MidiFile, MidiTrack, MetaMessage
#
# # 코드 마커 주입 유틸(외부 모듈)
# from .chord_markers import inject_chord_markers
#
#
# # =========================
# # 내부 유틸: 트리밍/반복
# # =========================
#
# def _last_sound_tick(track: MidiTrack) -> int:
#     """트랙에서 실제 '소리'가 나는 마지막 tick(절대시간)을 반환."""
#     t = 0
#     last = 0
#     for msg in track:
#         t += msg.time
#         if not msg.is_meta:
#             if msg.type == "note_on" and msg.velocity > 0:
#                 last = t
#             elif msg.type in ("note_off",) or (msg.type == "note_on" and msg.velocity == 0):
#                 last = t
#     return last
#
#
# def _slice_track_upto(track: MidiTrack, end_tick: int) -> MidiTrack:
#     """
#     track을 end_tick(절대시간)까지 잘라 반환.
#     end_tick을 넘는 메시지는 버리고, 마지막은 EndOfTrack(time=0)으로 강제 종료.
#     """
#     new_tr = MidiTrack()
#     acc = 0
#     for msg in track:
#         nxt = acc + msg.time
#         if msg.type == "end_of_track":
#             acc = nxt
#             continue
#         if nxt <= end_tick:
#             new_tr.append(msg.copy())
#             acc = nxt
#         else:
#             break
#     new_tr.append(MetaMessage("end_of_track", time=0))
#     return new_tr
#
#
# def _repeat_tracks(mid: MidiFile, repeats: int) -> MidiFile:
#     """
#     각 트랙을 '실제 소리의 마지막 시점'까지를 하나의 청크로 보고 그 청크를 repeats회 연결.
#     - 메타(템포/박자 등)가 청크 내부에 있어도 함께 반복됨.
#     - '소리가 전혀 없는 트랙'(메타만 있는 트랙)은 time=0 메타만 유지하고 바로 종료.
#       (※ 코드 마커는 반복/트리밍 '이후'에 주입해야 함)
#     """
#     out = MidiFile(type=mid.type, ticks_per_beat=mid.ticks_per_beat)
#     for tr in mid.tracks:
#         end_tick = _last_sound_tick(tr)
#
#         if end_tick <= 0:
#             # 메타 전용 트랙: time=0 메타만 유지
#             base = MidiTrack()
#             acc = 0
#             for msg in tr:
#                 acc += msg.time
#                 if acc == 0 and msg.is_meta and msg.type != "end_of_track":
#                     base.append(msg.copy())
#             base.append(MetaMessage("end_of_track", time=0))
#             out.tracks.append(base)
#             continue
#
#         # end_tick까지 슬라이스한 청크
#         chunk = _slice_track_upto(tr, end_tick)
#
#         # chunk 반복 연결
#         rep = MidiTrack()
#         for msg in chunk:
#             if msg.type == "end_of_track":
#                 continue
#             rep.append(msg.copy())
#
#         for _ in range(max(1, int(repeats)) - 1):
#             for msg in chunk:
#                 if msg.type == "end_of_track":
#                     continue
#                 rep.append(msg.copy())
#
#         rep.append(MetaMessage("end_of_track", time=0))
#         out.tracks.append(rep)
#
#     return out
#
#
# def _postprocess_midi_repeat_and_trim(midi_path: Path, repeats: int) -> None:
#     """생성된 MIDI를 로드하여 각 트랙을 트리밍하고 repeats회 반복하여 같은 경로에 덮어쓴다."""
#     mid = MidiFile(str(midi_path))
#     processed = _repeat_tracks(mid, max(1, int(repeats)))
#     processed.save(str(midi_path))
#
#
# def _read_first_time_signature(midi_path: Path) -> Tuple[int, int]:
#     """MIDI에서 첫 박자표(time_signature)를 읽어 (분자, 분모) 반환. 없으면 (4,4)."""
#     mid = MidiFile(str(midi_path))
#     for tr in mid.tracks:
#         acc = 0
#         for msg in tr:
#             acc += msg.time
#             if msg.is_meta and msg.type == "time_signature":
#                 return (msg.numerator, msg.denominator)
#     return (4, 4)
#
#
# # =========================
# # 공개 함수
# # =========================
#
# def make_track(genre: str, progression: List[str], tempo: float, options: dict, outdir: Path):
#     """
#     1) SongMaker로 기본 트랙 생성
#     2) 실제 연주 구간까지만 남기고 트랙별 트리밍
#     3) 해당 구간을 repeats(기본 6회) 반복
#     4) 마지막으로 코드 마커 삽입(프론트 HUD/표시용)
#     """
#     outdir.mkdir(parents=True, exist_ok=True)
#     job_id = uuid.uuid4().hex[:8]
#     job_dir = outdir / job_id
#     job_dir.mkdir(parents=True, exist_ok=True)
#
#     opts = options or {}
#     repeats = int(opts.get("repeats", 6))                # 진행 반복 횟수(오디오 길이)
#     bars_per_chord = int(opts.get("bars_per_chord", 1))  # 코드 1개가 차지하는 마디 수(기본 1마디=4박)
#
#     # --- 1) SongMaker 호출 ---
#     if genre == "rock":
#         result = generate_rock_track(
#             progression=progression, tempo=tempo,
#             drum=opts.get("drum", "auto"),
#             gtr=opts.get("gtr", "auto"),
#             keys=opts.get("keys", "auto"),
#             keys_shell=opts.get("keys_shell", False),
#             point_inst=opts.get("point_inst", "none"),
#             point_density=opts.get("point_density", "light"),
#             point_key=opts.get("point_key", "C"),
#             out_dir=str(job_dir),
#         )
#     elif genre == "jazz":
#         result = generate_jazz_track(
#             progression=progression, tempo=tempo,
#             drum=opts.get("drum", "auto"),
#             comp=opts.get("comp", "auto"),
#             point_inst=opts.get("point_inst", "none"),
#             point_density=opts.get("point_density", "light"),
#             point_key=opts.get("point_key", "C"),
#             out_dir=str(job_dir),
#         )
#     elif genre == "pop":
#         result = generate_pop_track(
#             progression=progression, tempo=tempo,
#             drum=opts.get("drum", "auto"),
#             gtr=opts.get("gtr", "auto"),
#             keys=opts.get("keys", "auto"),
#             point_inst=opts.get("point_inst", "none"),
#             point_density=opts.get("point_density", "light"),
#             point_key=opts.get("point_key", "C"),
#             out_dir=str(job_dir),
#         )
#     else:
#         raise ValueError(f"지원되지 않는 장르: {genre}")
#
#     midi_path = Path(result["midi_path"])
#
#     # --- 2~3) 트리밍 + 반복 ---
#     try:
#         _postprocess_midi_repeat_and_trim(midi_path, repeats=repeats)
#     except Exception:
#         # 후처리 실패해도 원본은 사용 가능
#         pass
#
#     # --- 4) 코드 마커 주입(항상 마지막 단계에서) ---
#     try:
#         time_sig = _read_first_time_signature(midi_path)  # 없으면 (4,4)
#         kwargs_common = dict(
#             midi_path=str(midi_path),
#             progression=progression,
#             tempo_bpm=float(tempo),
#             time_sig=time_sig,
#             bars_per_chord=bars_per_chord,
#             track_name="Chord Markers",
#         )
#         # 외부 유틸의 파라미터명이 repeat 또는 repeats 인 경우 모두 대응
#         try:
#             inject_chord_markers(**kwargs_common, repeats=repeats)
#         except TypeError:
#             inject_chord_markers(**kwargs_common, repeat=repeats)
#     except Exception:
#         # 마커 주입 실패해도 트랙은 사용 가능
#         pass
#
#     return {
#         "job_id": job_id,
#         "midi_path": str(midi_path),
#         "xml_path": result["musicxml_path"],
#     }

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