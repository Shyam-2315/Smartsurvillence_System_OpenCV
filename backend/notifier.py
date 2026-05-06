import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


# 📩 Send Text Alert
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, data=data)
        print("Message sent:", response.status_code)
    except Exception as e:
        print("Error sending message:", e)


# 📸 Send Image Alert
def send_telegram_image(image_path, caption="Alert Image"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    try:
        with open(image_path, "rb") as img:
            files = {"photo": img}
            data = {
                "chat_id": CHAT_ID,
                "caption": caption
            }

            response = requests.post(url, files=files, data=data)
            print("Image sent:", response.status_code)

    except Exception as e:
        print("Error sending image:", e)