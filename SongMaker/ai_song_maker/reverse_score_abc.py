from music21 import key, meter, tempo, clef
from fractions import Fraction

def convert_to_nearest_fraction(duration):
    if duration < 1 / 16:
        return '0'
    fractions = [
        (Fraction(7, 1), '7'), (Fraction(6, 1), '6'), (Fraction(5, 1), '5'), (Fraction(4, 1), '4'), (Fraction(3, 1), '3'), (Fraction(2, 1), '2'),
        (Fraction(3, 2), '3/2'), (Fraction(1, 1), ''), (Fraction(3, 4), '3/4'), (Fraction(1, 2), '1/2'),
        (Fraction(3, 8), '3/8'), (Fraction(1, 4), '1/4'), (Fraction(1, 8), '1/8'), (Fraction(1, 16), '1/16')
    ]
    for fraction, notation in fractions:
        if duration >= fraction:
            return notation
    return ''

def midi_note_to_abc(note: str) -> str:
    if note == '' or note == 'rest':
        return ''
    pitch = note[:-1]
    try:
        octave = int(note[-1])
    except:
        print("unrecognized note: " + note)
    note_map = {
        'C': 'C', 'C#': '^C', 'Db': '_D', 'D': 'D', 'D#': '^D', 'Eb': '_E', 'E': 'E', 'F': 'F', 'F#': '^F', 'Gb': '_G', 'G': 'G', 'G#': '^G',
        'Ab': '_A', 'A': 'A', 'A#': '^A', 'Bb': '_B', 'B': 'B'
    }
    abc_note = note_map.get(pitch, pitch)
    if octave == 5:
        return abc_note.lower()
    elif octave == 6:
        return abc_note.lower() + "'"
    elif octave == 7:
        return abc_note.lower() + "''"
    elif octave == 3:
        return abc_note + ","
    elif octave == 2:
        return abc_note + ",,"
    elif octave == 1:
        return abc_note + ",,,"
    return abc_note

def convert_parts_to_abc(parts_data, score_data):
    # Set default values
    title = score_data.get('title', 'Untitled')
    time_signature = score_data.get('time_signature', meter.TimeSignature('4/4')).ratioString
    tempo_value = score_data.get('tempo', tempo.MetronomeMark(number=120)).number
    key_signature = score_data.get('key', key.Key('C', 'major'))
    clef_type = score_data.get('clef', clef.TrebleClef()).name

    abc_string = f"M:{time_signature}\nT:{title}\nQ:1/4={tempo_value}\nK:{key_signature.tonicPitchNameWithCase} {key_signature.mode.capitalize()}\n"
    n = 1

    for part_name, part_data in parts_data.items():
        abc_string += f"V:{n} clef={clef_type} name={part_name}\n"
        beat_ends = part_data['beat_ends']
        melodies = part_data['melodies']
        n += 1
        current_time = 0
        beat_count = 0
        note_count = 0
        line_beat_total = 0

        for i, (end_time, melody) in enumerate(zip(beat_ends, melodies)):
            start_time = current_time
            duration = end_time - start_time
            rest_duration = convert_to_nearest_fraction(Fraction(duration).limit_denominator(16))
            if rest_duration == '0':
                continue
            if melody == '':
                abc_string += f"z{rest_duration} "
            elif isinstance(melody, list):
                abc_string += f"[{''.join(midi_note_to_abc(note) for note in melody)}]{rest_duration} "
            else:
                abc_string += f"{midi_note_to_abc(melody)}{rest_duration} "

            current_time = end_time
            if rest_duration == "":
                rest_duration = 1
            beat_count += Fraction(rest_duration)
            line_beat_total += Fraction(rest_duration)
            note_count += 1

            if beat_count >= 4:
                abc_string += '| '
                beat_count = 0

            if note_count >= 15:
                abc_string += f"% {line_beat_total} \n"
                note_count = 0
                line_beat_total = 0

        # Add the remaining beats total for the last line if it has less than 15 notes
        if note_count > 0:
            abc_string += f"% {line_beat_total} \n"

        abc_string += "\n"

    return abc_string

