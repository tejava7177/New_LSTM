from .notesRecognizer.blob_detector import detect_blobs
from .notesRecognizer.getting_lines import get_staffs
from .notesRecognizer.note import *
from .notesRecognizer.photo_adjuster import adjust_photo
from . import parts_data_view

import cv2
# try:
#     from notesRecognizer.blob_detector import detect_blobs
#     from notesRecognizer.getting_lines import get_staffs
#     from notesRecognizer.note import *
#     from notesRecognizer.photo_adjuster import adjust_photo
#     import view_parts_data
#
# except:
#     pass

##adapted from https://github.com/mpralat/notesRecognizer 03/24

def process_image(image_path, annotate_image_location = None):
    image = cv2.imread(image_path)
    adjusted_photo = adjust_photo(image)
    staffs = get_staffs(adjusted_photo)
    blobs = detect_blobs(adjusted_photo, staffs)
    notes = extract_notes(blobs, staffs, adjusted_photo)
    if annotate_image_location:
        draw_notes_pitch(adjusted_photo, notes, annotate_image_location)

    array_of_notes = []
    array_of_beat_ends = []
    i = 1
    previous_center = None  # To store the center of the previous note
    current_sub_array = []  # Temporary storage for a group of notes

    for note in notes:
        if previous_center is None:
            # This is the first note, so we just start a new sub-array with it
            current_sub_array.append(note.pitch)
        else:
            # Calculate the difference from the previous note's center
            difference = abs(note.center[0] - previous_center)
            if difference < 5:
                # The difference is small, add to the current sub-array
                current_sub_array.append(note.pitch)
            else:
                # The difference is 3 or more, time to start a new sub-array
                # But first, we need to add the current sub-array (or singular note) to the main array
                if len(current_sub_array) == 1:
                    # If it's a single note, append it directly
                    array_of_notes.append(current_sub_array[0])
                else:
                    # For multiple notes, append the sub-array itself
                    array_of_notes.append(current_sub_array)
                array_of_beat_ends.append(i)
                # Start a new sub-array with the current note
                current_sub_array = [note.pitch]

        # Update the previous center and the beat end index for the next iteration
        previous_center = note.center[0]
        i += 1

    # Don't forget to add the last sub-array or note to the main array after the loop
    if current_sub_array:  # Check if there's anything left to add
        if len(current_sub_array) == 1:
            array_of_notes.append(current_sub_array[0])
        else:
            array_of_notes.append(current_sub_array)
        array_of_beat_ends.append(i)

    parts_data = {  # key is 1st/2nd/3rd instrument.
        'Assuming_single_part': {  # Harmony instrument part
            'instrument': "Piano",  # Use instruments compatible with MIDI
            'beat_ends': array_of_beat_ends,
            # example for adding xxx section (e.g. verse 1 section) to instrument's part.
            'melodies': array_of_notes
        }
    }
    parts_data_string = "Printing first 64 beats of sheet music image using view_parts_data: \n"
    parts_data_string += parts_data_view.view_parts_data(parts_data, 0, 64)
    return parts_data, parts_data_string

# process_image('C:/Users/Sherwyn/Documents/2023/music21-m21_8/music21/v8/ai_song_maker/notesRecognizer/input/good/easy2.jpg', '../image.png')
