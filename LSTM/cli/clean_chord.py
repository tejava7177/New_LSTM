import csv
import json
import re
import os

# 입력 및 출력 경로
input_csv = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/chordonomicon.csv"
output_json = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/pop_midi/pop_chords_cleaned.json"

# 태그인지 확인하는 함수 (예: <verse_1>)
def is_tag(token):
    return token.startswith('<') and token.endswith('>')

# Pop 장르용 코드 정규화 함수
def normalize_pop_chord(chord):
    chord = chord.split('/')[0]  # 슬래시 코드 제거 (예: C/G → C)
    chord = chord.replace('♯', '#').replace('♭', 'b')  # 유니코드 기호 정리
    chord = re.sub(r'[^A-Ga-g0-9#bmMaddsusdimaug+]+', '', chord)  # 특수문자 제거
    return chord.strip()

# 코드 진행 수집
progressions = []

with open(input_csv, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['main_genre'].lower() == 'pop':
            raw_chords = row['chords']
            tokens = [c for c in raw_chords.split() if not is_tag(c)]  # 태그 제거
            norm_chords = [normalize_pop_chord(c) for c in tokens if c]
            if norm_chords and any(len(ch) > 0 for ch in norm_chords):
                progressions.append(" ".join(norm_chords))

# JSON 저장 구조
out = {"pop_chord_progressions": progressions}

# 출력 디렉토리 생성
os.makedirs(os.path.dirname(output_json), exist_ok=True)

# JSON 저장
with open(output_json, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"✅ Pop 코드 진행 {len(progressions)}개 추출 및 정규화 완료 → {output_json}")