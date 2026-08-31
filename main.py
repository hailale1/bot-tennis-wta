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
            "text": "🤖 ¡PRUEBA DE BOT EXITOSA! El servidor Render está activo y monitoreando TODOS los torneos WTA."
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
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_active_wta_tournaments():
    """Consulta la lista de todos los deportes/torneos activos y filtra los de WTA."""
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={ODDS_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            sports = r.json()
            # Detecta cualquier clave que contenga 'tennis_wta' (ej. tennis_wta_us_open, tennis_wta_wuhan, etc.)
            wta_keys = [s['key'] for s in sports if 'tennis_wta' in s['key']]
            logging.info(f"Torneos WTA activos encontrados: {wta_keys}")
            return wta_keys
        else:
            logging.error(f"Error al consultar lista de deportes: {r.text}")
            return []
    except Exception as e:
        logging.error(f"Fallo al obtener torneos WTA activos: {e}")
        return []

def fetch_and_store_all_wta():
    """Monitorea y almacena partidos de TODOS los torneos WTA activos."""
    wta_tournaments = get_active_wta_tournaments()
    
    if not wta_tournaments:
        logging.info("No hay torneos WTA activos en este momento.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    for sport_key in wta_tournaments:
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        params = {
            'apiKey': ODDS_API_KEY,
            'regions': 'eu',
            'markets': 'h2h'
        }
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                matches = r.json()
                for match in matches:
                    match_id = match.get('id')
                    p1 = match.get('home_team')
                    p2 = match.get('away_team')
                    
                    # Extraer cuotas del primer bookmaker disponible
                    bookmakers = match.get('bookmakers', [])
                    p1_odds, p2_odds = None, None
                    if bookmakers:
                        outcomes = bookmakers[0].get('markets', [{}])[0].get('outcomes', [])
                        for o in outcomes:
                            if o.get('name') == p1:
                                p1_odds = o.get('price')
                            elif o.get('name') == p2:
                                p2_odds = o.get('price')

                    if match_id and p1 and p2:
                        cursor.execute('''
                            INSERT OR REPLACE INTO wta_matches (match_id, player_1, player_2, p1_pre_odds, p2_pre_odds)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (match_id, p1, p2, p1_odds, p2_odds))
                        logging.info(f"Guardado/Actualizado partido [{sport_key}]: {p1} vs {p2} (Odds: {p1_odds} / {p2_odds})")
            else:
                logging.error(f"Error en API para {sport_key}: {r.text}")
        except Exception as e:
            logging.error(f"Error al procesar {sport_key}: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    send_telegram_test()
    
    # Iniciar programador de tareas cada 30 minutos para revisar torneos y cuotas
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_and_store_all_wta, 'interval', minutes=30)
    scheduler.start()
    logging.info("Bot WTA (Monitoreo Global) activo y listo en Render.")
    
    # Ejecución inicial
    fetch_and_store_all_wta()
    
    # Mantener proceso vivo para el web server de Render
    import http.server
    import socketserver
    
    PORT = int(os.environ.get("PORT", 8000))
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
