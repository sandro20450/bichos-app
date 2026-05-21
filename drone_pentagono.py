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

# === CONFIGURAÇÕES E CREDENCIAIS ===
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

# --- FUNÇÕES DE CONEXÃO E EXTRAÇÃO ---
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "HTML"})

def conectar_sheets():
    try:
        creds_dict = json.loads(google_creds_str)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds).open("CentralBichos")
    except Exception as e:
        enviar_telegram(f"❌ <b>ERRO NO DRONE:</b> Falha ao conectar no Google Sheets. Erro: {e}")
        return None

def extrair_dia(banca, data_alvo):
    url = f"{BANCAS_CONFIG[banca]}{data_alvo.strftime('%Y-%m-%d')}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        tabelas = soup.find_all('table')
        resultados = []
        for tab in tabelas:
            th_tag = tab.find('th')
            txt_th = th_tag.get_text().upper() if th_tag else ""
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b'])
            txt_prev = prev.get_text().upper() if prev else ""
            texto_alvo = txt_th + " " + txt_prev
            if "FEDERAL" in texto_alvo.upper(): continue
            match_hora = re.search(r'(\d{2}):(\d{2})|(\d{2})\s*[hH]', texto_alvo)
            if match_hora:
                if match_hora.group(1): nome = f"{match_hora.group(1)}:{match_hora.group(2)}"
                else: nome = f"{match_hora.group(3)}:00"
            else: nome = "Extra"
            milhares = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhares.append(nums[0][:4].zfill(4) if nums and len(nums[0]) >= 3 else "----")
            if len(milhares) >= 5:
                resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

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

def rodar_drone():
    sh = conectar_sheets()
    if not sh: return
    
    dt = date.today()
    total_salvos = 0
    
    for banca_alvo in MAPA_ABAS.keys():
        res = extrair_dia(banca_alvo, dt)
        if res:
            ws = sh.worksheet(MAPA_ABAS[banca_alvo])
            existentes = ws.get_all_values()
            set_exist = {f"{str(r[0]).strip()}_{str(r[1]).strip()}" for r in existentes if len(r) >= 2}
            p_ins = [l for l in res if f"{str(l[0]).strip()}_{str(l[1]).strip()}" not in set_exist]
            if p_ins:
                ws.append_rows(p_ins, value_input_option="RAW")
                total_salvos += len(p_ins)
    
    rodar_analise(sh)
    if total_salvos == 0: enviar_telegram("🟢 <b>ROTAÇÃO CONCLUÍDA</b>\nNenhum sorteio novo no momento.")

if __name__ == "__main__":
    rodar_drone()
