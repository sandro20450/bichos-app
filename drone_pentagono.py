def rodar_analise(sh):
    alerta_msg = "🎯 <b>RELATÓRIO DE VARREDURA:</b>\n"
    achou_algo = False
    for banca, aba in MAPA_ABAS.items():
        try:
            ws = sh.worksheet(aba); dados = ws.get_all_values()
            if len(dados) < 2: continue
            df = pd.DataFrame(dados[1:], columns=["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"])
            configs = [
                {'alvos': {7,8,9,12,13,14,17,18,19}, 'modo': 'grupo', 'nome': "MIOLO", 'lim': 8},
                {'alvos': set(range(1,16)), 'modo': 'grupo', 'nome': "G: 01-15", 'lim': 5}
            ]
            for cfg in configs:
                # Agora o robô varre do P1 ao P5
                for premio in ["P1", "P2", "P3", "P4", "P5"]:
                    atr = calcular_atraso(df, premio, cfg)
                    if atr >= cfg['lim']:
                        alerta_msg += f"\n⚠️ <b>{banca}</b> | {cfg['nome']} | {premio} | Atraso: {atr}x"
                        achou_algo = True
        except: continue
    if achou_algo: enviar_telegram(alerta_msg)
