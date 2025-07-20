# debug_utils.py  ─────────────────────────────────────
from fractions import Fraction
def inspect_beats(name, beat_ends):
    """
    ① 단조 증가 여부
    ② 차이(길이) 목록
    ③ music21 이 표현 가능한 분수인지 확인
    """
    problems = False
    print(f"\n▼ {name}  총 {len(beat_ends)} events")
    for i, (b1, b2) in enumerate(zip(beat_ends, beat_ends[1:]), start=1):
        if b2 <= b1:
            print(f"  !! 역순/중복 at idx {i}: {b1} → {b2}")
            problems = True

    diffs = [round(b2 - b1, 5) for b1, b2 in zip([0.0] + beat_ends, beat_ends)]
    diff_set = sorted(set(diffs))
    print("  길이 종류:", diff_set[:12], "..." if len(diff_set) > 12 else "")
    # music21 은 대부분 (1/16=0.0625) 이상의 2⁻ⁿ 계열 분수를 표현
    for d in diff_set:
        f = Fraction(d).limit_denominator(128)   # 128분음표까지 허용
        if abs(float(f) - d) > 1e-6:
            print(f"  !! 애매한 길이 {d} → {f}")
            problems = True
    return problems