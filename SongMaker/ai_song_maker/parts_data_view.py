

def current_note_playing(note_start, note_end, beat_from, beat_end ):
    if note_start < beat_end and note_end > beat_from:
        return True
    else:
        return False

def view_parts_data(parts_data, beats_from=0, beats_to=10000000, part_name_filter=None):
    output = []
    if beats_from == 0:
        beats_from = -1
    if isinstance(part_name_filter, str):
        part_name_filter = [item.strip() for item in part_name_filter.split(',')]

    for part_id, part_data in parts_data.items():
        if part_name_filter:
            if not any(filter_item in part_id for filter_item in part_name_filter):
                continue
        melodies = part_data.get('melodies', [])
        beat_ends = part_data.get('beat_ends', [])
        # Find the indices and values for notes within the specified range
        selected_indices = [i for i, beat_end in enumerate(beat_ends)
                            if ((i == 0 and current_note_playing(0, beat_end, beats_from, beats_to)) or
                                (i > 0 and current_note_playing(beat_ends[i-1] , beat_end, beats_from, beats_to)))]

        if not selected_indices:
            # Handle case where no notes are in the specified range for this part
            output.append(f'parts_data["{part_id}"] is not playing during beat range\n')
            continue

        # Extract the actual beat ends and melodies for the selected indices
        selected_beat_ends = [beat_ends[i] for i in selected_indices]
        selected_melodies = [melodies[i] for i in selected_indices]

        # Format the output strings
        beat_ends_str = ', '.join(map(str, selected_beat_ends))
        melodies_str = ', '.join([f'"{melody}"' if isinstance(melody, str) else str(melody)
                                  for melody in selected_melodies])
        output.append \
            (f'parts_data["{part_id}"]["beat_ends"][{selected_indices[0]}:{selected_indices[-1]}] = [{beat_ends_str}]')
        output.append \
            (f'parts_data["{part_id}"]["melodies"][{selected_indices[0]}:{selected_indices[-1]}] = [{melodies_str}]\n')
    return ("Here is the parts_data dictionary in text form. \n"
            "To add dynamics or lyrics add a dynamics or lyrics array of the same length as notes to parts_data "
            "e.g. parts_data['part_name_1']['lyrics'] = ['word for note 1', ....] or parts_data['part_name_1']['dynamics'] = ['mf', ....] add lyrics to one part only\n"
            " and call song_maker.parts_data_to_music(parts_data, score_data, 'mnt/data/fileNameLyricsMusicXML.xml', 'mnt/data/fileNameDynamics.mid').\n") + "\n".join(output)

#
# from abc_helper import process_abc
#
# abc_notation = """
# M:4/4
# L:1/4
# Q:1/4=100
# K:G
# V:1
# |z1/2 C1/3 [C1/8 c1/8] z1/8 C1/4 z1/8 C1/3 [G,1/4 C1/8] ^G,1/8 z1/8 ^G,1/4 ^G,1/4 z1/8 C1/2 [C1/3 c1/3] z1/8 C1/2 z1/8 C1/2 | ^C1/4 z1/8 ^D13/8 ^C1/8 z1/8 C1/3 z5/4 F1/3 | z1/4 ^D1/2 ^C1/8 C1/2 z1/4 ^A,1/3 z1/4 ^G,1/2 z1/8 G,1/3 z1/8 G,2/3 G,1/4 | z3/4 G,2/3 z3 | G,1/4 z1/4 ^A,2/3 z1/8 C1/8 z1/8 ^C1/2 z1/8 C1/3 z1/2 ^A,1/3 z1/4 ^G,1/4 z1/8 G,1/4 | G,1/3 z1/4 ^A,1/3 C C1/2 B,1/8 z1/8 B,1/4 z8/3 | G,1/3 z1/8 ^G,1/2 z1/3 C1/3 z1/3 ^D1/8 z1/8 F2/3 z1/8 E1/4 z1/8 F2 | z1/4 ^D3/4 [^D1/3 ^d1/4] z1/4 ^A,1/4 z1/8 C1/3 C1/8 z1/8 C1/4 C1/8 z1/8 C1/2 z13/8
# """
#
# # Instrument mapping
# ordered_part_instrument = {'V:1': 'Piano'}
#
# musicxml_path = '../serene_landscape_duet_musicxml.xml'
# midi_path = '../serene_landscape_duet_midi.mid'
# from abc_helper import process_abc
# parts_data, score_data = process_abc(abc_notation, ordered_part_instrument,musicxml_path,midi_path)
#
# # str = view_parts_data(parts_data,1,14, ['Soprano','Alto'])
# print(str)
#
# musicxml_path = '../serene_landscape_duet_musicxml.xml'
# midi_path = '../serene_landscape_duet_midi.mid'
#
# # Generate and save the music files
# import score_helper
# score = score_helper.process_and_output_score(parts_data, score_data, musicxml_path, midi_path)
