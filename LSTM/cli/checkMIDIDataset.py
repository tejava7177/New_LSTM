import kagglehub
import os

path = kagglehub.dataset_download("imsparsh/lakh-midi-clean")
print("🗂️ 다운로드된 파일 목록:")
print(os.listdir(path))