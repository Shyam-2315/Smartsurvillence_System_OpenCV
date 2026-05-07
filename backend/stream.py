import cv2
import time
import worker

def generate_frames():

    while True:

        try:

            frame_to_stream = worker.processed_frame

            if frame_to_stream is None:
                time.sleep(0.01)
                continue

            success, buffer = cv2.imencode(".jpg", frame_to_stream)

            if not success:
                continue

            frame = buffer.tobytes()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                frame +
                b"\r\n"
            )

        except Exception as e:
            print("❌ Stream Error:", e)

            time.sleep(0.1)