import re
from fractions import Fraction

from music21 import stream, note, chord, meter, key, tempo, clef, instrument, pitch, duration, tie, dynamics
from music21.note import GeneralNote
import random
from collections import deque

import os
import shutil
import time


def move_music_files_to_archive(directory, archive_directory='/mnt/data/midi_musicXML_archive'):
    # Ensure the archive directory exists, if not, create it
    if not os.path.exists(archive_directory):
        os.makedirs(archive_directory, exist_ok=True)

    # List all files in the given directory
    for filename in os.listdir(directory):
        if filename.endswith('.mid') or filename.endswith('.xml'):
            source_file_path = os.path.join(directory, filename)
            destination_file_path = os.path.join(archive_directory, filename)
            try:
                # Check the modification time of the file
                file_modified_time = os.path.getmtime(source_file_path)
                current_time = time.time()
                # If the file is older than 20 seconds, move it to the archive directory
                if current_time - file_modified_time > 120:
                    shutil.move(source_file_path, destination_file_path)
            except Exception as e:
                print(f"Error archiving {source_file_path} to {destination_file_path}: {e}")


def process_and_output_score(parts_data, score_data, musicxml_path='/mnt/data/song_musicxml.xml',
                             midi_path='/mnt/data/song_midi.mid', show_html=True, sheet_music_html_path='/mnt/data/sheet_music.html'):
    try:
        directory = os.path.dirname(musicxml_path)
        move_music_files_to_archive(directory)
    except Exception as e:
        print("failed to archive old files")

    score = stream.Score()
    queue = deque(parts_data.keys())

    while queue:
        part_id = queue.popleft()  # Dequeue the current part to process
        part_data = parts_data[part_id]  # Get the current part data
        melody_notes = get_section_data(part_data, 'melodies', get_section_data(part_data, 'chords', []))
        melody_rhythms = get_section_data(part_data, 'beat_ends', [])
        section_lyrics = get_section_data(part_data, 'lyrics', [])
        section_dynamics = get_section_data(part_data, 'dynamics', [])
        melody1_notes_updated = []
        melody1_rhythms_updated = []
        melody1_dynamics_updated = []
        melody2_notes_updated = []
        melody2_rhythms_updated = []
        melody2_dynamics_updated = []

        # Adjust the loop to correctly handle the identification of second duplicates and split accordingly
        for i in range(len(melody_notes)):
            note_str = melody_notes[i]
            if i >= len(melody_rhythms):
                melody_rhythms.append(melody_rhythms[i - 1] + 1)
            rhythm = melody_rhythms[i]
            dynamic = section_dynamics[i] if i < len(section_dynamics) else 'mf'  # Handle cases with fewer dynamics

            # Check if this rhythm is a duplicate and it's the second occurrence
            if i > 0 and melody_rhythms[i] == melody_rhythms[i - 1]:
                melody2_notes_updated.append(note_str)
                # Use the next rhythm value for the current note in the second melody, if available
                next_rhythm = melody_rhythms[i + 1] if i < len(melody_rhythms) - 1 else rhythm
                melody2_rhythms_updated.append(next_rhythm)
                if dynamic:
                    melody2_dynamics_updated.append(dynamic)
            else:
                if melody_rhythms[i] == 0:
                    next_rhythm = melody_rhythms[i + 1] if i < len(melody_rhythms) - 1 else rhythm
                    melody2_rhythms_updated.append(next_rhythm)
                    melody2_notes_updated.append(note_str)
                    if dynamic:
                        melody2_dynamics_updated.append(dynamic)
                else:
                    melody1_rhythms_updated.append(rhythm)
                    melody1_notes_updated.append(note_str)
                    if dynamic:
                        melody1_dynamics_updated.append(dynamic)

        # Updating part_data structure
        melody_notes = melody1_notes_updated
        melody_rhythms = melody1_rhythms_updated
        section_dynamics = melody1_dynamics_updated

        if len(melody2_notes_updated) > 0:
            part_name = part_id
            while part_name in parts_data:
                part_name = part_name + "Y"
            parts_data[part_name] = {}
            parts_data[part_name]["instrument"] = part_data["instrument"]
            parts_data[part_name]["melodies"] = melody2_notes_updated
            parts_data[part_name]["beat_ends"] = melody2_rhythms_updated
            parts_data[part_name]["dynamics"] = melody2_dynamics_updated
            queue.append(part_name)


        if len(melody_notes) == 0 or len(melody_rhythms) == 0:
            print("Skipping " + part_id + ". No melody or beat_ends array found." )
            continue

        if len(melody_notes) != len(melody_rhythms):
            print("Warning: " + part_id + " melodies array len: " + str(len(melody_notes)) +
                  " is not equal to beat_ends array len: " + str(len(melody_rhythms)) +
                  ". Each note element (e.g. 'C4') and chord element (e.g. ['C3', 'E3', 'G3'])  in the melodies array needs a beat_end value in the beat_ends array, vice versa. Otherwise the longer array will be truncated.")

        part = stream.Part()
        part.id = part_id
        score.append(part)

        # Set or override instrument, key, time signature, clef, and tempo if provided
        if 'instrument' in part_data:
            if isinstance(part_data['instrument'], instrument.Instrument):
                part.insert(0, part_data['instrument'])
            elif isinstance(part_data['instrument'], str):
                part_instrument = get_instrument_class_by_name(part_data['instrument'])
                part.insert(0, part_instrument)
            else:
                part.insert(0, instrument.Piano())

        key_sig = get_key_signature(part_data.get('key', score_data.get('key')))
        time_sig = get_time_signature(part_data.get('time_signature', score_data.get('time_signature')))
        clef_sig = get_clef_signature(part_data.get('clef', score_data.get('clef')))
        tempo_sig = get_tempo_signature(part_data.get('tempo', score_data.get('tempo')))

        part.insert(0, key_sig)
        part.insert(0, time_sig)
        part.insert(0, clef_sig)
        part.insert(0, tempo_sig)


        accumulated_duration = 0
        bar_duration = time_sig.barDuration.quarterLength
        bar = stream.Measure()

        dynamic_marking = dynamics.Dynamic('mf')
        volume = dynamic_to_midi_velocity('mf')
        bar.insert(0, dynamic_marking)
        current_beat_no = 0
        beat_used_incorrect_count = 0
        long_note_count = 0
        for i, (n, beat_no) in enumerate(zip(melody_notes, melody_rhythms)):
            if not isinstance(beat_no, (float, int, Fraction)):
                print("Beat_ends need to be integers or float. Next, time create a finished part for the musical ideas discussed by ChatGPT.")
                continue
            if beat_no > current_beat_no:
                r = beat_no - current_beat_no
                if r > 8:
                    long_note_count += 1
                    if long_note_count < 5:
                            print("Warning: " + part_id + " note with beat_end " + str(beat_no) + " is " + str(r) + " beats long. If the note was meant to be shorter add a placeholder rest note before it, for the excess duration.")
                    elif long_note_count == 5:
                        print(
                            "Warning: Ignore if there are lots of long notes in this piece - Note duration is beat_end[n] -( if beat_end[n-1] is None else beat_end[n-1].")
            elif beat_no == current_beat_no:
                print("Error!!! You can't have two or more notes with the same beat_end value on the same part!"
                      " Fix and try again.")
                continue
            elif beat_no < current_beat_no:
                if beat_used_incorrect_count > 8:
                    print("Warning: Beat_end should represent the ending beat no from the start of the piece of the corresponding note")
                beat_used_incorrect_count += 1
                r = beat_no


            current_beat_no = beat_no

            if i < len(section_dynamics):
                dynamic_str = section_dynamics[i]
                if dynamic_str == '':
                    dynamic_str = 'mf'
                dynamic_marking = dynamics.Dynamic(dynamic_str)
                volume = dynamic_to_midi_velocity(dynamic_str)
            # Determine if it's a note, chord, or rest
            if isinstance(n, GeneralNote):
                element = n
                if i < len(section_lyrics):
                    element.addLyric(section_lyrics[i])

                element.volume.velocity = volume
            elif isinstance(n, list) and len(n) > 0:
                first_note = n[0]
                invalid_chord = False
                if n == ['rest']:
                    element = note.Rest(quarterLength=r)
                    invalid_chord = True

                if len(n) > 4:
                    print("Warning: Array " + str(n) + "is getting treated as a chord. If its meant to be "
                                                       "separate notes, remove the notes from the array.")
                for index, chord_note in enumerate(n):
                    n[index] = str(chord_note).replace('S', '#')
                    chord_note = n[index]
                    if not invalid_chord and not is_valid_note(chord_note):
                        print("Warning: Please fix chord" + str(n) + get_chord_string())
                        invalid_chord = True
                        if len(first_note) > 0:
                            element = check_and_create_note(first_note[0], quarterLength=r, volume=volume)
                        else:
                            element = note.Rest(quarterLength=r)

                if not invalid_chord:
                    element = check_and_create_chord(n, quarterLength=r, volume=volume)
                if i < len(section_lyrics):
                    element.addLyric(section_lyrics[i])

            elif isinstance(n, str) and n != '' and n != 'rest' and n != 'Rest' and n != 'rests' and n != 'z' and n != 'r' and n != 'R':
                n = str(n).replace('S', '#')
                if not is_valid_note(n) or ' ' in n:

                    chord_notes = n.split()
                    element = check_and_create_chord(chord_notes, quarterLength=r, volume=volume)
                    if element.isRest:
                        n = n[0]
                        element = check_and_create_note(n, quarterLength=r, volume=volume)
                else:
                    element = check_and_create_note(n, quarterLength=r, volume=volume)

                if i < len(section_lyrics):
                    element.addLyric(section_lyrics[i])

            else:
                element = note.Rest(quarterLength=r)
                if i < len(section_lyrics):
                    element.addLyric(section_lyrics[i])

            # Check if the element fits in the current bar

            if accumulated_duration + r > bar_duration:
                remaining_duration = bar_duration - accumulated_duration
                next_duration = r - remaining_duration
                remaining_duration_long_note = r - (remaining_duration + bar_duration)
                if remaining_duration_long_note > 0:
                    next_duration = bar_duration

                first_part, second_part = split_note_or_chord(element, remaining_duration, next_duration)
                if first_part.duration.quarterLength > 0:
                    first_part.expressions = element.expressions
                    if i < len(section_lyrics):
                        first_part.addLyric(section_lyrics[i])
                    bar.append(first_part)
                else:
                    if i < len(section_lyrics):
                        second_part.addLyric(section_lyrics[i])

                part.append(bar)
                bar = stream.Measure()
                bar.insert(0, dynamic_marking)
                if second_part.duration.quarterLength > 0:
                    second_part.expressions = element.expressions
                    if remaining_duration_long_note > 0:
                        second_part.tie = tie.Tie('continue')
                    bar.append(second_part)
                accumulated_duration = next_duration % bar_duration
                if accumulated_duration == 0:
                    part.append(bar)
                    bar = stream.Measure()
                    bar.insert(0, dynamic_marking)
                r -= remaining_duration + next_duration
                while remaining_duration_long_note > 0:
                    if accumulated_duration + r > bar_duration:
                        remaining_duration = bar_duration - accumulated_duration
                        next_duration = r - remaining_duration
                        remaining_duration_long_note = r - (remaining_duration + bar_duration)
                        if remaining_duration_long_note > 0:
                            next_duration = bar_duration
                        first_part, second_part = split_note_or_chord(element, remaining_duration, next_duration)
                        first_part.tie = tie.Tie('continue')
                        if first_part.duration.quarterLength > 0:
                            first_part.expressions = element.expressions
                            bar.append(first_part)

                        part.append(bar)
                        bar = stream.Measure()
                        bar.insert(0, dynamic_marking)
                        if second_part.duration.quarterLength > 0:
                            second_part.expressions = element.expressions
                            if remaining_duration_long_note > 0:
                                second_part.tie = tie.Tie('continue')
                            bar.append(second_part)
                        r -= (remaining_duration + max(next_duration,0))
                        part.append(bar)
                        bar = stream.Measure()
                        bar.insert(0, dynamic_marking)
                    else:
                        first_part, _ = split_note_or_chord(element, remaining_duration_long_note, 0)
                        bar.append(first_part)
                        accumulated_duration += r
                        remaining_duration_long_note = 0
                        if accumulated_duration == bar_duration:
                            accumulated_duration = 0
                            part.append(bar)
                            bar = stream.Measure()
                            bar.insert(0, dynamic_marking)
            else:
                bar.append(element)
                accumulated_duration += r
                if accumulated_duration == bar_duration:
                    accumulated_duration = 0
                    part.append(bar)
                    bar = stream.Measure()
                    bar.insert(0, dynamic_marking)
        if accumulated_duration > 0:
            pad_bar_with_rests(bar, time_sig)
            part.append(bar)  # Append the last bar

    # Write the score to MusicXML and MIDI files
    score.write('musicxml', fp=musicxml_path)
    score.write('midi', fp=midi_path)

    print("Fix warning or error messages printed above next time. If Any.")
    print("Ask user for feedback or to continue on with the next section (if applicable).")
    print("Midi/MusicXML saved to mount - sandbox:" + midi_path + " and sandbox:" + musicxml_path + " - provide user links to download it.")
    #
    try:
        if show_html:
            score.show('osmd')
    except:
        pass

    return score


def pad_bar_with_rests(bar, time_signature=meter.TimeSignature('4/4')):
    """
    Checks if the bar is full based on the provided time signature. If the bar is not full,
    pads it with a rest for the remaining duration.

    Args:
    - bar (music21.stream.Measure): The bar to check and pad.
    - time_signature (music21.meter.TimeSignature): The time signature to determine the full duration of the bar.

    Returns:
    - music21.stream.Measure: The possibly modified bar, padded with a rest if it was not full.
    """
    # Calculate the total duration of notes and rests in the bar
    total_duration = sum(element.duration.quarterLength for element in bar.notesAndRests)

    # Determine the expected full duration of a bar based on the time signature
    full_duration = time_signature.barDuration.quarterLength

    # Check if the bar is full
    if total_duration < full_duration:
        # Calculate the remaining duration that needs to be filled with a rest
        remaining_duration = full_duration - total_duration
        # Create a rest for the remaining duration and add it to the bar
        rest = note.Rest(quarterLength=remaining_duration)
        bar.append(rest)

    return bar


def is_valid_note(chord_note):
    return len(chord_note) == 1 or (len(chord_note) > 1 and (chord_note[-1].isdigit() or chord_note[-1] in ['#', '-']))


def get_instrument_class_by_name(instrument_name):
    """
    Returns an instance of the music21 instrument class based on the given instrument name string.
    If the instrument is not found, returns None.
    """
    # Normalize the instrument name to match class naming conventions in music21
    # This might include capitalizing the first letter and removing spaces for compound names
    # For example, "French Horn" should be converted to "FrenchHorn"
    class_name = lowercase_after_parenthesis(instrument_name).replace(' ', '').replace('(','').replace(')','').replace('+', '')


    if class_name == "Cello":
        class_name = "Violoncello"

    if class_name == "ElectricGuitar(distortion)":
        class_name = "ElectricGuitarlead"

    if class_name == "ElectricGuitar(clean)":
        class_name = "ElectricGuitarclean"

    if class_name == "FrenchHorn":
        class_name = "Horn"

    if class_name == "StringEnsemble":
        class_name = "StringInstrument"

    if class_name == "StringSection":
        class_name = "StringInstrument"

    if class_name == "Strings":
        class_name = "StringInstrument"

    if class_name == "Keyboard":
        class_name = "Piano"

    if class_name == "Synthesizer":
        class_name = "Sampler"

    if class_name == "SynthLead":
        class_name = "Sampler"

    if class_name == "SynthPad":
        class_name = "Sampler"

    if class_name == "DrumSet":
        class_name = "SnareDrum"

    if class_name == "Drumset":
        class_name = "SnareDrum"

    if class_name == "DrumKit":
        class_name = "SnareDrum"

    if class_name == "Drumkit":
        class_name = "SnareDrum"

    if class_name == "StandardDrumKit":
        class_name = "SnareDrum"

    if class_name == "Voice":
        # print("Voice is not supported! Piano will simulate voice section, you will need to add your own voice in")
        class_name = "Vocalist"

    # if class_name == "Vocalist":
    #     print("Voice is not supported! Piano will simulate Vocalist section, you will need to add your own voice in")
    #     class_name = "Piano"
    #
    # if class_name == "VocalistOverride":
    #     class_name = "Vocalist"

    # Attempt to get the class from the instrument module
    try:
        instrument_class = getattr(instrument, class_name)
        return instrument_class()  # Instantiate the class
    except AttributeError:
        print(
            "Warning: Instrument " + instrument_name + " not found, replacing with piano. Maybe the name has another variation or instrument is not supported.")
        return instrument.ElectricPiano()

def lowercase_after_parenthesis(text):
    # This function finds a '(' followed by any characters that are not ')' and applies lowercase to the next word
    return re.sub(r'\(([A-Za-z]+)', lambda x: '(' + x.group(1).lower(), text)
def get_chord_string():
    return ". chords must be entered as an array of notes e.g. ['C4','E#4','G4']. Fix this next time for the invalid chord."


def check_and_create_note(note_str, quarterLength=1.0, volume=None):
    try:
        if not quarterLength:
            quarterLength = 1.0
        # Attempt to create a Note object with the given string
        element = note.Note(note_str, quarterLength=quarterLength)
        if volume:
            element.volume.velocity = volume
        return element
    except (pitch.AccidentalException, pitch.PitchException):
        print("Error: Please fix note or chord " + note_str + get_chord_string())
        return note.Rest(quarterLength=quarterLength)


def check_and_create_chord(chord_array, quarterLength=1.0, volume=None):
    try:
        if not quarterLength:
            quarterLength = 1.0
        # Attempt to create a chord object with the given string
        element = chord.Chord(chord_array, quarterLength=quarterLength)
        if volume:
            element.volume.velocity = volume
        return element
    except (pitch.AccidentalException, pitch.PitchException):
        print("Error: Please fix note or chord " + str(chord_array) + get_chord_string())
        return note.Rest(quarterLength=quarterLength)


def split_note_or_chord(element, remaining_duration, next_duration):
    if element.isNote:
        # Splitting a note
        first_part = note.Note(element.pitch,
                               duration=duration.Duration(remaining_duration))
        second_part = note.Note(element.pitch,
                                duration=duration.Duration(next_duration))

        if remaining_duration > 0 and next_duration > 0:
            first_part.tie = tie.Tie('start')
            second_part.tie = tie.Tie('stop')
    elif element.isChord:
        # Splitting a chord
        first_part = chord.Chord(element.pitches,
                                 duration=duration.Duration(remaining_duration))
        second_part = chord.Chord(element.pitches,
                                  duration=duration.Duration(next_duration))

        if remaining_duration > 0 and next_duration > 0:
            for note_in_chord in first_part.notes:
                note_in_chord.tie = tie.Tie('start')
            for note_in_chord in second_part.notes:
                note_in_chord.tie = tie.Tie('stop')
    elif element.isRest:
        first_part = note.Rest(duration=duration.Duration(remaining_duration))
        second_part = note.Rest(duration=duration.Duration(next_duration))
        if remaining_duration > 0 and next_duration > 0:
            first_part.tie = tie.Tie('start')
            second_part.tie = tie.Tie('stop')
    else:
        raise ValueError("Element must be a Note or Chord")

    return first_part, second_part


def generate_random_notes(key_signature, length):
    scale = key_signature.getScale()
    return [scale.pitchFromDegree(random.randint(1, 7)) for _ in range(length)]


def get_section_data(part_data, key, default):
    data = part_data.get(key, {} if part_data.get(key) is not None else None)
    if data is None:
        return default
    return data


def generate_random_rhythms(length):
    rhythm_choices = [0.25, 0.5, 1, 2]  # Quarter, Eighth, Whole, Half notes
    return [random.choice(rhythm_choices) for _ in range(length)]


def dynamic_to_midi_velocity(dynamic_marking):
    # This dictionary maps dynamic markings to MIDI velocities
    dynamic_mapping = {
        'ppp': 20,
        'pp': 31,
        'p': 42,
        'mp': 53,
        'mf': 64,
        'f': 80,
        'ff': 96,
        'fff': 112
    }
    return dynamic_mapping.get(dynamic_marking, 64)  # Default to 'mf' if not found


def get_key_signature(key_data):
    try:
        if isinstance(key_data, key.Key):
            return key_data
        elif isinstance(key_data, str):
            return key.Key(key_data)
        else:
            return key.Key('C')
    except:
        return key.Key('C')


def get_time_signature(time_data):
    try:
        if isinstance(time_data, meter.TimeSignature):
            return time_data
        elif isinstance(time_data, str):
            return meter.TimeSignature(time_data)
        else:
            return meter.TimeSignature('4/4')
    except:
        return meter.TimeSignature('4/4')


def get_clef_signature(clef_data):
    try:
        if isinstance(clef_data, clef.Clef):
            return clef_data
        elif isinstance(clef_data, str):
            return clef.__dict__[clef_data]()  # Assuming clef_data is the class name as string
        else:
            return clef.TrebleClef()
    except:
        return clef.TrebleClef()


def get_tempo_signature(tempo_data):
    try:
        if isinstance(tempo_data, tempo.MetronomeMark):
            return tempo_data
        elif isinstance(tempo_data, (int, float)):  # Assuming tempo can be specified as BPM
            return tempo.MetronomeMark(number=tempo_data)
        else:
            return tempo.MetronomeMark(number=120)
    except:
        return tempo.MetronomeMark(number=120)


#
# #
#
# initial_melodies = ['D4', 'Rest', 'B3', 'B3', 'A3', 'Rest', 'G3', 'G3', 'D4', 'B3']
# initial_beat_ends = [0.5 * (i + 1) for i in range(len(initial_melodies))]
#
# # For the continuation, we'll mimic the pattern and create a continuation that feels natural for another 32 beats.
# # Extending the melody based on the initial pattern and creating a simple, repetitive structure that could follow.
# continuation_melodies = [
#     'G3', 'A3', 'B3', 'C4', 'D4', 'E4', 'F#4', 'G4',  # Ascending scale pattern for the next 8 notes.
#     'G4', 'F#4', 'E4', 'D4', 'C4', 'B3', 'A3', 'G3',  # Descending scale pattern for the following 8 notes.
#     'A3', 'B3', 'C4', 'D4', 'E4', 'F#4', 'G4', 'A4',  # Ascending scale pattern, reaching higher note.
#     'A4', 'G4', 'F#4', 'E4', 'D4', 'C4', 'B3', 'A3',  # Descending back to the starting note.
# ]
#
# # Combining the initial and continuation melodies.
# full_melodies = initial_melodies + continuation_melodies
# full_beat_ends = [0.5 * (i + 1) for i in range(len(full_melodies))]
#
# # Constructing the score and parts data.
# score_data = {
#     'key': 'C',  # Assuming key of C for simplicity.
#     'time_signature': '4/4',  # Common time.
#     'tempo': 120,  # Assuming a moderate tempo.
#     'clef': 'treble',  # Using treble clef.
# }
#
# parts_data = {
#     'Piano': {
#         'instrument': 'VocalistOverride',
#         'melodies': full_melodies,
#         'beat_ends': full_beat_ends,
#         'dynamics': [],  # Not specifying dynamics for simplicity.
#         'lyrics': [],  # No lyrics for instrumental.
#     }
# }
#
# # # Paths for output files
# musicxml_path = '../serene_landscape_duet_musicxml.xml'
# midi_path = '../serene_landscape_duet_midi.mid'
#
# # Generate and save the music files
# score = process_and_output_score(parts_data, score_data, musicxml_path, midi_path)

# score.show('osmd')
#
# print("pass")
