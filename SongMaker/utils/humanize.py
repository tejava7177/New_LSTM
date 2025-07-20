# SongMaker/utils/humanize.py
import random
from fractions import Fraction

def _q(x, step=0.125):          # 0.125 단위 퀀타이즈
    return round(x / step) * step

def humanize_melody(mels, ends, *, len_jitter=0.05, vel_base=80,
                    vel_jitter=5, rest_prob=0.0, snap=0.25):
    """
    returns new_mels, new_ends, velocities
    * snap = 0.25 → 16분음표 단위로 반올림
    """
    import random

    new_m, new_e, vels = [], [], []
    prev_end = 0.0

    for note, end in zip(mels, ends):
        # ―― 1) optional rest ――――――――――――――――――――――――――
        if random.random() < rest_prob:
            continue

        # ―― 2) Jitter (길이) ――――――――――――――――――――――――――
        jitter = random.uniform(-len_jitter, len_jitter)
        end += jitter

        # ―― 3) 최소 간격·단조 증가 보정 ――――――――――――――――――
        min_step = 1/32      # 32분음표 ≈ 0.125
        if end <= prev_end:
            end = prev_end + min_step

        # ―― 4) 그리드 스냅 (16분음표) ――――――――――――――――――
        end = round(end / snap) * snap
        if end <= prev_end:     # snap 로 다시 겹칠 경우 한 tick 더
            end += snap

        # ―― 5) 결과 추가 ―――――――――――――――――――――――――――
        new_m.append(note)
        new_e.append(end)
        vels.append(int(random.gauss(vel_base, vel_jitter)))

        prev_end = end

    return new_m, new_e, vels

def snap_beats(beat_ends, grid=0.25):
    """
    1. 지정된 그리드(기본 16분음표=0.25)에 맞춰 반올림
    2. 반올림 후에도 단조 증가가 깨지면 1-틱만큼 뒤로 밀어 중복 제거
    """
    snapped = []
    prev = -1.0
    for b in beat_ends:
        b = round(b / grid) * grid
        if b <= prev:          # 역순/중복 방지
            b = prev + grid
        snapped.append(b)
        prev = b
    return snapped