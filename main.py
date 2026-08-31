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

def calculate_comeback_probability(pre_odds_fav, live_odds_fav, first_serve_pct):
    """
    Calcula una probabilidad estimada de remontada (%) basándose en:
    - Probabilidad implícita inicial (Cuota T-5)
    - Reacción del mercado en vivo
    - Rendimiento técnico (Porcentaje de 1er servicio)
    """
    if not pre_odds_fav or pre_odds_fav <= 1.0:
        return 50.0 # Valor base neutral por defecto
        
    # 1. Probabilidad implícita inicial
    base_prob = (1.0 / pre_odds_fav) * 100
    
    # 2. Factor de Servicio (Si mantiene > 60% de primer servicio, suma fuerza)
    service_factor = 0.0
    if first_serve_pct >= 60:
        service_factor = 5.0
    elif first_serve_pct >= 50:
        service_factor = 2.0
    else:
        service_factor = -3.0
        
    # 3. Factor de resistencia de cuota (Comparación Pre vs Live)
    # Si la favorita era muy clara (< 1.40), su tasa histórica de remontada en WTA es mayor
    strength_bonus = 0.0
    if pre_odds_fav <= 1.30:
        strength_bonus = 8.0
    elif pre_odds_fav <= 1.60:
        strength_bonus = 4.0

    # Probabilidad final ajustada
    estimated_prob = base_prob + service_factor + strength_bonus
    
    # Acotar entre 15% y 85% para mantener realismo estadístico
    return round(max(15.0, min(85.0, estimated_prob)), 1)

def send_telegram_alert(match_info, fav_name, pre_odds, live_odds, serve_pct, prob):
    """Envía la alerta detallada a Telegram con la probabilidad calculada."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        message = (
            f"🚨 **ALERTA DE VALOR WTA** 🚨\n\n"
            f"🏆 **Torneo:** {match_info.get('tournament', 'WTA')}\n"
            f"🎾 **Partido:** {match_info.get('p1')} vs {match_info.get('p2')}\n"
            f"⭐ **Favorita Abajo:** {fav_name}\n\n"
            f"📊 **Métricas en Vivo:**\n"
            f"• Cuota Pre-Partido (T-5): `{pre_odds}`\n"
            f"• Cuota en Vivo (Set 2): `{live_odds}`\n"
            f"• 1er Servicio Favorita: `{serve_pct}%`\n\n"
            f"🎯 **Probabilidad Estimada de Remontada:** `{prob}%`"
        )
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, data=payload, timeout=10)
        except Exception as e:
            logging.error(f"Error al enviar alerta a Telegram: {e}")

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
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={ODDS_API_KEY}"
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
    
    scheduler = BackgroundScheduler()
    scheduler.start()
    
    scheduler.add_job(schedule_wta_matches, 'interval', minutes=20, args=[scheduler])
    logging.info("Bot WTA con Cálculo de Probabilidad Activo.")
    
    schedule_wta_matches(scheduler)
    
    import http.server
    import socketserver
    
    PORT = int(os.environ.get("PORT", 8000))
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
