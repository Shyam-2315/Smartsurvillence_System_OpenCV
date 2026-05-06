import datetime

def log_alert(track_id, duration):
    with open("alerts.log", "a") as f:
        f.write(f"{datetime.datetime.now()} - ALERT: ID {track_id}, Duration {duration}\n")