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

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
DB_NAME = "wta_bot.db"

PREMATCH_CACHE = {}
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot WTA Activo y Escaneando", 200

def send_telegram_alert(tournament, p1, p2, fav_name, pre_odds, live_odds, prob):
    """Envía la alerta estructurada a Telegram usando el método v10 oficial."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendRichMessage"
        
        html_content = (
            f"<b>🚨 ALERTA DE VALOR WTA (TEST CORREGIDO) 🚨</b><br><br>"
            f"🏆 <b>Torneo:</b> {tournament.replace('_', ' ').upper()}<br>"
            f"🎾 <b>Partido:</b> {p1} vs {p2}\n\n"
            f"⭐ <b>Favorita en Apuros:</b> {fav_name}<br><br>"
            f"📊 <b>Comparativa de Cuotas:</b><br>"
            f"• Cuota Pre-Partido: {pre_odds}<br>"
            f"• Cuota en Vivo Actual: {live_odds}<br><br>"
            f"🎯 <b>Probabilidad de Remontada:</b> {prob}%"
        )
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "rich_message": {
                "html": html_content
            }
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            logging.info(f"Envío de prueba completado. Código de respuesta: {r.status_code}")
        except Exception as e:
            logging.error(f"Error al conectar con Telegram: {e}")

def run_auto_start_test():
    # EJECUCIÓN INMEDIATA FORZADA: Envía la alerta de prueba apenas se enciende el servidor
    time.sleep(2)
    logging.info("⚡ Disparando alerta de prueba definitiva hacia Telegram...")
    send_telegram_alert("WTA 1000 Madrid Open", "Paula Badosa", "Coco Gauff", "Paula Badosa", 1.45, 2.62, 78.4)

if __name__ == "__main__":
    # Arranca el hilo de la prueba automatizada al encender
    threading.Thread(target=run_auto_start_test, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


