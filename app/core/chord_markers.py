# app/core/chord_markers.py
from __future__ import annotations
from typing import List, Tuple
import mido

def inject_chord_markers(
    midi_path: str,
    progression: List[str],
    tempo_bpm: float,
    time_sig: Tuple[int, int] = (4, 4),
    repeat: int = 6,
    bars_per_chord: int = 1,
    track_name: str = "Chord Markers",
) -> None:
    """
    MIDI 파일에 코드 마커(meta: marker)를 바(또는 n바) 단위로 삽입.
    - progression: 예) ["C", "Dm", "G", "C"]
    - repeat: 진행 반복 횟수(요구사항: 6회)
    - bars_per_chord: 한 코드가 차지하는 마디 수(보통 1)
    """
    mid = mido.MidiFile(midi_path)
    ppq = mid.ticks_per_beat
    beats_per_bar = time_sig[0]
    bar_ticks = ppq * beats_per_bar

    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage("track_name", name=track_name, time=0))

    # 절대 tick 스케줄 생성
    schedule = []
    pos = 0
    for _ in range(repeat):
        for ch in progression:
            schedule.append((pos, ch))
            pos += bar_ticks * bars_per_chord

    # 절대 tick → delta time 으로 변환하며 marker 삽입
    last = 0
    for tick, text in schedule:
        delta = tick - last
        tr.append(mido.MetaMessage("marker", text=text, time=delta))
        last = tick

    # 끝 지점 표시(옵션)
    tr.append(mido.MetaMessage("marker", text="END", time=(pos - last)))

    # 별도 트랙으로 삽입(맨 앞에 넣어도, 뒤에 넣어도 무방)
    mid.tracks.insert(0, tr)
    mid.save(midi_path)