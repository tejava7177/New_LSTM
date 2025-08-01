# SongMaker/Patterns_Rock/Drum/rockDrumPatterns.py
import random

# GM 드럼 맵(피치 이름): Kick=C2, Snare=D2, ClosedHat=F#2, OpenHat=A#2, Tom=E2/G2/A2, Crash=C#3 등
KICK = "C2"; SNARE = "D2"; CH = "F#2"; OH = "A#2"
TOM1 = "E2"; TOM2 = "G2"; TOMF = "A2"; CRASH = "C#3"

def _emit(events, t, pitches, dur):
    """events(list)에 (피치들, 종료비트) 추가."""
    if isinstance(pitches, str):
        pitches = [pitches]
    events.append((pitches, t + dur))
    return t + dur

def _fill_bar(style="fill16"):
    """간단한 1마디 필(필요 시 응용)."""
    t = 0.0; ev=[]
    if style == "fill16":
        # 16분 노트로 스네어/탐 롤 → 마지막에 크래시
        seq = [SNARE, SNARE, TOM1, TOM2, TOMF, TOM2, TOM1, SNARE]
        for p in seq:
            t = _emit(ev, t, [p, CH], 0.25)
        t = _emit(ev, t, [CRASH, KICK], 0.5)  # 다운비트 충돌
        t = _emit(ev, t, CH, 0.5)
    else:
        for _ in range(3):
            t = _emit(ev, t, [SNARE, CH], 0.5)
        t = _emit(ev, t, [CRASH, KICK], 1.0)
    return ev

def generate_rock_drum_pattern(measures=8, style="straight8", density="med", fill_prob=0.12, seed=None):
    """
    반환: melodies(list[list[str] or list[str]]), beat_ends(list[float]), dynamics(list[str]), lyrics(list[str])
    style: "straight8", "straight16", "halfTime", "punk8", "tomGroove"
    density: "low" | "med" | "high"  → 하이햇 개수/오픈 정도
    """
    if seed is not None:
        random.seed(seed)

    hat_rate = {"low": 0.75, "med": 0.9, "high": 1.0}[density]
    open_hat_chance = {"low": 0.02, "med": 0.06, "high": 0.12}[density]

    melodies=[]; beats=[]; dyn=[]; lyr=[]
    t=0.0

    for m in range(measures):
        bar=[]
        # 1) 하이햇/킥/스네어 기본 골격
        if style in ("straight8", "punk8"):
            # 8분 하이햇, 2/4 스네어, 킥은 1·3 중심 + 랜덤 추가
            for i in range(8):
                have_hat = random.random() < hat_rate
                if have_hat:
                    hat = OH if random.random() < open_hat_chance else CH
                    t = _emit(bar, t, hat, 0.5)
                else:
                    t = _emit(bar, t, "rest", 0.5)

                # 킥(1,3 강세) + 가끔 싱코
                if i in (0,4) or (random.random() < 0.25 and i not in (2,6)):
                    beats[-1:]  # no-op (명시적)
                    bar[-1] = (bar[-1][0] + [KICK] if bar[-1][0] != ["rest"] else [KICK], bar[-1][1])

                # 스네어(2,4)
                if i in (2,6):
                    bar[-1] = (bar[-1][0] + [SNARE] if bar[-1][0] != ["rest"] else [SNARE], bar[-1][1])

        elif style == "straight16":
            # 16분 하이햇, 2/4 스네어, 킥은 1·3 + 랜덤
            for i in range(16):
                hat = OH if random.random() < open_hat_chance else CH
                t = _emit(bar, t, hat, 0.25)
                if i in (4,12):  # 2,4박 스네어
                    bar[-1] = (bar[-1][0] + [SNARE], bar[-1][1])
                if i in (0,8) or (random.random() < 0.18 and i not in (4,12)):
                    bar[-1] = (bar[-1][0] + [KICK], bar[-1][1])

        elif style == "halfTime":
            # 하프타임: 스네어 3박, 킥은 1박, 하이햇 8분
            for i in range(8):
                hat = OH if random.random() < open_hat_chance else CH
                t = _emit(bar, t, hat, 0.5)
                if i == 0:
                    bar[-1] = (bar[-1][0] + [KICK], bar[-1][1])
                if i == 4:  # 3박 위치(=마디 3)
                    bar[-1] = (bar[-1][0] + [SNARE], bar[-1][1])

        elif style == "tomGroove":
            # 탐 위주의 8분 그루브
            tom_seq = [TOM1, TOM2, TOMF, TOM2]*2
            for i,p in enumerate(tom_seq):
                t = _emit(bar, t, [p, CH], 0.5)
                if i in (2,6):  # 2,4박 스네어 살짝
                    bar[-1] = (bar[-1][0] + [SNARE], bar[-1][1])
                if i in (0,4):
                    bar[-1] = (bar[-1][0] + [KICK], bar[-1][1])

        # 2) 가끔 필
        if random.random() < fill_prob:
            bar = _fill_bar()

        # 누적 반영
        for pitches, end in bar:
            melodies.append(pitches if pitches != "rest" else ["rest"])
            beats.append(end)
            dyn.append("mf")
            lyr.append("")
    return melodies, beats, dyn, lyr