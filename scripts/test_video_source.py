"""Non-destructive OpenCV source probe for USB indexes or RTSP/IP URLs."""
from __future__ import annotations

import argparse
import time

import cv2


def parse_source(value: str) -> int | str:
    return int(value) if value.isdigit() else value


def main() -> int:
    parser = argparse.ArgumentParser(description="Open one video source and measure frame acquisition without YOLO.")
    parser.add_argument("source", help="USB index (for example 1) or RTSP/IP URL")
    parser.add_argument("--frames", type=int, default=60, help="maximum frames to sample (default: 60)")
    args = parser.parse_args()
    source = parse_source(args.source)
    backend = cv2.CAP_DSHOW if isinstance(source, int) and hasattr(cv2, "CAP_DSHOW") else cv2.CAP_ANY
    capture = cv2.VideoCapture(source, backend)
    try:
        if not capture.isOpened():
            print("Connection failed: OpenCV could not open the source.")
            return 2
        started, received, shape = time.monotonic(), 0, None
        for _ in range(max(1, args.frames)):
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            received += 1
            shape = frame.shape
        elapsed = time.monotonic() - started
        if not received or shape is None:
            print("Connection opened but no frame was acquired.")
            return 3
        height, width = shape[:2]
        print(f"Connected: {source}")
        print(f"Resolution: {width}x{height}")
        print(f"Acquired: {received} frames in {elapsed:.2f}s ({received / max(elapsed, .001):.2f} FPS)")
        print(f"Reported FPS: {capture.get(cv2.CAP_PROP_FPS):.2f}")
        return 0
    finally:
        capture.release()


if __name__ == "__main__":
    raise SystemExit(main())
