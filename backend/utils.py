import cv2
import os
import time

OUTPUT_DIR = "../outputs"

def save_screenshot(frame, track_id):
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    timestamp = int(time.time())
    filename = f"{OUTPUT_DIR}/alert_{track_id}_{timestamp}.jpg"

    cv2.imwrite(filename, frame)
    # Return both relative filename and full path consumers can use.
    return filename