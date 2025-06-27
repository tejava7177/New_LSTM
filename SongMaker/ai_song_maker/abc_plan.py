def create_plan(beats_per_measure, sections, song_structure):
    output = []

    # A helper function to generate a repeating sequence of chords for given measures
    def get_chord_sequence(measures, chord_sequence):
        # Repeat the chord sequence enough times to cover all measures
        repeated_chords = (chord_sequence * ((measures // len(chord_sequence)) + 1))[:measures]
        return repeated_chords

    # Iterate through each instrument in the song structure dictionary
    i = 0
    for instrument, details in song_structure.items():
        i += 1
        instrument_output = []
        # Start defining the voice line for this instrument
        instrument_output.append(
            f"V:{i} clef=specify name=\"{instrument}\" snm=\"{i}\"")

        # Iterate through each section of the song structure for the current instrument
        cumulative_beats = 0
        for section, section_info in details['sections'].items():
            measures = sections[section]['measures']
            chord_sequence = sections[section]['harmonic_loop']
            chords_for_measures = get_chord_sequence(measures, chord_sequence)
            description = section_info.get('comment', '')
            average_note_length = section_info.get('average_note_length', '')

            # Create the bar string with chords for the current section
            bar_str = ' | '.join([f'"{chord}"{beats_per_measure}' for chord in chords_for_measures])
            beat_txt  = 'beat' if str(average_note_length) == '1' else "beats"
            cumulative_beats += measures * beats_per_measure
            bar_description = f" % [{cumulative_beats}] avg note len={average_note_length} {beat_txt}, {section} info: {description}"
            instrument_output.append(f"| {bar_str} |{bar_description}")

        # Join all parts for the current instrument into a single string
        output.append('\n'.join(instrument_output))

    # Join all instrument strings into the final output
    return "The comment structure contains expected note length and overall feel by section, and the chord played by the harmonic instrument each measure:  \n " + '\n'.join(output)

#
# # Example Usage
# song_structure = {
#     "Piano": {
#         "sections": {
#             "intro": {
#                 "average_note_length": "1-3",
#                 "description": "soft and slow"
#             },
#             "verse": {
#                 "average_note_length": "0.5-1",
#                 "description": "more dynamic"
#             }
#         }
#     },
#     "Bass": {
#         "sections": {
#             "intro": {
#                 "average_note_length": "1",
#                 "description": "steady bassline"
#             },
#             "verse": {
#                 "average_note_length": "0.5",
#                 "description": "groovy bassline"
#             }
#         }
#     }
# }
#
# sections = {
#     "intro": {
#         "measures": 6,
#         "harmonic_loop": ["Em", "Gm", "Am", "F"]
#     },
#     "verse": {
#         "measures": 4,
#         "harmonic_loop": ["C", "Am", "F", "G"]
#     }
# }
#
# beats_per_measure = 4
# print(create_plan(beats_per_measure, sections, song_structure))
