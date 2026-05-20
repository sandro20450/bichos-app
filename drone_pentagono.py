import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import date
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# === CREDENCIAIS ===
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
google_creds_str = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://www.resultadofacil.com.br/resultados-nordeste-montes-claros-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

# --- LÓGICA DE ANÁLISE ---
def get_grupo_int(m):
    try: d = int(str(m)[-2:]); return 25 if d == 0 else math.ceil(d/4)
    except: return None

def calcular_atraso(df_analise, coluna, cfg):
    alvos, modo = cfg['alvos'], cfg['modo']
    atr = 0
    for i in range(len(df_analise)-1, -1, -1):
        milhar = str(df_analise.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "nan" or not milhar.strip(): continue
        g = get_grupo_int(milhar); d = int(milhar[-2:]); u = int(milhar[-1:])
        hit = (modo == 'grupo' and g in alvos) or (modo == 'dezena' and d in alvos) or (modo == 'unidade' and u in alvos)
        if hit: break
        atr += 1
    return atr

def rodar_analise(sh):
    alerta_msg = "🎯 <b>RELATÓRIO DE VARREDURA:</b>\n"
    achou_algo = False
    for banca, aba in MAPA_ABAS.items():
        ws = sh.worksheet(aba); dados = ws.get_all_values()
        if len(dados) < 2: continue
        df = pd.DataFrame(dados[1:], columns=["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"])
        # Matriz simplificada para o Drone (exemplo: Miolo e 15 Grupos)
        configs = [
            {'alvos': {7,8,9,12,13,14,17,18,19}, 'modo': 'grupo', 'nome': "MIOLO", 'lim': 8},
            {'alvos': set(range(1,16)), 'modo': 'grupo', 'nome': "G: 01-15", 'lim': 5}
        ]
        for cfg in configs:
            for col in ["P1"]: # Focado no 1º prêmio
                atr = calcular_atraso(df, col, cfg)
                if atr >= cfg['lim']:
                    alerta_msg += f"\n⚠️ <b>{banca}</b> | {cfg['nome']} | Atraso: {atr}x"
                    achou_algo = True
    if achou_algo: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": alerta_msg, "parse_mode": "HTML"})

# --- FUNÇÕES DE EXTRAÇÃO (Mantidas) ---
# [Insira aqui as funções 'extrair_dia', 'conectar_sheets' do código anterior]
# (Por brevidade, conecte as funções de extração que já temos)

def rodar_drone():
    sh = conectar_sheets()
    if not sh: return
    # ... (executar extração) ...
    # Após atualizar:
    rodar_analise(sh)

if __name__ == "__main__":
    rodar_drone()
