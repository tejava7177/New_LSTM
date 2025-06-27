import kagglehub
import os
import shutil

print("🔄 Downloading Lakh MIDI Clean...")
path = kagglehub.dataset_download("imsparsh/lakh-midi-clean")
midi_dir = os.path.join(path, "clean_midi")

output_dir = "./data/sample_midi"
os.makedirs(output_dir, exist_ok=True)

# 파일 몇 개만 복사해서 실험
count = 0
for filename in os.listdir(midi_dir):
    if filename.endswith(".mid") or filename.endswith(".midi"):
        shutil.copy(os.path.join(midi_dir, filename), os.path.join(output_dir, filename))
        count += 1
    if count >= 50:  # 50개만 샘플
        break

print(f"✅ {count}개의 MIDI 샘플이 {output_dir}에 복사되었습니다.")