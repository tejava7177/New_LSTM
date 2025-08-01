# SongMaker/Patterns_Rock/Guitar/rhythmGuitarPatterns.py
import random
from typing import List, Tuple

# --------- 기본 유틸 ---------
def chord_notes_map(ch: str) -> List[str]:
    """코드명 -> 간단한 트라이어드(저역) 맵."""
    base = {
        "C": ["C3", "E3", "G3"],
        "G": ["G3", "B3", "D4"],
        "Am": ["A3", "C4", "E4"],
        "F": ["F3", "A3", "C4"],
        "D": ["D3", "F#3", "A3"],
        "Em": ["E3", "G3", "B3"],
        "Bm": ["B2", "D3", "F#3"],
        "E": ["E3", "G#3", "B3"],
    }
    return base.get(ch, ["C3", "E3", "G3"])


def _as_list(pitches):
    """단일 음도 내부 표현은 리스트로 통일."""
    if pitches == "rest":
        return ["rest"]
    if isinstance(pitches, str):
        return [pitches]
    return list(pitches)


def _add_event(
    mel: List[List[str]],
    beats: List[float],
    dyn: List[str],
    lyr: List[str],
    t: float,
    pitches,
    dur: float,
    dynamic: str = "mf",
    lyric: str = "",
) -> float:
    """이벤트 1개 추가하고 누적 beat_end(t)를 반환."""
    mel.append(_as_list(pitches))
    t += float(dur)
    beats.append(t)
    dyn.append(dynamic)
    lyr.append(lyric)
    return t


def normalize_to_total_beats(
    mel: List[List[str]],
    beats: List[float],
    dyn: List[str],
    lyr: List[str],
    total_beats: float,
    fill="rest",
) -> Tuple[List[List[str]], List[float], List[str], List[str]]:
    """마지막 beat_end를 total_beats로 강제 정렬.
    - 초과분은 잘라내고, 부족분은 하나의 이벤트로 채운다.
    """
    # 길이 동일성 보장
    n = min(len(mel), len(beats), len(dyn), len(lyr))
    del mel[n:]; del beats[n:]; del dyn[n:]; del lyr[n:]

    # 1) 초과분 제거
    while beats and beats[-1] > total_beats + 1e-9:
        mel.pop(); beats.pop(); dyn.pop(); lyr.pop()

    # 2) 부족분 채우기
    if not beats or beats[-1] < total_beats - 1e-9:
        remain = total_beats - (beats[-1] if beats else 0.0)
        # 마지막 이벤트로 채움
        mel.append(_as_list(fill))
        beats.append(total_beats)
        dyn.append("mp")
        lyr.append("")
    return mel, beats, dyn, lyr


# --------- 메인 패턴 생성 ---------
def generate_rock_rhythm_guitar(
    chords: List[str],
    style: str = "power8",     # "power8" | "sync16" | "offChop"
    chug_prob: float = 0.30,   # 일부 16분 척 느낌
    accent: str = "2&4",       # 억양 힌트(현재는 단순 사용)
) -> Tuple[List[List[str]], List[float], List[str], List[str]]:
    """
    리듬 기타 트랙 생성.
    반환: melodies(List[List[str]]), beat_ends(List[float]), dynamics(List[str]), lyrics(List[str])
    """
    mel: List[List[str]] = []
    beats: List[float] = []
    dyn: List[str] = []
    lyr: List[str] = []
    t = 0.0

    for ch in chords:
        triad = chord_notes_map(ch)
        power = [triad[0], triad[2]]  # 루트 + 5도 (파워코드 간략 모델)

        if style == "power8":
            # 8분 스트럼(파워코드). 2,4박 살짝 강조.
            for i in range(8):
                dur = 0.5
                hit = power
                # 백비트 전후로 짧게 끊는 척 느낌(음은 동일, 리듬만 짧아지는 연출은 score_helper에서 길이로 구현됨)
                # 여기서는 음만 유지.
                emph = (i in (2, 6))
                t = _add_event(mel, beats, dyn, lyr, t, hit, dur, "f" if emph else "mf")

        elif style == "sync16":
            # 16분 싱코페이션(앤드/백비트 길이 부여)
            pattern = [
                0.25, 0.25, 0.5, 0.25,
                0.25, 0.25, 0.5, 0.25,
                0.25, 0.25, 0.5, 0.25,
                0.25, 0.25, 0.5, 0.25,
            ]
            for idx, d in enumerate(pattern):
                # 1e&a 중 '앤드(두 번째 0.25 뒤)' 또는 3번째 슬롯에 약간 강조
                slot = idx % 4
                emph = (slot == 2)
                t = _add_event(mel, beats, dyn, lyr, t, power, d, "f" if emph else "mf")

        elif style == "offChop":
            # 오프비트 체프: 다운은 비우고 앤드에서 짧게 스트럼
            for _ in range(4):
                t = _add_event(mel, beats, dyn, lyr, t, "rest", 0.5, "mp")
                t = _add_event(mel, beats, dyn, lyr, t, power, 0.5, "mf")
        else:
            # 알 수 없는 스타일은 기본 power8
            for i in range(8):
                t = _add_event(mel, beats, dyn, lyr, t, power, 0.5, "mf")

    # ---- 길이 정규화: 항상 4 * len(chords) 에 맞춘다 ----
    total_beats = 4.0 * len(chords)
    mel, beats, dyn, lyr = normalize_to_total_beats(mel, beats, dyn, lyr, total_beats, fill="rest")

    return mel, beats, dyn, lyr


# ---------- 간단 테스트 ----------
if __name__ == "__main__":
    test_chords = ["Am", "F", "C", "G"] * 2
    for st in ("power8", "sync16", "offChop"):
        m, b, d, l = generate_rock_rhythm_guitar(test_chords, style=st)
        print(st, "→ events:", len(m), "last beat:", b[-1])