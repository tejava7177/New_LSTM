import json
import re

input_json = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/pop_midi/pop_chords_cleaned.json"
output_json = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/cli/data/pop_midi/pop_chords_normalized.json"

# 허용 패턴 정의
ROOT = r'([A-G][b#]?)'
QUALITY = (
    r'(maj7?|M7?|m7?|min7?|dim7?|aug|sus2|sus4|'    # 주요 접미사
    r'add\d{1,2}|'                                  # add9, add11
    r'6|7|9|11|13)?'                                # 단일 확장
)
# 합법 조합: 루트 + 여러 확장 (최대 3개까지 연속 허용, 예: Cmaj7add9sus4)
CHORD_PATTERN = re.compile(f'^{ROOT}({QUALITY}){{0,3}}$', re.I)

# 코드 정규화 함수
def normalize_chord(chord):
    chord = chord.strip()
    chord = chord.split('/')[0]  # 슬래시 이후 제거
    chord = chord.replace('♯', '#').replace('♭', 'b').lower()

    # 자주 나타나는 이상치 사전 정리
    chord = re.sub(r'sus(sus)+', 'sus', chord)
    chord = re.sub(r'([a-g][#b]?)(s?3d|as3d)', r'\1dim', chord)  # Fs3d, As3d → Fdim, Adim
    chord = re.sub(r'addadd', 'add', chord)
    chord = re.sub(r'mi+', 'm', chord)       # mi, mii 등 → m
    chord = re.sub(r'min', 'm', chord)
    chord = re.sub(r'majmaj', 'maj', chord)

    # 품사 허용 토큰만 뽑기
    tokens = re.findall(r'(maj7?|M7?|m7?|dim7?|aug|sus2|sus4|add\d{1,2}|6|7|9|11|13)', chord)
    root_match = re.match(r'^[a-g][#b]?', chord)
    if not root_match:
        return ''
    root = root_match.group().capitalize()
    tail = ''.join(tokens)
    final = root + tail

    # 최종 허용 패턴 아니면 빈 값
    if not CHORD_PATTERN.match(final):
        return ''
    return final

# JSON 로드
with open(input_json, 'r', encoding='utf-8') as f:
    data = json.load(f)

progressions = data.get("pop_chord_progressions", [])
normalized_progressions = []

for line in progressions:
    chords = line.split()
    normalized_chords = [normalize_chord(ch) for ch in chords if ch.strip()]
    # 빈 스트링은 자동 제거
    normalized_chords = [ch for ch in normalized_chords if ch]
    if normalized_chords:
        normalized_progressions.append(" ".join(normalized_chords))

# JSON 저장
out = {"pop_chord_progressions": normalized_progressions}
with open(output_json, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"✅ 정규화 완료! 총 {len(normalized_progressions)}개의 진행이 저장됨.")
print(f"→ 저장 위치: {output_json}")