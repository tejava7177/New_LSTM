from music21 import instrument

# ───── 포인트 악기 목록 (필요에 따라 더 추가해도 됨) ─────
POINT_INSTRUMENTS = {
    "clarinet": instrument.Clarinet(),
    "trumpet": instrument.Trumpet(),
    "vibraphone": instrument.Vibraphone(),
    "alto_sax": instrument.AltoSaxophone(),
    "tenor_sax": instrument.TenorSaxophone(),
    "flute": instrument.Flute(),
    #"muted_trumpet": instrument.MutedTrumpet()
}

def select_point_instrument():
    print("포인트 악기를 선택하세요:")
    for idx, name in enumerate(POINT_INSTRUMENTS.keys(), 1):
        print(f"{idx}. {name}")
    while True:
        choice = input("번호 또는 이름 입력: ").strip().lower()
        if choice.isdigit() and 1 <= int(choice) <= len(POINT_INSTRUMENTS):
            return list(POINT_INSTRUMENTS.values())[int(choice)-1]
        elif choice in POINT_INSTRUMENTS:
            return POINT_INSTRUMENTS[choice]
        else:
            print("잘못 입력하셨습니다. 다시 선택해주세요.")

