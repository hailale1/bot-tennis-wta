def schedule_daily_matches(scheduler):
    """Escanea los partidos WTA programados de forma segura."""
    params = {'apiKey': ODDS_API_KEY}
    try:
        response = requests.get(BASE_ODDS_URL, params=params, timeout=10)
        data = response.json()
        
        # Validar si la API devolvió un error (diccionario en lugar de lista)
        if isinstance(data, dict):
            error_msg = data.get('message', 'Error desconocido de la API')
            logging.error(f" Error de la API de Odds: {error_msg}")
            return

        # Si la respuesta es una lista válida de partidos
        if isinstance(data, list):
            for match in data:
                match_id = match['id']
                p1 = match['home_team']
                p2 = match['away_team']
                
                # Formato ISO UTC
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
                    logging.info(f" Programado snapshot T-30 para {p1} vs {p2} a las {run_time}")
                else:
                    fetch_and_store_t30(match_id, p1, p2)
    except Exception as e:
        logging.error(f"Error escaneando partidos programados: {e}")
