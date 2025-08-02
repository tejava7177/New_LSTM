# Patterns_Jazz/PointInst/point_inst_list.py
from music21 import instrument

# 사용자가 입력할 이름 → music21 악기 객체
POINT_CHOICES_JAZZ = {
    "vibes":            instrument.Vibraphone(),
    "clarinet":         instrument.Clarinet(),
    "trumpet":          instrument.Trumpet(),
    #"muted_trumpet":    instrument.MutedTrumpet(),
    "alto_sax":         instrument.AltoSaxophone(),
    "tenor_sax":        instrument.TenorSaxophone(),
    "soprano_sax":      instrument.SopranoSaxophone(),
    "trombone":         instrument.Trombone(),
    "flute":            instrument.Flute(),
    "jazz_guitar":      instrument.ElectricGuitar(),
    "harmonica":        instrument.Harmonica(),
}

def get_point_instrument(name):
    """단일 이름 → instrument (없으면 None)"""
    return POINT_CHOICES_JAZZ.get(name.lower().strip())

def select_point_instruments():
    """
    쉼표로 여러 악기 입력 받기. 예: 'trumpet, flute'
    반환: [(name, instrument), ...]
    """
    print("🎯 포인트 악기를 선택하세요. 쉼표로 여러 개 가능")
    print("   선택지:", ", ".join(POINT_CHOICES_JAZZ.keys()))
    print("   (아무것도 입력하지 않으면 'none'으로 처리)")
    text = input("포인트 악기 입력 (예: trumpet, flute): ").strip().lower()

    if not text or text == "none":
        return []

    result = []
    for raw in text.split(","):
        name = raw.strip()
        if not name:
            continue
        inst = get_point_instrument(name)
        if inst is None:
            print(f"⚠️  알 수 없는 악기 '{name}' (건너뜁니다)")
            continue
        result.append((name, inst))
    return result