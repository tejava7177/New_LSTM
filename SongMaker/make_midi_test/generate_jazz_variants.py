# make_midi_test/generate_jazz_variants.py
import os, time
from SongMaker.make_midi_test.useSongMaker_jazz_test import generate_jazz_track_test

# 같은 진행/장르/템포로도 결과가 매번 달라지는지 확인
progression = ["Cmaj7","Am7","Dm7","G7","Cmaj7","Am7","Dm7","G7"]  # 8 bars

OUT_DIR = "/Users/simjuheun/Desktop/myProject/New_LSTM/SongMaker/make_midi_test/out"
os.makedirs(OUT_DIR, exist_ok=True)

tempo = 148
N = 6  # 원하는 개수로 조정

for i in range(N):
    result = generate_jazz_track_test(
        progression=progression,
        tempo=tempo,
        drum="auto",
        comp="auto",
        point_inst="auto",      # 자동 편성
        point_density="medium",
        out_dir=OUT_DIR,
        seed=None               # None이면 매번 다른 seed
    )
    print(f"[{i}] {result['tag']} → {result['midi_path']}")
    time.sleep(0.2)

print(f"\n✅ Done. Check: {OUT_DIR}\n")