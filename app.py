import os
import requests
import threading
import time
from flask import Flask

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

app = Flask(__name__)

def send_telegram_alert():
    """Función directa de prueba hacia Telegram."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
        message = (
            f"🚨 **ALERTA DE VALOR WTA (TEST)** 🚨\n\n"
            f"🏆 **Torneo:** WTA US OPEN (PRUEBA)\n"
            f"🎾 **Partido:** Iga Swiatek vs Aryna Sabalenka\n"
            f"⭐ **Favorita:** Iga Swiatek\n"
            f"🎯 **Probabilidad:** `72.5%`"
        )
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, data=payload, timeout=10)
        except Exception:
            pass

@app.route('/')
def home():
    return "Servidor WTA Activo", 200

@app.route('/test-alert')
def test_alert():
    send_telegram_alert()
    return "Alerta de prueba disparada. Revisa tu Telegram.", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
