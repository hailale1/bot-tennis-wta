import os
import sqlite3
import logging
import requests
import threading
import time
from datetime import datetime, timedelta
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DB_NAME = "wta_bot.db"

PREMATCH_CACHE = {}
app = Flask(__name__)

def send_telegram_alert(tournament, p1, p2, fav_name, pre_odds, live_odds, prob):
    """Envía la alerta detallada a Telegram."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
        message = (
            f"🚨 **ALERTA DE VALOR WTA** 🚨\n\n"
            f"🏆 **Torneo:** {tournament.replace('_', ' ').upper()}\n"
            f"🎾 **Partido:** {p1} vs {p2}\n"
            f"⭐ **Favorita en Apuros:** {fav_name}\n\n"
            f"📊 **Comparativa de Cuotas:**\n"
            f"• Cuota Pre-Partido: `{pre_odds}`\n"
            f"• Cuota en Vivo Actual: `{live_odds}`\n\n"
            f"🎯 **Probabilidad de Remontada:** `{prob}%`"
        )
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            r = requests.post(url, data=payload, timeout=10)
            if r.status_code == 200:
                logging.info(f"✅ Alerta de prueba enviada a Telegram.")
            else:
                logging.error(f"❌ Error de Telegram (Status {r.status_code}): {r.text}")
        except Exception as e:
            logging.error(f"❌ Error al enviar alerta: {e}")

@app.route('/')
def home():
    return "Bot WTA Activo y Monitoreando", 200

# --- NUEVA RUTA DE PRUEBA MANUAL ---
@app.route('/test-alert')
def test_alert():
    """Ruta especial para obligar al bot a mandar un mensaje de prueba inmediato."""
    send_telegram_alert("WTA US Open (TEST)", "Iga Swiatek", "Aryna Sabalenka", "Iga Swiatek", 1.35, 2.40, 72.5)
    return "Alerta de prueba disparada. Revisa tu Telegram.", 200

def start_bot_logic():
    # Inicializa el flujo normal
    pass

if __name__ == "__main__":
    threading.Thread(target=start_bot_logic, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

