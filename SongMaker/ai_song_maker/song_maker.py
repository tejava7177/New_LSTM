from ai_song_maker import abc_helper, imageToNotes, reverse_score, score_helper, parts_data_view, abc_plan, \
    reverse_score_abc


def process_abc(abc_notation, part_instrument: dict, musicxml_path='/mnt/data/music_files/song_musicxml.xml',
                midi_path='/mnt/data/music_files/song_midi.mid', show_html=True, time_threshold = 3):
    return abc_helper.process_abc(abc_notation, part_instrument, musicxml_path, midi_path, show_html, time_threshold)

def analyze_measures(abc_string, expected_beats_per_measure = 4):
    return abc_helper.analyze_measures(abc_string, expected_beats_per_measure)

def parts_data_to_music(parts_data, score_data, musicxml_path='/mnt/data/song_musicxml.xml',
                        midi_path='/mnt/data/song_midi.mid', show_html=True,
                        sheet_music_html_path='/mnt/data/sheet_music.html'):
    return score_helper.process_and_output_score(parts_data, score_data, musicxml_path, midi_path,
                                            show_html, sheet_music_html_path)


def process_image(image_path, annotate_image_location=None):
    return imageToNotes.process_image(image_path, annotate_image_location)


def convert_to_parts_data(score):
    return reverse_score.convert_to_parts_data(score)

def score_to_abc(score):
    parts_data, score_data, _ = reverse_score.convert_to_parts_data(score)
    return reverse_score_abc.convert_parts_to_abc(parts_data, score_data)

def view_parts_data(parts_data, beats_from=0, beats_to=10000000, part_name_filter=None):
    return parts_data_view.view_parts_data(parts_data, beats_from, beats_to, part_name_filter)

def create_abc_plan(beats_per_measure, sections, song_structure):
    return abc_plan.create_plan(beats_per_measure, sections, song_structure)


def show_commands():
    print("""Available commands:
    def process_abc(abc_notation, part_instrument: dict, musicxml_path='/mnt/data/music_files/song_musicxml.xml',
                midi_path='/mnt/data/music_files/song_midi.mid', show_html=True, time_threshold = 3):
    Creates MIDI, MusicXML and HTML files for song. And returns parts_data for adding lyrics or dynamics via parts_data_to_music and to see exactly which notes are played at specfic times using view_parts_data

def analyze_measures(abc_string, expected_beats_per_measure = 4):
    Checks if abc notation is formatted correctly and returns corrections annotated on the abc notation

def parts_data_to_music(parts_data, score_data, musicxml_path='/mnt/data/song_musicxml.xml',
                        midi_path='/mnt/data/song_midi.mid', show_html=True,
                        sheet_music_html_path='/mnt/data/sheet_music.html'):
    Takes in parts_data eg {'Piano': {
         'instrument': 'Piano',
         'melodies': ['G3', ...],
         'beat_ends': [1, 1.5, 3, 7, 7.5, ..],
         'dynamics': ['mf', ...],
         'lyrics': ['', '', ...],
     }, 'Guitar': {...}, ...} and creates MIDI and MusicXML and HTML sheet music.


def process_image(image_path, annotate_image_location=None):
    takes image_path and returns parts_data for editing and recreating MIDI and MusicXML

def score_to_abc(score):
    Takes in music21 score and returns an abc_string for editing and recreating

def convert_to_parts_data(score):
    Takes in music21 score and returns parts_data for editing and recreating

def parts_data_annotated(parts_data, beats_from=0, beats_to=10000000, part_name_filter=None):
    To see a annotated parts_data (notes, beats, lyrics) between certain beats for editing""")


# from music21 import converter
# midi_file_path = '../wizards_anthem_midi.mid'
# score = converter.parse(midi_file_path)
#
# # Convert the parsed score to ABC notation
# abc_notes = score_to_abc(score)
# print(abc_notes)
