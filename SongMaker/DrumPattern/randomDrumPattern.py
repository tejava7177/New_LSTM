# randomDrumPattern.py
import random

def generate_random_drum_pattern(measures=8, beats_per_measure=4):
    # General MIDI Drum Map (music21 기준 pitch name)
    KICK = "C2"
    SNARE = "D2"
    HIHAT = "F#2"

    melodies = []
    beat_ends = []
    dynamics = []
    lyrics = []
    current_beat = 0.0

    for m in range(measures):
        for b in range(beats_per_measure):
            beat_drums = []
            # 하이햇 기본 (대부분 박자에 등장)
            if random.random() < 0.9:
                beat_drums.append(HIHAT)
            # 킥, 스네어는 변칙적으로 (예시 확률)
            if b == 0 or random.random() < 0.5:
                beat_drums.append(KICK)
            if b == 1 or random.random() < 0.4:
                beat_drums.append(SNARE)
            if not beat_drums:
                beat_drums = ["rest"]
            melodies.append(beat_drums)
            current_beat += 1.0
            beat_ends.append(current_beat)
            dynamics.append("mf")
            lyrics.append("")
    return melodies, beat_ends, dynamics, lyrics