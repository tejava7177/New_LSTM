# SongMaker/utils/timing_jazz.py
from typing import List, Tuple, Optional, Union

Note = Union[str, List[str]]  # 생성기가 문자열 또는 리스트를 줄 수 있어 호환

def fix_beats(
    mel: List[Note],
    beats: List[float],
    dyn: List[str],
    lyr: List[str],
    *,
    grid: float = 0.5,            # 스윙 계열에서 8분(0.5) 그리드가 자연스러움
    total_beats: Optional[float] = None,
) -> Tuple[List[Note], List[float], List[str], List[str]]:
    """
    - beats를 0부터 증가하는 누적 끝박으로 스냅(grid) 정렬
    - 음수/역전 제거, total_beats 넘어가면 잘라냄
    """
    if not mel:
        return [], [], [], []
    fm: List[Note] = []
    fb: List[float] = []
    fd: List[str] = []
    fl: List[str] = []

    prev = 0.0
    n = len(mel)
    for i in range(n):
        be = beats[i] if i < len(beats) else prev
        # 스냅
        be = round(be / grid) * grid
        # 역전 방지
        if be < prev:
            be = prev
        # 총 길이 클램프
        if total_beats is not None and be > total_beats:
            be = total_beats
        fm.append(mel[i])
        fb.append(be)
        fd.append(dyn[i] if i < len(dyn) else "mf")
        fl.append(lyr[i] if i < len(lyr) else "")
        prev = be
    return fm, fb, fd, fl


def clip_and_fill_rests(
    mel: List[Note],
    beats: List[float],
    dyn: List[str],
    lyr: List[str],
    *,
    dur_max: float = 2.0,         # 한 이벤트 최대 지속시간(beat). 1.5/1.0로 더 잘게 쪼갤 수도 있음
    grid: float = 0.5,
) -> Tuple[List[Note], List[float], List[str], List[str]]:
    """
    - 각 노트의 길이가 dur_max를 넘으면 grid 단위로 분할
    - 인접 이벤트 사이에 '구멍'이 있으면 'rest'로 채움(길이는 간격)
    - 반환은 여전히 플랫 시퀀스
    """
    if not mel:
        return [], [], [], []
    out_m: List[Note] = []
    out_b: List[float] = []
    out_d: List[str] = []
    out_l: List[str] = []

    start = 0.0
    n = len(mel)
    for i in range(n):
        end = beats[i] if i < len(beats) else start
        dur = end - start

        # 첫 이벤트 전에 공백이 생기면 rest로 채움
        if i == 0 and dur > grid:
            out_m.append("rest")
            out_b.append(round(end, 6))  # 첫 end까지를 휴지로
            out_d.append("mp")
            out_l.append("")

        # 길이 클립/분할
        if dur_max > 0:
            slices = max(1, int(round(dur / dur_max)))
        else:
            slices = 1
        slice_len = dur / slices if slices > 0 else dur

        acc = start
        for _ in range(slices):
            acc += slice_len
            out_m.append(mel[i])
            out_b.append(round(acc, 6))
            out_d.append(dyn[i] if i < len(dyn) else "mf")
            out_l.append(lyr[i] if i < len(lyr) else "")

        start = end

    return out_m, out_b, out_d, out_l