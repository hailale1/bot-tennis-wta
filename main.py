import os
import sqlite3
import logging
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

# --- CONFIGURACIÓN DE VARIABLES DE ENTORNO ---
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

BASE_ODDS_URL = f"https://api.the-odds-api.com/v4/sports/tennis_wta_us_open/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
DB_NAME = "wta_bot.db"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
PREMATCH_CACHE = {}

def send_telegram_test():
    """Envía un mensaje de prueba a Telegram al iniciar el bot."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": "🚨 ¡PRUEBA DE BOT EXITOSA! El servidor Render está activo y conectado con tu Telegram."
        }
        try:
            r = requests.post(url, data=payload, timeout=10)
            if r.status_code == 200:
                logging.info("Mensaje de prueba enviado con éxito a Telegram.")
            else:
                logging.error(f"Error al enviar a Telegram: {r.text}")
        except Exception as e:
            logging.error(f"Fallo al conectar con Telegram: {e}")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wta_matches (
            match_id TEXT PRIMARY KEY,
            player_1 TEXT,
            player_2 TEXT,
            p1_pre_odds REAL,
            p2_pre_odds REAL,
            prematch_favorite TEXT,
            snapshot_time TEXT,
            alert_sent INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("Base de datos local SQLite lista.")

def save_prematch_favorite(match_id, player_1, player_2, p1_odds, p2_odds):
    favorite = player_1 if p1_odds < p2_odds else player_2
    fav_odds = p1_odds if favorite == player_1 else p2_odds
    
    PREMATCH_CACHE[match_id] = {
        "player_1": player_1,
        "player_2": player_2,
        "p1_pre_odds": p1_odds,
        "p2_pre_odds": p2_odds,
        "prematch_favorite": favorite,
        "fav_odds": fav_odds,
        "alert_sent": False
    }

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO wta_matches 
            (match_id, player_1, player_2, p1_pre_odds, p2_pre_odds, prematch_favorite, snapshot_time, alert_sent)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        ''', (match_id, player_1, player_2, p1_odds, p2_odds, favorite, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Error escribiendo en SQLite: {e}")

    logging.info(f"[T-30 CAPTURADO] {player_1} vs {player_2} | Favorita: {favorite} (Cuota: {fav_odds:.2f})")

def fetch_and_store_t30(match_id, player_1, player_2):
    params = {'apiKey': ODDS_API_KEY, 'regions': 'eu', 'markets': 'h2h'}
    try:
        res = requests.get(BASE_ODDS_URL, params=params, timeout=10).json()
        if isinstance(res, list):
            for match in res:
                if match['id'] == match_id:
                    outcomes = match['bookmakers'][0]['markets'][0]['outcomes']
                    p1_odds = next(o['price'] for o in outcomes if o['name'] == player_1)
                    p2_odds = next(o['price'] for o in outcomes if o['name'] == player_2)
                    save_prematch_favorite(match_id, player_1, player_2, p1_odds, p2_odds)
                    break
    except Exception as e:
        logging.error(f"Error al obtener cuotas T-30 para {match_id}: {e}")

def schedule_daily_matches(scheduler):
    params = {'apiKey': ODDS_API_KEY}
    try:
        res = requests.get(BASE_ODDS_URL, params=params, timeout=10)
        data = res.json()
        
        if isinstance(data, dict):
            logging.error(f"Respuesta de la API: {data.get('message', 'Error en la consulta')}")
            return

        if isinstance(data, list):
            for match in data:
                match_id = match['id']
                p1 = match['home_team']
                p2 = match['away_team']
                
                start_time = datetime.fromisoformat(match['commence_time'].replace('Z', '+00:00'))
                run_time = start_time - timedelta(minutes=30)
                
                if run_time > datetime.now(run_time.tzinfo):
                    scheduler.add_job(
                        fetch_and_store_t30,
                        'date',
                        run_date=run_time,
                        args=[match_id, p1, p2],
                        id=f"t30_{match_id}",
                        replace_existing=True
                    )
                    logging.info(f"Programado snapshot T-30 para {p1} vs {p2} a las {run_time}")
                else:
                    fetch_and_store_t30(match_id, p1, p2)
    except Exception as e:
        logging.error(f"Error escaneando partidos: {e}")

if __name__ == "__main__":
    init_db()
    
    # MANDA MENSAJE AUTOMÁTICO EN CUANTO ARRANCA
    send_telegram_test()
    
    scheduler = BackgroundScheduler()
    scheduler.start()
    
    scheduler.add_job(lambda: schedule_daily_matches(scheduler), 'interval', hours=6)
    schedule_daily_matches(scheduler)

    logging.info("Bot WTA activo y listo en Render.")
    
    import time
    while True:
        time.sleep(60)
