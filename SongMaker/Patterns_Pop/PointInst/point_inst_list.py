# Patterns_Pop/PointInst/point_inst_list.py
from music21 import instrument

# 사용자 입력 이름 → music21 악기
POINT_CHOICES_POP = {
    # 팝에서 포인트 주기 좋은 악기들
    "glockenspiel": instrument.Glockenspiel(),
    "celesta":      instrument.Celesta(),
    "vibes":        instrument.Vibraphone(),
    "marimba":      instrument.Marimba(),
    "bells":        instrument.TubularBells(),
    "flute":        instrument.Flute(),
    "clarinet":     instrument.Clarinet(),
    #"strings":      instrument.StringEnsemble1(),  # 가벼운 스트링 레이어
    "nylon_guitar": instrument.AcousticGuitar(),
    "clean_guitar": instrument.ElectricGuitar(),
    #"lead_square":  instrument.SquareLead(),
    #"lead_saw":     instrument.SawtoothLead(),
    "synth_bell":   instrument.ElectricPiano(),    # 대체(벨톤 계열이 없을 때 가볍게)
}

def get_point_instrument(name):
    return POINT_CHOICES_POP.get(name.lower().strip())

def select_point_instruments():
    """
    쉼표로 여러 악기 입력(없으면 none). 예: 'glockenspiel, flute'
    반환: [(name, instrument), ...]
    """
    print("🎯 POP 포인트 악기 선택(쉼표로 여러 개 가능)")
    print("   선택지:", ", ".join(POINT_CHOICES_POP.keys()))
    print("   (아무것도 입력하지 않으면 'none'으로 처리)")
    text = input("포인트 악기 입력 (예: glockenspiel, flute): ").strip().lower()

    if not text or text == "none":
        return []

    result = []
    for raw in text.split(","):
        nm = raw.strip()
        if not nm:
            continue
        inst = get_point_instrument(nm)
        if inst is None:
            print(f"⚠️  알 수 없는 악기 '{nm}' (건너뜁니다)")
            continue
        result.append((nm, inst))
    return result