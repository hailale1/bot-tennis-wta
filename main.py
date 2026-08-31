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

DB_NAME = "wta_bot.db"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
PREMATCH_CACHE = {}

def send_telegram_test():
    """Envía un mensaje de prueba a Telegram al iniciar el bot."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": "🤖 ¡PRUEBA EXITOSA! Bot WTA activo con monitoreo global y captura exacta a T-5 minutos."
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
            tournament TEXT,
            player_1 TEXT,
            player_2 TEXT,
            p1_pre_odds REAL,
            p2_pre_odds REAL,
            commence_time TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_active_wta_tournaments():
    """Consulta todos los torneos activos de la WTA."""
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={ODDS_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            sports = r.json()
            wta_keys = [s['key'] for s in sports if 'tennis_wta' in s['key']]
            logging.info(f"Torneos WTA detectados: {wta_keys}")
            return wta_keys
        else:
            logging.error(f"Error al obtener deportes: {r.text}")
            return []
    except Exception as e:
        logging.error(f"Fallo al consultar torneos: {e}")
        return []

def fetch_single_match_odds(sport_key, match_id, p1, p2):
    """Guarda las cuotas exactas tomadas a 5 minutos del inicio del partido (T-5)."""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {'apiKey': ODDS_API_KEY, 'regions': 'eu', 'markets': 'h2h'}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            matches = r.json()
            for m in matches:
                if m.get('id') == match_id:
                    bookmakers = m.get('bookmakers', [])
                    p1_odds, p2_odds = None, None
                    if bookmakers:
                        outcomes = bookmakers[0].get('markets', [{}])[0].get('outcomes', [])
                        for o in outcomes:
                            if o.get('name') == p1:
                                p1_odds = o.get('price')
                            elif o.get('name') == p2:
                                p2_odds = o.get('price')
                    
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO wta_matches (match_id, tournament, player_1, player_2, p1_pre_odds, p2_pre_odds)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (match_id, sport_key, p1, p2, p1_odds, p2_odds))
                    conn.commit()
                    conn.close()
                    logging.info(f"SNAPSHOT T-5 GUARDADO [{sport_key}]: {p1} vs {p2} -> Odds: {p1_odds} / {p2_odds}")
    except Exception as e:
        logging.error(f"Error en snapshot T-5 para {match_id}: {e}")

def schedule_wta_matches(scheduler):
    """Busca los partidos de todos los torneos WTA y programa las capturas a T-5 minutos."""
    wta_tournaments = get_active_wta_tournaments()
    
    for sport_key in wta_tournaments:
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
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
                            scheduler.add_job(
                                fetch_single_match_odds,
                                'date',
                                run_date=t5_dt,
                                args=[sport_key, match_id, p1, p2],
                                id=f"t5_{match_id}",
                                replace_existing=True
                            )
                            PREMATCH_CACHE[match_id] = True
                            logging.info(f"Programado snapshot T-5 para {p1} vs {p2} a las {t5_dt} UTC")
        except Exception as e:
            logging.error(f"Error al programar partidos para {sport_key}: {e}")

if __name__ == "__main__":
    init_db()
    send_telegram_test()
    
    scheduler = BackgroundScheduler()
    scheduler.start()
    
    # Revisa la agenda de partidos de todos los torneos WTA cada hora
    scheduler.add_job(schedule_wta_matches, 'interval', hours=1, args=[scheduler])
    logging.info("Bot WTA (Global + Snapshots T-5) activo en Render.")
    
    # Programación inicial
    schedule_wta_matches(scheduler)
    
    import http.server
    import socketserver
    
    PORT = int(os.environ.get("PORT", 8000))
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
