import os
import sys

import json
import torch
import numpy as np
import soundfile as sf

# 경로 설정 (변경 반영됨)
mel_path = "/Users/simjuheun/Desktop/myProject/Use_Magenta/MIDItowave/test/0ec264d4f0b5938d9d074e4b252e9d5e.npy"
checkpoint_path = "/hifi_gan_Chords/hifi-gan/universal/g_02500000"
config_path = "/hifi_gan_Chords/hifi-gan/universal/config.json"
output_path = "/hifi_gan_Chords/audioResult/0ec264d4f0b5938d9d074e4b252e9d5e_generated.wav"

# sys.path 추가 (모델 임포트를 위한 경로)
sys.path.append("/hifi_gan_Chords/hifi-gan")
from models import Generator


# AttrDict
class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


# Config 로드
with open(config_path) as f:
    config = AttrDict(json.load(f))

# 디바이스 설정
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 모델 로드
model = Generator(config).to(device)
checkpoint = torch.load(checkpoint_path, map_location=device)
model.load_state_dict(checkpoint["generator"])
model.eval()
model.remove_weight_norm()
print("✅ Generator 로드 완료")

# mel 로드 + 평균 에너지 정규화
mel = np.load(mel_path)
mean_energy = np.mean(mel)
if mean_energy < 1.0:
    scale_factor = 1.0 / (mean_energy + 1e-6)
    mel *= scale_factor
    print(f"🔧 평균 에너지 낮음 → 스케일 보정 적용: x{scale_factor:.2f}")

# 추론
mel_tensor = torch.FloatTensor(mel).unsqueeze(0).to(device)
with torch.no_grad():
    audio = model(mel_tensor).squeeze().cpu().numpy()

# 정규화 후 저장
audio = audio / np.max(np.abs(audio))
sf.write(output_path, audio, config.sampling_rate)

print(f"🎧 오디오 저장 완료: {output_path}")
print(f"🔍 MEL shape: {mel.shape} | mean: {mel.mean():.4f}, min: {mel.min():.4f}, max: {mel.max():.4f}")
print(f"🔊 Audio stats → shape: {audio.shape}, min: {audio.min():.4f}, max: {audio.max():.4f}, mean: {audio.mean():.4f}")