from fractions import Fraction

from music21 import note, chord, meter, tempo, clef, percussion, key, stream
import json


from ai_song_maker import parts_data_view
# import view_parts_data

def convert_to_parts_data(score):
    """
    Converts a music21 stream.Score object into parts_data and score_data structures,
    assuming all parts have just one section and ignoring measures.
    """
    parts_data = {}
    song_structure = ["section_1"]  # Assuming all parts have just one section
    try:
        key_signature = score.analyze('key')
    except:
        key_signature = key.Key('C')

    time_signatures = score.recurse().getElementsByClass(meter.TimeSignature)
    time_signature = time_signatures[0] if time_signatures else meter.TimeSignature('4/4')
    bpm = score.metronomeMarkBoundaries()[0][2].number if score.metronomeMarkBoundaries() else 120
    max_beat_no = 1000
    for part in score.parts:
        part_name = part.partName or "Part"
        while part_name in parts_data:
            part_name = part_name + "X"
        # Attempt to extract the instrument from the part, default to Piano if not present
        part_instrument = part.getInstrument()
        instrument_name = part_instrument.instrumentName if part_instrument else "Piano"

        melodies = []
        rhythms = []
        lyrics = []
        dynamics = []
        current_beat_no = 0
        repeat_start_index = None
        in_repeat = False

        def process_notes_in_measure(measure):
            nonlocal current_beat_no

            def process_element(element):
                nonlocal current_beat_no
                if isinstance(element, stream.Voice):
                    # Process each element in the Voice object
                    for sub_element in element:
                        process_element(sub_element)
                else:
                    current_beat_no = round(current_beat_no + element.duration.quarterLength, 2)
                    rhythms.append(current_beat_no)
                    if not isinstance(element, note.Rest) and hasattr(element, 'volume') and element.volume:
                        dynamics.append(velocity_to_dynamic(element.volume.velocity))

                    if isinstance(element, note.Note):
                        melodies.append(element.nameWithOctave)

                    elif isinstance(element, chord.Chord):
                        melody_chord = [n.nameWithOctave for n in element.notes]
                        melodies.append(melody_chord)

                    elif isinstance(element, note.Rest):
                        melodies.append('rest')

                    else:
                        # If the element does not match any known types, append 'rest' as a placeholder
                        melodies.append('rest')

                    if hasattr(element, 'lyric'):
                        lyrics.append(element.lyric if element.lyric else '')

            if hasattr(measure, "notesAndRests"):
                elements = list(measure.notesAndRests)
                if len(elements) == 0:
                    # If no notes or rests, look for voices and process each voice
                    elements = list(measure.voices)
                for element in elements:
                    try:
                        process_element(element)
                    except:
                        # Append default values on error
                        melodies.append('')
                        rhythms.append(current_beat_no)
                        dynamics.append('mf')
        for measure in part.recurse().getElementsByClass('Measure'):
            process_notes_in_measure(measure)
            try:
                if measure.leftBarline is not None and hasattr(measure.leftBarline, 'direction') and measure.leftBarline.direction == 'start':
                    repeat_start_index = measure.number
                    in_repeat = True
                elif measure.rightBarline is not None and hasattr(measure.rightBarline, 'direction') and  measure.rightBarline.direction == 'end':
                    if in_repeat and repeat_start_index is not None:
                        # Process the repeat section again
                        for m in part.measures(repeat_start_index, measure.number):
                            process_notes_in_measure(m)
                        repeat_start_index = None
                        in_repeat = False
            except:
                repeat_start_index = None
                in_repeat = False

        max_beat_no = current_beat_no
        parts_data[part_name] = {
            'instrument': instrument_name,
            'melodies': melodies,
            'beat_ends': rhythms,
            'dynamics': dynamics
        }
        if any(lyrics):
            parts_data['lyrics'] = lyrics

    score_data = {
        'song_structure': song_structure,
        'key': key_signature,
        'time_signature': time_signature,
        'tempo': tempo.MetronomeMark(number=bpm),
        'clef': clef.TrebleClef(),  # Simplification for this example
    }
    string_to_print = "An error occurred calling view_parts_data. Please try call view_parts_data again or manually print all notes inside file to screen."
    try:
        string_to_print = 'Printing first 64 beats of parts_data: \n'
        string_to_print += '\ncall view_parts_data(parts_data, 64,' + str(max_beat_no) + ', [part_n, part_x]) to view rest.\n'
        string_to_print += parts_data_view.view_parts_data(parts_data, 0, 64)
        string_to_print += '\nEdit "beat_ends" or "melodies" by editing parts_data["part_n"]["beat_ends"][xxx:yyy] = [x,y,z, ...]  \n'


        string_to_print += '\nscore_data json output from score is: \n'
        string_to_print += "\nuse music21 python classes to change music21 objects in score_data e.g. key.Key('C', 'Major'), meter.TimeSignature('4/4'), tempo.MetronomeMark(number=120), clef.TrebleClef()\n"
        string_to_print += json.dumps(score_data, default=str)
    except:
        pass

    return parts_data, score_data, string_to_print


def custom_serializer(obj):
    if isinstance(obj, Fraction):
        # Convert Fraction to a string or a float, depending on your needs
        return float(obj)  # or float(obj) for a numerical representation
    return obj

def velocity_to_dynamic(velocity):
    if not velocity:
        return 'mf'
    # Original mapping from dynamic markings to MIDI velocities
    dynamic_mapping = {
        'pp': 31,
        'p': 42,
        'mp': 53,
        'mf': 64,
        'f': 80,
        'ff': 96,
    }

    # Invert the dictionary to create a reverse mapping
    reverse_mapping = {v: k for k, v in dynamic_mapping.items()}

    # Find the closest velocity in the reverse mapping
    closest_velocity = min(reverse_mapping.keys(), key=lambda x: abs(x - velocity))

    return reverse_mapping[closest_velocity]


def beat_to_length(beat_ends):
    durations = []
    previous = 0
    for beat in beat_ends:
        duration = beat - previous
        previous = beat
        if duration == 0.25:
            durations.append('/')
        elif duration == 0.5:
            durations.append('')
        elif duration == 0.75:
            durations.append('3/2')
        elif duration == 1.0:
            durations.append('2')
        else:
            # For durations that are not standard, we calculate the fraction
            denominator = round(1 / duration)
            durations.append(f"{denominator}")
    return durations

def abc_notation_for_piano(melodies, beat_ends):

    note_lengths = beat_to_length(beat_ends)
    abc_notes = []

    for i, note in enumerate(melodies):
        if note == "rest":
            abc_note = "z" + note_lengths[i]
        else:
            # Handle specific cases for example alterations
            if i == 1:  # Example for a sharp
                abc_note = "^" + note[0].lower() + note[1:] + note_lengths[i]
            elif i == 2:  # Example for a flat
                abc_note = "_" + note[0].lower() + note[1:] + note_lengths[i]
            elif i == 3:  # Example for a natural
                abc_note = "=" + note[0].lower() + note[1:] + note_lengths[i]
            else:
                abc_note = note[0].lower() + note[1:] + note_lengths[i]

        abc_notes.append(abc_note)

    # Assemble into ABC notation string
    abc_string = "| " + " ".join(abc_notes) + " |"
    return abc_string





# from music21 import converter
# score = converter.parse('../corpus/bach/bwv846.mxl') # ensure corpus has been unzipped first
# parts_data, score_data, string_to_print = convert_to_parts_data(score)
# print(string_to_print)
#
# # Generate ABC notation for piano
# for key, part in parts_data.items():
#
#     abc_piano_string = abc_notation_for_piano(part["melodies"], part["beat_ends"])
#     print(abc_piano_string)
