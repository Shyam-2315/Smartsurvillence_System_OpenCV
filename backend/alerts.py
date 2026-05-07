import datetime
import sqlite3

def log_alert(track_id, duration):
    with open("alerts.log", "a") as f:
        f.write(f"{datetime.datetime.now()} - ALERT: ID {track_id}, Duration {duration}\n")


def save_alert_db(track_id, message, db_path="alerts.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            track_id INTEGER NOT NULL,
            message TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        "INSERT INTO alerts (created_at, track_id, message) VALUES (?, ?, ?)",
        (datetime.datetime.now().isoformat(), int(track_id), message),
    )
    conn.commit()
    conn.close()