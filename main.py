import os
import sqlite3
import requests
from datetime import datetime

# Cargar variables de entorno o ingresar valores de prueba
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "TU_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "TU_TELEGRAM_CHAT_ID")
DB_NAME = "wta_bot.db"

def run_test():
    print("🚀 INICIANDO CORRIDA DE PRUEBA DEL BOT WTA...")

    # 1. Crear / Verificar Base de Datos
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
    
    # 2. Insertar Partido Simulado (T-30 min)
    # Ejemplo: Favorita (Player A, cuota 1.45) vs Underdog (Player B, cuota 2.70)
    test_match_id = "test_wta_101"
    player_1 = "Iga Swiatek"      # Favorita
    player_2 = "Linda Noskova"     # Underdog
    p1_odds = 1.45
    p2_odds = 2.70
    favorite = player_1

    cursor.execute('''
        INSERT OR REPLACE INTO wta_matches 
        (match_id, player_1, player_2, p1_pre_odds, p2_pre_odds, prematch_favorite, snapshot_time, alert_sent)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    ''', (test_match_id, player_1, player_2, p1_odds, p2_odds, favorite, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print(f"✅ [SIMULACIÓN T-30] Registrado partido de prueba: {player_1} ({p1_odds}) vs {player_2} ({p2_odds})")

    # 3. Simular actualización en vivo al terminar el 1er set
    live_data_simulation = {
        "match_id": test_match_id,
        "set_1_finished": True,
        "winner_set_1": player_2,      # La favorita PERDIÓ el 1er set (Ganó Noskova)
        "first_serve_pct": 52.0        # Cumple el filtro >= 47%
    }

    # 4. Evaluar filtros
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT player_1, player_2, p1_pre_odds, p2_pre_odds, prematch_favorite, alert_sent FROM wta_matches WHERE match_id = ?', (test_match_id,))
    rec = cursor.fetchone()
    conn.close()

    p1, p2, p1_o, p2_o, fav, alert_sent = rec
    fav_odds = p1_o if fav == p1 else p2_o
    winner_set1 = live_data_simulation["winner_set_1"]
    fs_pct = live_data_simulation["first_serve_pct"]

    favorita_perdio = (winner_set1 != fav)
    cuota_ok = (1.20 <= fav_odds <= 1.80)
    servicio_ok = (fs_pct >= 47.0)

    print(f"📊 Evaluando filtros: Favorita perdió={favorita_perdio} | Cuota en rango={cuota_ok} ({fav_odds}) | Servicio OK={servicio_ok} ({fs_pct}%)")

    # 5. Disparar Alerta a Telegram
    if favorita_perdio and cuota_ok and servicio_ok and alert_sent == 0:
        mensaje = (
            f"🧪 *[CORRIDA DE PRUEBA]* 🧪\n"
            f"🎾 *ALERTA WTA: FAVORITA PERDIÓ 1ER SET*\n\n"
            f"📌 *Partido:* {p1} vs {p2}\n"
            f"⭐ *Favorita Pre-Partido (T-30m):* {fav} (Cuota: `{fav_odds:.2f}`)\n"
            f"❌ *Ganadora Set 1:* {winner_set1}\n"
            f"📊 *1er Servicio Favorita:* `{fs_pct:.1f}%` (Filtro >47% OK)\n\n"
            f"✅ *El bot está configurado y respondiendo correctamente.*"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
        
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            print("📩 ¡ALERTA DE PRUEBA ENVIADA CON ÉXITO A TELEGRAM!")
        else:
            print(f"❌ Error al enviar a Telegram: {res.text}")

if __name__ == "__main__":
    run_test()
