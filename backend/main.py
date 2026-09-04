"""Legacy compatibility notice.

The supported application entry point is `uvicorn api:app --host 127.0.0.1 --port 8001`.
This module deliberately contains no second OpenCV pipeline.
"""
if __name__ == "__main__":
    raise SystemExit("Use: uvicorn api:app --host 127.0.0.1 --port 8001")
