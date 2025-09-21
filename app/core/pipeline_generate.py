# app/core/pipeline_generate.py
from pathlib import Path
from typing import Dict, List
import uuid

# 장르별 함수 임포트
from SongMaker.useSongMaker_rock import generate_rock_track
from SongMaker.useSongMaker_jazz import generate_jazz_track
from SongMaker.useSongMaker_pop import generate_pop_track

# MIDI 후처리(트리밍/반복)용
from mido import MidiFile, MidiTrack, Message, MetaMessage


def _last_sound_tick(track: MidiTrack) -> int:
    """트랙에서 실제 '소리'가 나는 마지막 tick(절대시간)을 반환."""
    t = 0
    last = 0
    for msg in track:
        t += msg.time
        if not msg.is_meta:
            if msg.type == 'note_on' and msg.velocity > 0:
                last = t
            elif msg.type in ('note_off',) or (msg.type == 'note_on' and msg.velocity == 0):
                last = t
    return last


def _slice_track_upto(track: MidiTrack, end_tick: int) -> MidiTrack:
    """
    track을 end_tick(절대시간)까지 잘라 반환.
    end_tick을 넘는 메시지는 버리고, 마지막은 EndOfTrack(time=0)으로 강제 종료.
    """
    new_tr = MidiTrack()
    acc = 0
    for msg in track:
        nxt = acc + msg.time
        if msg.type == 'end_of_track':
            # 원래 EOT는 무시하고, 마지막에 time=0으로 새로 추가
            acc = nxt
            continue
        if nxt <= end_tick:
            # 그대로 복사
            new_tr.append(msg.copy())
            acc = nxt
        else:
            # end_tick을 넘어서는 첫 메시지
            # 보통 여기 들어오면 msg는 메타인 경우가 많음. 잘라버림.
            break
    # 딱 끝에 맞춰 종료
    new_tr.append(MetaMessage('end_of_track', time=0))
    return new_tr


def _repeat_tracks(mid: MidiFile, repeats: int) -> MidiFile:
    """
    각 트랙을 '소리의 마지막 시점'까지를 하나의 청크로 보고 그 청크를 repeats회 연결.
    메타(템포/박자 등)가 청크 내부에 있어도 함께 반복됨.
    '소리가 전혀 없는 트랙'(메타만 있는 트랙)은 time=0에 있는 메타만 유지하고 EOT로 종료.
    """
    out = MidiFile(type=mid.type, ticks_per_beat=mid.ticks_per_beat)
    for tr in mid.tracks:
        # 청크 길이: 실제 소리가 끝나는 tick
        end_tick = _last_sound_tick(tr)

        if end_tick <= 0:
            # 소리가 전혀 없는 메타 전용 트랙
            # time=0 에 있는 메타만 유지하고, EOT(0)로 끝냄
            base = MidiTrack()
            acc = 0
            for msg in tr:
                acc += msg.time
                # time>0 메타는 반복시 기준 구간 밖이므로 버린다(초기 템포/박자만 유지)
                if acc == 0 and msg.is_meta and msg.type != 'end_of_track':
                    base.append(msg.copy())
            base.append(MetaMessage('end_of_track', time=0))
            out.tracks.append(base)
            continue

        # end_tick까지 슬라이스한 청크
        chunk = _slice_track_upto(tr, end_tick)

        # chunk 반복 연결
        rep = MidiTrack()
        # 첫 반복은 그대로 붙이고
        for msg in chunk:
            if msg.type == 'end_of_track':
                # 마지막 EOT는 일단 제거(전체 반복이 끝난 뒤 한 번만 붙임)
                continue
            rep.append(msg.copy())

        # 2회차 이상 반복: 청크를 동일한 델타로 그대로 이어붙임
        for _ in range(repeats - 1):
            for msg in chunk:
                if msg.type == 'end_of_track':
                    continue
                rep.append(msg.copy())

        # 전체 트랙 종료 지점에서 즉시 종료
        rep.append(MetaMessage('end_of_track', time=0))
        out.tracks.append(rep)

    return out


def _postprocess_midi_repeat_and_trim(midi_path: Path, repeats: int) -> None:
    """
    생성된 MIDI를 로드하여 각 트랙을 트리밍하고 repeats회 반복하여 같은 경로에 덮어쓴다.
    """
    mid = MidiFile(str(midi_path))
    # 반복이 1 미만이면 최소 1
    repeats = max(1, int(repeats))
    processed = _repeat_tracks(mid, repeats)
    processed.save(str(midi_path))


def make_track(genre, progression, tempo, options, outdir):
    """
    SongMaker로 기본 트랙을 생성한 뒤,
    - 각 트랙의 실제 소리 구간까지만 남기고(꼬리 제거),
    - 그 구간을 repeats(기본 6회)만큼 반복하여
    최종 .mid를 덮어쓴다.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex[:8]
    job_dir = outdir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # 기본 옵션
    opts = options or {}
    repeats = int(opts.get("repeats", 6))

    if genre == "rock":
        result = generate_rock_track(
            progression=progression, tempo=tempo,
            drum=opts.get("drum", "auto"),
            gtr=opts.get("gtr", "auto"),
            keys=opts.get("keys", "auto"),
            keys_shell=opts.get("keys_shell", False),
            point_inst=opts.get("point_inst", "none"),
            point_density=opts.get("point_density", "light"),
            point_key=opts.get("point_key", "C"),
            out_dir=str(job_dir)
        )
    elif genre == "jazz":
        result = generate_jazz_track(
            progression=progression, tempo=tempo,
            drum=opts.get("drum","auto"),
            comp=opts.get("comp","auto"),
            point_inst=opts.get("point_inst","none"),
            point_density=opts.get("point_density","light"),
            point_key=opts.get("point_key","C"),
            out_dir=str(job_dir)
        )
    elif genre == "pop":
        result = generate_pop_track(
            progression=progression, tempo=tempo,
            drum=opts.get("drum", "auto"),
            gtr=opts.get("gtr", "auto"),
            keys=opts.get("keys", "auto"),
            point_inst=opts.get("point_inst", "none"),
            point_density=opts.get("point_density", "light"),
            point_key=opts.get("point_key", "C"),
            out_dir=str(job_dir)
        )
    else:
        raise ValueError(f"지원되지 않는 장르: {genre}")

    midi_path = Path(result["midi_path"])
    # 생성된 MIDI를 트리밍 + 반복 후 덮어쓰기
    try:
        _postprocess_midi_repeat_and_trim(midi_path, repeats=repeats)
    except Exception as e:
        # 후처리 실패해도 원본은 존재하므로, 에러를 굳이 막진 않지만 로그 남기기 원하면 여기서 처리
        # print(f"[WARN] MIDI postprocess failed: {e}")
        pass

    return {
        "job_id": job_id,
        "midi_path": str(midi_path),
        "xml_path": result["musicxml_path"]
    }