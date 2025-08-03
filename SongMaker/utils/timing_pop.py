# SongMaker/utils/timing_pop.py
from typing import List, Tuple, Optional, Union

Note = Union[str, List[str]]

def fix_beats(mel: List[Note], beats: List[float], dyn: List[str], lyr: List[str],
              grid: float = 0.25, total_beats: Optional[float] = None
              ) -> Tuple[List[Note], List[float], List[str], List[str]]:
    """
    - beats를 0부터 증가하는 누적 끝박으로 스냅(grid) 정렬
    - 음수/역전 제거, total_beats 넘어가면 잘라냄
    """
    if not mel:
        return [], [], [], []
    fm: List[Note]; fb: List[float]; fd: List[str]; fl: List[str]
    fm, fb, fd, fl = [], [], [], []
    prev = 0.0
    n = len(mel)
    for i in range(n):
        be = beats[i] if i < len(beats) else prev
        be = round(be / grid) * grid          # 스냅
        if be < prev:                          # 역전 방지
            be = prev
        if total_beats is not None and be > total_beats:
            be = total_beats
        fm.append(mel[i]); fb.append(be)
        fd.append(dyn[i] if i < len(dyn) else "mf")
        fl.append(lyr[i] if i < len(lyr) else "")
        prev = be
    return fm, fb, fd, fl

def clip_and_fill_rests(mel: List[Note], beats: List[float], dyn: List[str], lyr: List[str],
                        dur_max: float = 2.0, grid: float = 0.25
                        ) -> Tuple[List[Note], List[float], List[str], List[str]]:
    """
    - 각 노트의 길이가 dur_max를 넘으면 grid 단위로 분할
    - 인접 이벤트 사이에 '구멍'이 있으면 'rest'로 채움(길이는 간격)
    - 반환은 플랫 시퀀스 유지
    """
    if not mel:
        return [], [], [], []
    out_m: List[Note]; out_b: List[float]; out_d: List[str]; out_l: List[str]
    out_m, out_b, out_d, out_l = [], [], [], []

    start = 0.0
    n = len(mel)
    for i in range(n):
        end = beats[i]
        dur = end - start
        # 첫 이벤트 전에 공백이 있으면 rest로 채움
        if dur > grid and (i == 0 or (i > 0 and mel[i-1] == 'rest')):
            out_m.append('rest'); out_b.append(end)
            out_d.append("mp");   out_l.append("")
        # 길이 분할
        n_slices = max(1, int(round(dur / dur_max)))
        slice_len = dur / n_slices if n_slices > 0 else dur
        acc = start
        for _ in range(n_slices):
            acc += slice_len
            out_m.append(mel[i]); out_b.append(acc)
            out_d.append(dyn[i] if i < len(dyn) else "mf")
            out_l.append(lyr[i] if i < len(lyr) else "")
        start = end

    return out_m, out_b, out_d, out_l