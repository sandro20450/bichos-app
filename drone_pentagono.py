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

# === CREDENCIAIS DO COFRE DO GITHUB ===
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
# (Ajuste rápido: coloquei Caminho e Monte Carlos no resultado facil como o senhor havia configurado na V65.15)

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

def rodar_varredura():
    enviar_telegram("🛸 <b>DRONE PENTÁGONO ATIVADO</b>\nIniciando extração e varredura de alvos...")
    sh = conectar_sheets()
    if not sh: return
    
    dt = date.today()
    total_salvos = 0
    relatorio = ""
    
    for banca_alvo in BANCAS_CONFIG.keys():
        res = extrair_dia(banca_alvo, dt)
        if res:
            ws = sh.worksheet(MAPA_ABAS[banca_alvo])
            existentes = ws.get_all_values()
            set_exist = {f"{str(r[0]).strip()}_{str(r[1]).strip()}" for r in existentes if len(r) >= 2}
            p_ins = [l for l in res if f"{str(l[0]).strip()}_{str(l[1]).strip()}" not in set_exist]
            if p_ins:
                ws.append_rows(p_ins, value_input_option="RAW")
                total_salvos += len(p_ins)
                relatorio += f"✅ {banca_alvo}: {len(p_ins)} novos sorteios.\n"
    
    if total_salvos > 0:
        enviar_telegram(f"📊 <b>PLANILHA ATUALIZADA!</b>\n{relatorio}\n<i>(No futuro, os cálculos de atraso serão processados aqui).</i>")
    else:
        enviar_telegram("🟢 <b>ROTAÇÃO CONCLUÍDA</b>\nNenhum sorteio novo encontrado no momento.")

if __name__ == "__main__":
    rodar_varredura()
