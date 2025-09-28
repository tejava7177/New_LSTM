# app/core/chord_markers.py
from typing import Iterable, List, Tuple
from mido import MidiFile, MidiTrack, MetaMessage

def _beat_and_bar_ticks(ticks_per_beat: int, time_sig: Tuple[int, int]) -> Tuple[int, int]:
    numer, denom = time_sig
    beat_ticks = int(ticks_per_beat * (4 / denom))     # mido의 ticks_per_beat는 1/4 기준
    bar_ticks  = beat_ticks * numer
    return beat_ticks, bar_ticks

def inject_chord_markers(
    midi_path: str,
    progression: Iterable[str],
    tempo_bpm: float,
    time_sig: Tuple[int, int] = (4, 4),
    repeat: int = 1,
    bars_per_chord: int = 1,
    track_name: str = "Chord Markers",
) -> None:
    """
    최종 MIDI(이미 트리밍/반복 적용됨)에 '코드 마커' 트랙을 추가한다.
    progression 을 repeat 회 반복하며 각 코드마다 bars_per_chord 마디 길이로 마커 삽입.
    """
    mid = MidiFile(midi_path)
    _, bar_ticks = _beat_and_bar_ticks(mid.ticks_per_beat, time_sig)

    # (1) 절대틱 기반 큐 생성
    abs_events: List[Tuple[int, str]] = []
    offset = 0
    prog = list(progression)
    for _ in range(max(1, int(repeat))):
        for ch in prog:
            abs_events.append((offset, ch))
            offset += bar_ticks * max(1, int(bars_per_chord))

    # (2) 마커 전용 트랙 작성 (delta time으로 변환)
    tr = MidiTrack()
    tr.append(MetaMessage("track_name", name=track_name, time=0))

    cur = 0
    for t_abs, text in abs_events:
        delta = max(0, t_abs - cur)
        tr.append(MetaMessage("marker", text=str(text), time=delta))
        cur = t_abs
    tr.append(MetaMessage("end_of_track", time=0))

    # (3) 붙이고 저장
    mid.tracks.append(tr)
    mid.save(midi_path)