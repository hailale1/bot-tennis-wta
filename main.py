import os
import sqlite3
import logging
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

# --- 1. CONFIGURACIÓN DE ENTORNO ---
# Configura estas variables en el panel de Render (Environment Variables)
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "TU_ODDS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "TU_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "TU_TELEGRAM_CHAT_ID")
LIVE_SCORE_API_KEY = os.getenv("LIVE_SCORE_API_KEY", "TU_LIVE_SCORE_API_KEY")

BASE_ODDS_URL = "https://api.the-odds-api.com/v4/sports/tennis_wta/odds/"
DB_NAME = "wta_bot.db"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# CACHÉ EN MEMORIA (Evita fallos si Render reinicia la base de datos)
PREMATCH_CACHE = {}

# --- 2. BASE DE DATOS LOCAL Y CACHÉ ---
def init_db():
    """Inicializa la tabla donde se congelan las cuotas a T-30 minutos."""
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
    logging.info(" Base de datos local SQLite lista.")

def save_prematch_favorite(match_id, player_1, player_2, p1_odds, p2_odds):
    """Congela las cuotas a T-30 min en SQLite y en memoria RAM."""
    # Determina la favorita pre-partido (menor cuota)
    favorite = player_1 if p1_odds < p2_odds else player_2
    fav_odds = p1_odds if favorite == player_1 else p2_odds
    
    # 1. Guardar en memoria RAM
    PREMATCH_CACHE[match_id] = {
        "player_1": player_1,
        "player_2": player_2,
        "p1_pre_odds": p1_odds,
        "p2_pre_odds": p2_odds,
        "prematch_favorite": favorite,
        "fav_odds": fav_odds,
        "alert_sent": False
    }

    # 2. Guardar en SQLite
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

    logging.info(f" [T-30 CAPTURADO] {player_1} vs {player_2} | Favorita: {favorite} (Cuota: {fav_odds:.2f})")

# --- 3. CAPTURA DE CUOTAS A T-30 MINUTOS ---
def fetch_and_store_t30(match_id, player_1, player_2):
    """Obtiene y guarda las cuotas exactas a 30 min del inicio."""
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': 'eu',
        'markets': 'h2h'
    }
    try:
        res = requests.get(BASE_ODDS_URL, params=params, timeout=10).json()
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
    """Escanea los partidos WTA programados y programa la captura a T-30 min."""
    params = {'apiKey': ODDS_API_KEY}
    try:
        matches = requests.get(BASE_ODDS_URL, params=params, timeout=10).json()
        for match in matches:
            match_id = match['id']
            p1 = match['home_team']
            p2 = match['away_team']
            
            # Formato ISO UTC
            start_time = datetime.fromisoformat(match['commence_time'].replace('Z', '+00:00'))
            run_time = start_time - timedelta(minutes=30)
            
            # Si T-30 está en el futuro, se agenda
            if run_time > datetime.now(run_time.tzinfo):
                scheduler.add_job(
                    fetch_and_store_t30,
                    'date',
                    run_date=run_time,
                    args=[match_id, p1, p2],
                    id=f"t30_{match_id}",
                    replace_existing=True
                )
                logging.info(f" Programado snapshot T-30 para {p1} vs {p2} a las {run_time}")
            else:
                # Si el partido inicia en menos de 30 min, congelar cuotas inmediatamente
                fetch_and_store_t30(match_id, p1, p2)
    except Exception as e:
        logging.error(f"Error escaneando partidos programados: {e}")

# --- 4. ENVÍO DE ALERTAS DE TELEGRAM ---
def send_telegram_alert(match_name, favorite, fav_odds, winner_set1, fs_pct):
    """Envía el mensaje formateado a Telegram."""
    mensaje = (
        f"🎾 *ALERTA WTA: FAVORITA PERDIÓ 1ER SET*\n\n"
        f"📌 *Partido:* {match_name}\n"
        f"⭐ *Favorita Pre-Partido (T-30m):* {favorite} (Cuota: `{fav_odds:.2f}`)\n"
        f"❌ *Ganadora Set 1:* {winner_set1}\n"
        f"📊 *1er Servicio Favorita:* `{fs_pct:.1f}%` (Filtro >47% OK)\n\n"
        f"💡 *Oportunidad:* Entrada de valor en directo."
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
        logging.info(f" Alerta Telegram enviada con éxito para {match_name}")
    except Exception as e:
        logging.error(f"Error enviando mensaje a Telegram: {e}")

# --- 5. EVALUACIÓN DE MARCADORES EN VIVO ---
def evaluate_live_match(live_data):
    """
    Evalúa el partido en tiempo real al concluir el 1er set.
    live_data: dict con información reportada por tu API en directo.
    """
    match_id = live_data['match_id']
    set_1_finished = live_data.get('set_1_finished', False)
    winner_set_1 = live_data.get('winner_set_1')
    first_serve_pct = live_data.get('first_serve_pct', 0.0)

    if not set_1_finished:
        return

    # Buscar datos pre-partido en RAM o SQLite
    match_info = PREMATCH_CACHE.get(match_id)

    if not match_info:
        # Fallback: Consulta SQLite si no está en RAM
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT player_1, player_2, p1_pre_odds, p2_pre_odds, prematch_favorite, alert_sent 
            FROM wta_matches WHERE match_id = ?
        ''', (match_id,))
        rec = cursor.fetchone()
        conn.close()

        if rec:
            p1, p2, p1_o, p2_o, fav, sent = rec
            fav_o = p1_o if fav == p1 else p2_o
            match_info = {
                "player_1": p1, "player_2": p2,
                "prematch_favorite": fav, "fav_odds": fav_o,
                "alert_sent": bool(sent)
            }

    if not match_info:
        logging.warning(f"⚠️ Sin cuotas pre-partido registradas para {match_id}. Alerta omitida.")
        return

    if match_info['alert_sent']:
        return

    fav_player = match_info['prematch_favorite']
    fav_odds = match_info['fav_odds']

    # CONDICIONES DE FILTRO:
    # 1. La favorita perdió el Set 1
    # 2. Cuota pre-partido entre 1.20 y 1.80
    # 3. % 1er servicio de la favorita >= 47%
    favorita_perdio = (winner_set_1 != fav_player)
    cuota_en_rango = (1.20 <= fav_odds <= 1.80)
    servicio_valido = (first_serve_pct >= 47.0)

    if favorita_perdio and cuota_en_rango and servicio_valido:
        match_name = f"{match_info['player_1']} vs {match_info['player_2']}"
        send_telegram_alert(match_name, fav_player, fav_odds, winner_set1, first_serve_pct)

        # Marcar alerta como enviada en RAM y SQLite
        if match_id in PREMATCH_CACHE:
            PREMATCH_CACHE[match_id]['alert_sent'] = True

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE wta_matches SET alert_sent = 1 WHERE match_id = ?', (match_id,))
        conn.commit()
        conn.close()

# --- 6. ARRANQUE DEL BOT ---
if __name__ == "__main__":
    init_db()
    
    scheduler = BackgroundScheduler()
    scheduler.start()

    # Programar escaneo de partidos cada 6 horas
    scheduler.add_job(lambda: schedule_daily_matches(scheduler), 'interval', hours=6)
    
    # Primer escaneo al iniciar
    schedule_daily_matches(scheduler)

    logging.info(" Bot WTA activo y listo en Render.")
    
    # Mantener el proceso activo en Render
    import time
    while True:
        time.sleep(60)
