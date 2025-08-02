# Patterns_Pop/Drum/popDrumPatterns.py
import random

KICK  = "C2"   # Bass Drum (GM)
SNARE = "D2"   # Snare (GM)
HAT   = "F#2"  # Closed Hi-hat (GM)
CLAP  = "D#2"  # Hand Clap (GM)

def _emit(mel, beats, dyn, lyr, t, pitches, dur, vel="mf", text=""):
    if isinstance(pitches, str):
        pitches = [pitches]
    t += dur
    mel.append(pitches)
    beats.append(t)
    dyn.append(vel)
    lyr.append(text)
    return t

def generate_pop_drum_pattern(measures=8, style="fourFloor", clap_prob=0.5, hat_fill_prob=0.15, seed=None):
    """
    style: 'fourFloor' | 'backbeat' | 'halfTime' | 'edm16'
      - fourFloor: 킥 4온더플로어 + 8분 하이햇, 스네어 2/4 + 확률적 클랩
      - backbeat : 킥 1&3 중심, 스네어 2/4, 하이햇 8분
      - halfTime : 스네어만 박자3, 킥은 느슨
      - edm16    : 16분 하이햇 + 4온더플로어 킥
    반환: melodies, beat_ends, dynamics, lyrics
    """
    if seed is not None:
        random.seed(seed)

    mel, beats, dyn, lyr = [], [], [], []
    t = 0.0

    for m in range(measures):
        if style == "fourFloor":
            # 1마디 = 4/4
            grid = [0.5]*8  # 8분
            for i in range(8):
                # 킥: 4온더플로어
                if i in (0,2,4,6):
                    t = _emit(mel, beats, dyn, lyr, t, [KICK, HAT], 0.5, vel="mf")
                else:
                    t = _emit(mel, beats, dyn, lyr, t, HAT, 0.5, vel="mp")
                # 스네어 2/4 + 클랩 레이어(확률)
                if i == 2 or i == 6:
                    mel[-1] = mel[-1] + [SNARE]
                    if random.random() < clap_prob:
                        mel[-1] = mel[-1] + [CLAP]

        elif style == "backbeat":
            # 킥 1, "& of 2", 3 약간 / 스네어 2/4 / 하이햇 8분
            for i in range(8):
                hits = [HAT]
                if i in (0,4):          # 1,3
                    hits = [KICK, HAT]
                if i in (1,5) and random.random() < 0.4:  # & of 1/3 보강
                    hits = [KICK, HAT]
                if i in (2,6):          # 2,4 스네어
                    hits = hits + [SNARE]
                    if random.random() < clap_prob:
                        hits = hits + [CLAP]
                t = _emit(mel, beats, dyn, lyr, t, hits, 0.5, vel="mf")

        elif style == "halfTime":
            # 하프타임: 스네어 박자3, 킥은 앞쪽/뒤쪽 느슨 / 하이햇 8분
            for i in range(8):
                hits = [HAT]
                if i in (0,1) and random.random() < 0.8:  # 앞쪽 킥
                    hits = [KICK, HAT]
                if i == 4:                                 # 박자3 스네어
                    hits = [HAT, SNARE]
                    if random.random() < clap_prob:
                        hits = hits + [CLAP]
                t = _emit(mel, beats, dyn, lyr, t, hits, 0.5, vel="mp" if i%2 else "mf")

        elif style == "edm16":
            # 16분 하이햇, 킥 4온더플로어, 스네어 2/4
            for i in range(16):
                dur = 0.25
                hits = [HAT]
                if i % 4 == 0:    # 1,2,3,4 다운비트 킥
                    hits = [KICK, HAT]
                if i in (8, 0):   # 리듬에 따라 downbeat마다 강세
                    pass
                if i in (4,12):   # 2,4 비트 스네어(다운)
                    hits = hits + [SNARE]
                    if random.random() < clap_prob:
                        hits = hits + [CLAP]
                # 16분 히트 중 일부 비워서 움직임
                if random.random() < hat_fill_prob:
                    hits = hits + [HAT]
                t = _emit(mel, beats, dyn, lyr, t, hits, dur, vel="mp" if i%2 else "mf")

        else:
            raise ValueError("Unsupported POP drum style.")

    return mel, beats, ["mf"]*len(mel), [""]*len(mel)