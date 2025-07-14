# SongMaker/PianoPattern/randomPianoRhythm.py
import random

def random_rhythm_for_bar(total_beat=4.0, allowed_durations=[0.25, 0.5, 1.0, 1.5, 2.0]):
    durations = []
    remain = total_beat
    while remain > 0:
        possible = [d for d in allowed_durations if d <= remain]
        dur = random.choice(possible)
        durations.append(dur)
        remain -= dur
    return durations

def generate_random_piano_rhythms(num_bars, allowed_durations=None):
    if allowed_durations is None:
        allowed_durations = [0.25, 0.5, 1.0, 1.5, 2.0]
    return [random_rhythm_for_bar(total_beat=4.0, allowed_durations=allowed_durations) for _ in range(num_bars)]