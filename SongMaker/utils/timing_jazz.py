# utils/timing.py
def fix_beats(mel, beats, dyn, lyr, grid=0.25, total_beats=None):
    """
    - beats를 0부터 증가하는 누적 끝박으로 스냅(grid) 정렬
    - 음수/역전 제거, total_beats 넘어가면 잘라냄
    """
    if not mel: return [], [], [], []
    fm, fb, fd, fl = [], [], [], []
    prev = 0.0
    for i in range(len(mel)):
        be = beats[i] if i < len(beats) else prev
        # 스냅
        be = round(be / grid) * grid
        if be < prev:     # 역전 방지
            be = prev
        if total_beats is not None and be > total_beats:
            be = total_beats
        fm.append(mel[i]); fb.append(be)
        fd.append(dyn[i] if i < len(dyn) else "mf")
        fl.append(lyr[i] if i < len(lyr) else "")
        prev = be
    return fm, fb, fd, fl


def clip_and_fill_rests(mel, beats, dyn, lyr, dur_max=2.0, grid=0.25):
    """
    - 각 노트의 길이가 dur_max를 넘으면 grid 단위로 분할
    - 인접 이벤트 사이에 '구멍'이 있으면 'rest'로 채움(길이는 간격)
    - 반환은 여전히 플랫 시퀀스
    """
    if not mel: return [], [], [], []
    out_m, out_b, out_d, out_l = [], [], [], []

    start = 0.0
    for i in range(len(mel)):
        end = beats[i]
        dur = end - start
        # 휴지 채우기
        if dur > grid and (i == 0 or (i > 0 and mel[i-1] == 'rest')):
            # 첫 노트 이전에 공백이 생기면 rest 추가
            out_m.append('rest'); out_b.append(end)
            out_d.append("mp");   out_l.append("")
        # 길이 클립/분할
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