import csv
import json
import re

input_csv = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/chordonomicon.csv"
output_json = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/jazz_midi/jazz_chords_cleaned.json"

def is_tag(token):
    return token.startswith('<') and token.endswith('>')

def normalize_jazz_chord(chord):
    chord = chord.split('/')[0]
    # 주요 재즈 확장코드까지 커버 (필요시 패턴 확장)
    match = re.match(r"^([A-G][b#]?((m|M)?(aj)?(add)?(6|7|9|11|13|sus4|dim7?|aug)?))", chord)
    return match.group(1) if match else chord

progressions = []

with open(input_csv, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['main_genre'].lower() == 'jazz':
            chords = row['chords']
            # 태그(<verse_1> 등) 제거
            tokens = [c for c in chords.split() if not is_tag(c)]
            # 정규화
            norm_tokens = [normalize_jazz_chord(c) for c in tokens if c]
            if norm_tokens and any(len(ch) > 0 for ch in norm_tokens):
                progressions.append(" ".join(norm_tokens))

out = {"jazz_chord_progressions": progressions}

with open(output_json, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"✅ 재즈 코드 정규화 완료! {len(progressions)}개 진행 → {output_json}")