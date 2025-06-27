import cv2
import numpy as np

from .config import *


def double_white_pixel_groups(im_inv, min_width=5, min_height=1, max_height=10):
    rows, cols = im_inv.shape
    output_image = np.copy(im_inv)

    # Precompute rows that need processing based on white pixel ratio
    row_white_ratios = np.mean(im_inv == 0, axis=1)
    rows_to_process = np.where((row_white_ratios > 0.5) & (row_white_ratios < 0.99))[0]

    # Process only rows that meet the white pixel ratio criteria
    for y in rows_to_process:
        x = 0
        while x < cols:
            if im_inv[y, x] == 0:  # White pixel found
                # Find the width of the white segment
                width = 1
                while x + width < cols and im_inv[y, x + width] == 0:
                    width += 1

                # Check vertical continuity only if the width meets the minimum requirement
                if width >= min_width:
                    # Simplify the vertical check by using any() to find the first non-zero pixel
                    for height in range(1, max_height + 1):
                        if y + height >= rows or np.any(im_inv[y:y + height, x:x + width] != 0):
                            break

                    # Adjust height to be within limits
                    height = max(min_height, min(height, max_height))

                    # Triple the height of the segment within image bounds
                    new_start_y = max(0, y - height)
                    new_end_y = min(rows, y + 2 * height)
                    output_image[new_start_y:new_end_y, x:x + width] = 0

                x += width  # Skip ahead by the width of the processed segment
            else:
                x += 1

    return output_image


def detect_blobs(input_image, staffs):
    """
    Detects blobs with given parameters.

    https://www.learnopencv.com/blob-detection-using-opencv-python-c/
    """
    if VERBOSE:
        print("Detecting blobs.")
    im_with_blobs = input_image.copy()
    im_inv = 255 - im_with_blobs
    threshold_value = 30
    im_inv[im_inv < threshold_value] = 0
    # Dynamic kernel sizing with minimum size consideration
    height = int(im_inv.shape[0] / 500)
    width = int(im_inv.shape[1] / 350)
    if im_inv.shape[1] < 800:
        im_inv = double_white_pixel_groups(im_inv, width*5, 1, 3)
        min_kernel_height = 4
    else:
        min_kernel_height = max(2, height)  # Minimum kernel height for horizontal lines
    kernel_h = cv2.getStructuringElement(ksize=(1, min_kernel_height), shape=cv2.MORPH_RECT)
    horizontal_lines = cv2.morphologyEx(im_inv, cv2.MORPH_OPEN, kernel_h, iterations=2)  # Apply operation iteratively
    horizontal_lines = 255 - horizontal_lines

    min_kernel_width = max(1, width)  # Minimum kernel width for vertical lines
    kernel_v = cv2.getStructuringElement(ksize=(min_kernel_width, 1), shape=cv2.MORPH_RECT)
    vertical_lines = cv2.morphologyEx(255 - horizontal_lines, cv2.MORPH_OPEN, kernel_v, iterations=2)
    vertical_lines = 255 - vertical_lines

    if SAVING_IMAGES_STEPS:
        cv2.imwrite("../8a_lines_horizontal_removed.png", horizontal_lines)
        cv2.imwrite("../8a_lines_vertical_removed.png", vertical_lines)

    im_with_blobs = vertical_lines
    im_with_blobs = cv2.cvtColor(im_with_blobs, cv2.COLOR_GRAY2BGR)

    # Set up the SimpleBlobDetector with default parameters.
    params = cv2.SimpleBlobDetector_Params()
    params.filterByArea = True
    params.minArea = 50  # Reduced from 225
    params.maxArea = 800  # Reduced from 1500 if needed, depending on the image
    params.filterByCircularity = True
    params.minCircularity = 0.6  # Reduced from 0.6
    params.filterByConvexity = True
    params.minConvexity = 0.9  # Reduced from 0.9
    params.filterByInertia = True
    params.minInertiaRatio = 0.01  # Keep this low as it helps to detect elongated blobs

    detector = cv2.SimpleBlobDetector_create(params)
    keypoints = detector.detect(im_with_blobs)

    cv2.drawKeypoints(im_with_blobs, keypoints=keypoints, outImage=im_with_blobs, color=(0, 0, 255),
                      flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)

    if SAVING_IMAGES_STEPS:
        cv2.imwrite("../8b_with_blobs.jpg", im_with_blobs)

    '''
    Here we enumerate notes.
    '''
    staff_diff = 3 / 5 * (staffs[0].max_range - staffs[0].min_range)
    bins = [x for sublist in [[staff.min_range - staff_diff, staff.max_range + staff_diff] for staff in staffs] for x in
            sublist]

    keypoints_staff = np.digitize([key.pt[1] for key in keypoints], bins)
    sorted_notes = sorted(list(zip(keypoints, keypoints_staff)), key=lambda tup: (tup[1], tup[0].pt[0]))

    im_with_numbers = im_with_blobs.copy()

    for idx, tup in enumerate(sorted_notes):
        cv2.putText(im_with_numbers, str(idx), (int(tup[0].pt[0]), int(tup[0].pt[1])),
                    fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                    fontScale=1, color=(255, 0, 0))
        cv2.putText(im_with_blobs, str(tup[1]), (int(tup[0].pt[0]), int(tup[0].pt[1])),
                    fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                    fontScale=1, color=(255, 0, 0))
    if SAVING_IMAGES_STEPS:
        cv2.imwrite("../8c_with_numbers.jpg", im_with_numbers)
        cv2.imwrite("../8d_with_staff_numbers.jpg", im_with_blobs)

    if VERBOSE:
        print("Keypoints length : " + str(len(keypoints)))

    return sorted_notes
