from notifier import send_telegram_alert, send_telegram_image

# Test text
send_telegram_alert("🚨 Test Alert from Smart Surveillance")

# Test image (use any image path)
send_telegram_image("test.jpg", "📸 Test Image")