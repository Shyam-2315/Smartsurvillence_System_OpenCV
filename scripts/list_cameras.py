"""Non-destructive Windows USB-camera discovery for VAYU-X configuration."""
from __future__ import annotations

import argparse

import cv2


def main() -> int:
    parser = argparse.ArgumentParser(description="List OpenCV-readable camera indexes without changing VAYU-X.")
    parser.add_argument("--max-index", type=int, default=8, help="highest index to probe (default: 8)")
    args = parser.parse_args()
    backend = cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else cv2.CAP_ANY
    found = []
    for index in range(max(0, args.max_index) + 1):
        capture = cv2.VideoCapture(index, backend)
        try:
            if not capture.isOpened():
                continue
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            height, width = frame.shape[:2]
            fps = capture.get(cv2.CAP_PROP_FPS)
            found.append(index)
            print(f"{index}: readable, {width}x{height}, reported FPS {fps:.2f}")
        finally:
            capture.release()
    if not found:
        print("No readable cameras found. Check receiver power, USB cable, Windows Camera privacy access, and drivers.")
        return 1
    print("Set CAMERA_SOURCE to one listed index and CAMERA_ID=AIR-01, CAMERA_MODE=airborne for the airborne receiver.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
