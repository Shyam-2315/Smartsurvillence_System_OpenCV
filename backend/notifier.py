import requests
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables (try backend/.env, then repo-root/.env, then default lookup)
load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.abspath(os.path.join(BASE_DIR, "..", ".env")))
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


# 📩 Send Text Alert
def send_telegram_alert(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram not configured: set BOT_TOKEN and CHAT_ID in .env")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, data=data)
        if response.ok:
            print("✅ Telegram message sent")
            return True
        print(f"⚠️ Telegram sendMessage failed: HTTP {response.status_code} - {response.text}")
        return False
    except Exception as e:
        print("Error sending message:", e)
        return False


# 📸 Send Image Alert
def send_telegram_image(image_path, caption="Alert Image"):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram not configured: set BOT_TOKEN and CHAT_ID in .env")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    try:
        with open(image_path, "rb") as img:
            files = {"photo": img}
            data = {
                "chat_id": CHAT_ID,
                "caption": caption
            }

            response = requests.post(url, files=files, data=data)
            if response.ok:
                print("✅ Telegram image sent")
                return True
            print(f"⚠️ Telegram sendPhoto failed: HTTP {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print("Error sending image:", e)
        return False