import kagglehub
import os
import zipfile
import pandas as pd

# 데이터셋 다운로드
print("🔄 Downloading Lakh MIDI Clean...")
path = kagglehub.dataset_download("imsparsh/lakh-midi-clean")

# 디렉토리 구조 정의
midi_dir = os.path.join(path, "clean_midi")
meta_path = os.path.join(path, "metadata.csv")  # 또는 .json 버전

# Rock MIDI만 추출
rock_dir = "./data/rock_midi"
os.makedirs(rock_dir, exist_ok=True)

# 메타데이터 읽기
df = pd.read_csv(meta_path)

rock_files = df[df['genre'].str.lower() == 'rock']['filename'].tolist()

print(f"🎸 Rock 장르 MIDI {len(rock_files)}개 추출 중...")

for f in rock_files:
    src = os.path.join(midi_dir, f)
    dst = os.path.join(rock_dir, f)
    if os.path.exists(src):
        os.link(src, dst)  # 또는 shutil.copy() 대체 가능

print(f"✅ Rock MIDI 저장 완료: {rock_dir}")