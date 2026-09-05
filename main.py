import os
import sqlite3
import logging
import requests
import threading
import time
from datetime import datetime, timedelta
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

# --- CONFIGURACIÓN DE LOGS Y DISPOSITIVO ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DB_NAME = "wta_bot.db"

PREMATCH_CACHE = {}

# --- SERVIDOR WEB FLASK (EXIGIDO POR RENDER) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot WTA Activo y Monitoreando", 200

def send_telegram_alert(tournament, p1, p2, fav_name, pre_odds, live_odds, prob):
    """Envía la alerta detallada a Telegram cuando se detecta valor en vivo."""
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
                logging.info(f"✅ Alerta enviada a Telegram para: {p1} vs {p2}")
            else:
                logging.error(f"❌ Error de Telegram (Status {r.status_code}): {r.text}")
        except Exception as e:
            logging.error(f"❌ Error al enviar alerta a Telegram: {e}")

def calculate_comeback_probability(pre_odds_fav, live_odds_fav):
    if not pre_odds_fav or pre_odds_fav <= 1.0:
        return 50.0
    base_prob = (1.0 / pre_odds_fav) * 100
    strength_bonus = 10.0 if pre_odds_fav <= 1.30 else (5.0 if pre_odds_fav <= 1.60 else 0.0)
    live_drop_factor = (pre_odds_fav / live_odds_fav) * 10
    estimated_prob = base_prob + strength_bonus - (10 - live_drop_factor)
    return round(max(10.0, min(90.0, estimated_prob)), 1)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wta_matches (
            match_id TEXT PRIMARY KEY,
            tournament TEXT,
            player_1 TEXT,
            player_2 TEXT,
            p1_pre_odds REAL,
            p2_pre_odds REAL,
            fav_name TEXT,
            fav_pre_odds REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_active_wta_tournaments():
    url = f"https://the-odds-api.com{ODDS_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            sports = r.json()
            return [s['key'] for s in sports if 'tennis_wta' in s['key']]
        return []
    except Exception as e:
        logging.error(f"Error al consultar torneos: {e}")
        return []

def fetch_single_match_odds(sport_key, match_id, p1, p2):
    url = f"https://the-odds-api.com{sport_key}/odds/"
    params = {'apiKey': ODDS_API_KEY, 'regions': 'eu', 'markets': 'h2h'}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            matches = r.json()
            for m in matches:
                if m.get('id') == match_id:
                    bookmakers = m.get('bookmakers', [])
                    p1_odds, p2_odds = None, None
                    if bookmakers and len(bookmakers) > 0:
                        markets = bookmakers[0].get('markets', [])
                        if markets and len(markets) > 0:
                            outcomes = markets[0].get('outcomes', [])
                            for o in outcomes:
                                if o.get('name') == p1: p1_odds = o.get('price')
                                elif o.get('name') == p2: p2_odds = o.get('price')
                    
                    if p1_odds and p2_odds:
                        fav_name = p1 if p1_odds < p2_odds else p2
                        fav_pre_odds = p1_odds if p1_odds < p2_odds else p2_odds
                        
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT OR REPLACE INTO wta_matches (match_id, tournament, player_1, player_2, p1_pre_odds, p2_pre_odds, fav_name, fav_pre_odds)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (match_id, sport_key, p1, p2, p1_odds, p2_odds, fav_name, fav_pre_odds))
                        conn.commit()
                        conn.close()
                        logging.info(f"💾 PRE-PARTIDO REGISTRADO: {p1} vs {p2}")
    except Exception as e:
        logging.error(f"Error en snapshot para {match_id}: {e}")

def schedule_wta_matches(scheduler):
    wta_tournaments = get_active_wta_tournaments()
    for sport_key in wta_tournaments:
        url = f"https://the-odds-api.com{sport_key}/odds/"
        params = {'apiKey': ODDS_API_KEY, 'regions': 'eu', 'markets': 'h2h'}
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                matches = r.json()
                now = datetime.utcnow()
                for match in matches:
                    match_id = match.get('id')
                    p1 = match.get('home_team')
                    p2 = match.get('away_team')
                    commence_str = match.get('commence_time')
                    
                    if commence_str and match_id not in PREMATCH_CACHE:
                        commence_dt = datetime.strptime(commence_str, "%Y-%m-%dT%H:%M:%SZ")
                        t5_dt = commence_dt - timedelta(minutes=5)
                        
                        if t5_dt > now:
                            scheduler.add_job(fetch_single_match_odds, 'date', run_date=t5_dt, args=[sport_key, match_id, p1, p2], id=f"t5_{match_id}", replace_existing=True)
                            PREMATCH_CACHE[match_id] = True
                        elif now <= commence_dt:
                            fetch_single_match_odds(sport_key, match_id, p1, p2)
                            PREMATCH_CACHE[match_id] = True
        except Exception as e:
            logging.error(f"Error al programar partidos: {e}")

def monitor_live_matches():
    logging.info("🔄 Verificando partidos EN VIVO...")
    wta_tournaments = get_active_wta_tournaments()
    for sport_key in wta_tournaments:
        url = f"https://the-odds-api.com{sport_key}/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                live_matches = r.json()
                for match in live_matches:
                    match_id = match.get('id')
                    
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("SELECT tournament, player_1, player_2, fav_name, fav_pre_odds FROM wta_matches WHERE match_id=?", (match_id,))
                    db_data = cursor.fetchone()
                    conn.close()
                    
                    if db_data:
                        tournament, p1, p2, fav_name, fav_pre_odds = db_data
                        bookmakers = match.get('bookmakers', [])
                        if bookmakers and len(bookmakers) > 0:
                            markets = bookmakers[0].get('markets', [])
                            if markets and len(markets) > 0:
                                outcomes = markets[0].get('outcomes', [])
                                live_odds_fav = None
                                for o in outcomes:
                                    if o.get('name') == fav_name: live_odds_fav = o.get('price')
                                
                                if live_odds_fav and fav_pre_odds:
                                    if live_odds_fav >= (fav_pre_odds * 1.4):
                                        prob = calculate_comeback_probability(fav_pre_odds, live_odds_fav)
                                        send_telegram_alert(tournament, p1, p2, fav_name, fav_pre_odds, live_odds_fav, prob)
                                        
                                        conn = sqlite3.connect(DB_NAME)
                                        cursor = conn.cursor()
                                        cursor.execute("DELETE FROM wta_matches WHERE match_id=?", (match_id,))
                                        conn.commit()
                                        conn.close()
        except Exception as e:
            logging.error(f"Error en escaneo en vivo: {e}")

def start_bot_logic():
    init_db()
    scheduler = BackgroundScheduler()
    scheduler.start()
    scheduler.add_job(schedule_wta_matches, 'interval', minutes=30, args=[scheduler])
    scheduler.add_job(monitor_live_matches, 'interval', minutes=2)
    logging.info("🚀 Bot WTA Completo Activo con Escáner Live (Cada 2 min).")
    schedule_wta_matches(scheduler)
    monitor_live_matches()

# --- HILO PRINCIPAL ---
if __name__ == "__main__":
    # Arrancar la lógica del bot en un hilo secundario
    threading.Thread(target=start_bot_logic, daemon=True).start()
    
    # Arrancar la app de Flask en el hilo principal usando las variables de Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


