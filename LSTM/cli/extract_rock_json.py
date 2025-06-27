import json
import re

input_path = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_chords_cleaned_no_tag.json"
output_path = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/rock_chords_rich_normalized.json"

def normalize_chord(chord):
    chord = chord.split('/')[0]
    # C, Cm, C7, C5, Csus4, Cdim, Caug, Cmaj7까지 남김 (더 확장 가능)
    match = re.match(r"^([A-G][b#]?((m|M)?(aj)?(7|5|sus4|dim|aug)?))", chord)
    return match.group(1) if match else chord

with open(input_path, "r", encoding="utf-8") as f:
    data = json.load(f)

normalized_seqs = []
for seq in data["rock_chord_progressions"]:
    chords = seq.split()
    norm_chords = [normalize_chord(c) for c in chords]
    # 완전히 비는 진행은 삭제
    if norm_chords and any(len(ch) > 0 for ch in norm_chords):
        normalized_seqs.append(" ".join(norm_chords))

out = {"rock_chord_progressions": normalized_seqs}
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"✅ 코드 정규화(파워코드 등 유지) 완료! {len(normalized_seqs)}개 코드 진행 → {output_path}")