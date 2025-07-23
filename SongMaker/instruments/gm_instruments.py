# instruments/gm_instruments.py
from music21 import instrument

def gm_instrument(program_num):
    """GM program 번호로 instrument 반환."""
    inst = instrument.Instrument()
    inst.midiProgram = program_num
    return inst

# 대표 악기 미리 정의
def get_rock_band_instruments():
    return {
        'synth': gm_instrument(81),       # Lead 2 (sawtooth)
        'elec_guitar': gm_instrument(30), # Overdriven Guitar
        'acoustic_guitar': gm_instrument(25),
        'bass': gm_instrument(33),        # Electric Bass(finger)
        'drum': instrument.SnareDrum(),   # 드럼은 GM이지만, music21 표준 객체 사용
    }

