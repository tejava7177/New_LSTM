# make_midi_test/generate_bass_backing_track.py
import os
from SongMaker.make_midi_test.useSongMaker_jazz_test import generate_jazz_track_test

if __name__ == "__main__":
    BASE = os.path.dirname(__file__)
    OUT  = os.path.join(BASE, "out")
    progression = ["Cmaj7","Am7","Dm7","G7"]*2

    result = generate_jazz_track_test(
        progression=progression,
        tempo=140,
        drum="brush_ballad",      # 잔잔
        comp="shell",              # 희박 컴핑
        guitar="none",
        lead="none",
        lead_per_bar=(1, 1),       # 마디당 1음
        lead_register=(64, 81),
        lead_tension_prob=0.10,
        out_dir=OUT,
        seed=20241008,
    )
    print(result)