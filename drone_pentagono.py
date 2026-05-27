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

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
google_creds_str = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}
COLUNAS_DF = ["P1", "P2", "P3", "P4", "P5"]
TITULOS_PREMIOS = ["1º PRÊMIO", "2º PRÊMIO", "3º PRÊMIO", "4º PRÊMIO", "5º PRÊMIO"]

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": mensagem[:4000], "parse_mode": "HTML"})

def conectar_sheets():
    try:
        creds_dict = json.loads(google_creds_str)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds).open("CentralBichos")
    except Exception as e: return None

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
            nome = f"{match_hora.group(1)}:{match_hora.group(2)}" if match_hora and match_hora.group(1) else "Extra"
            milhares = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhares.append(nums[0][:4].zfill(4) if nums and len(nums[0]) >= 3 else "----")
            if len(milhares) >= 5:
                resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

def gerar_matrizes_taticas():
    esquadroes = []; cms = []
    for c in range(7): cms.append({'c_min': c*100, 'c_max': c*100+399, 'm_min': c*1000, 'm_max': c*1000+3999})
    for cm in cms:
        for g in range(1, 12): esquadroes.append({'alvos': set(range(g, g+15)), 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G: {str(g).zfill(2)}-{str(g+14).zfill(2)}", 'lim': 7, **cm})
        for g in range(1, 15): esquadroes.append({'alvos': set(range(g, g+12)), 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G12: {str(g).zfill(2)}-{str(g+11).zfill(2)}", 'lim': 10, **cm})
        esquadroes.append({'alvos': set(range(1, 26, 2)), 'modo': 'grupo', 'tipo': 'impar', 'nome': "G: ÍMPARES", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(2, 26, 2)), 'modo': 'grupo', 'tipo': 'par', 'nome': "G: PARES", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(1, 51)), 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: BAIXAS", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(51, 100))|{0}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: ALTAS", 'lim': 9, **cm})
        
        bases_inv_8 = [[0,1,2,3,4,5,6,7], [1,2,3,4,5,6,7,8]]
        for b in bases_inv_8: esquadroes.append({'alvos': {int(f"{d1}{d2}") for d1 in b for d2 in b if d1!=d2}, 'modo': 'dezena', 'tipo': 'dez', 'nome': f"D: INV 8D ({b[0]} AO {b[-1]})", 'lim': 10, **cm})
            
        bases_inv_9 = [[0,1,2,3,4,5,6,7,8], [1,2,3,4,5,6,7,8,9]]
        for b in bases_inv_9: esquadroes.append({'alvos': {int(f"{d1}{d2}{d3}") for d1 in b for d2 in b for d3 in b if d1!=d2 and d2!=d3 and d1!=d3}, 'modo': 'centena', 'tipo': 'seq', 'nome': f"C: INV 9D ({b[0]} AO {b[-1]})", 'lim': 10, **cm})
    return esquadroes

def calcular_metricas_fantasma(df_analise, coluna, cfg):
    alvos, modo = cfg['alvos'], cfg['modo']
    c_min, c_max = cfg['c_min'], cfg['c_max']
    m_min, m_max = cfg['m_min'], cfg['m_max']
    cur_p, cur_c, cur_m = 0, 0, 0
    max_p, max_c, max_m = 0, 0, 0
    
    valores = df_analise[coluna].astype(str).tolist()
    for val in valores:
        milhar = val.strip().zfill(4)
        if milhar == "----" or milhar == "0nan" or milhar == "nan" or not milhar: continue
        try:
            m = int(milhar); c = int(milhar[-3:]); d = int(milhar[-2:]); u = int(milhar[-1:])
        except: continue
        
        g = 25 if d == 0 else math.ceil(d/4)
        hit_p = (modo == 'grupo' and g in alvos) or (modo == 'dezena' and d in alvos) or (modo == 'unidade' and u in alvos) or (modo == 'centena' and c in alvos)
        
        if hit_p: cur_p = 0
        else: 
            cur_p += 1
            if cur_p > max_p: max_p = cur_p
            
        if (c_min <= c <= c_max): cur_c = 0
        else: 
            cur_c += 1
            if cur_c > max_c: max_c = cur_c
            
        if (m_min <= m <= m_max): cur_m = 0
        else: 
            cur_m += 1
            if cur_m > max_m: max_m = cur_m
            
    return cur_p, cur_c, cur_m, max(max_p, cur_p), max(max_c, cur_c), max(max_m, cur_m)

def rodar_drone():
    sh = conectar_sheets()
    if not sh: return
    dt = date.today()
    total_salvos = 0; dados_bancas = {}
    
    for banca_nome, aba_nome in MAPA_ABAS.items():
        res = extrair_dia(banca_nome, dt)
        if res:
            ws = sh.worksheet(aba_nome)
            existentes = ws.get_all_values()
            set_exist = {f"{str(r[0]).strip()}_{str(r[1]).strip()}" for r in existentes if len(r) >= 2}
            p_ins = [l for l in res if f"{str(l[0]).strip()}_{str(l[1]).strip()}" not in set_exist]
            if p_ins:
                ws.append_rows(p_ins, value_input_option="RAW")
                total_salvos += len(p_ins)
            
            dados_atualizados = ws.get_all_values()
            if len(dados_atualizados) > 1:
                df = pd.DataFrame(dados_atualizados[1:], columns=["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"])
                df = df[df["P1"].astype(str).str.strip() != ""]
                dados_bancas[banca_nome] = df

    todos_esq = gerar_matrizes_taticas()
    msg_telegram = ""; achou_algo = False; alvos_vistos = set()

    for banca_nome, df in dados_bancas.items():
        if df.empty: continue
        ultimo_sorteio = str(df.iloc[-1]["Sorteio"])

        metrics_cache = {}
        for cfg in todos_esq:
            for col in COLUNAS_DF:
                if banca_nome == "Tradicional" and col != "P1": continue
                ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                metrics_cache[(cfg['nome'], cfg['c_min'], col)] = (ap, ac, am)

        for cfg in todos_esq:
            for col in COLUNAS_DF:
                if (cfg['nome'], cfg['c_min'], col) not in metrics_cache: continue
                ap, ac, am = metrics_cache[(cfg['nome'], cfg['c_min'], col)]
                ap_lim = cfg['lim']
                
                is_anomaly = False; is_alerta = False; tipo_ataque = ""
                
                if am >= 13 and ac >= 13 and ap >= ap_lim: is_anomaly = True; tipo_ataque = "🔥 ATAQUE TOTAL (G+C+M)"
                elif am >= 13: is_anomaly = True; tipo_ataque = f"🔵 ATAQUE MILHAR ({am}x)"
                elif ac >= 13: is_anomaly = True; tipo_ataque = f"🟢 ATAQUE CENTENA ({ac}x)"
                elif ap >= ap_lim: is_anomaly = True; tipo_ataque = f"🟡 ATAQUE FORTE ({cfg['modo'].upper()})"
                elif am >= 11 and ac >= 11 and ap >= (ap_lim - 2): is_alerta = True; tipo_ataque = "🟠 ALERTA: APROXIMAÇÃO TETO TOTAL"
                elif am >= 11: is_alerta = True; tipo_ataque = f"🟠 ALERTA: MILHAR PRÓXIMO AO TETO ({am}/13)"
                elif ac >= 11: is_alerta = True; tipo_ataque = f"🟠 ALERTA: CENTENA PRÓXIMA AO TETO ({ac}/13)"
                elif ap >= (ap_lim - 2): is_alerta = True; tipo_ataque = f"🟠 ALERTA: {cfg['modo'].upper()} PRÓXIMO AO TETO ({ap}/{ap_lim})"

                if is_anomaly or is_alerta:
                    c_min, c_max, m_min, m_max = cfg['c_min'], cfg['c_max'], cfg['m_min'], cfg['m_max']
                    sig = f"{banca_nome}_{col}_C_{c_min}" if "CENTENA" in tipo_ataque else f"{banca_nome}_{col}_{cfg['nome']}"
                    if sig in alvos_vistos: continue
                    alvos_vistos.add(sig)

                    msg_telegram += f"🎯 <b>{tipo_ataque}</b>\n🏦 {banca_nome} ({ultimo_sorteio}) | 🏆 {col}\nAlvo: <b>{cfg['nome']}</b>\nAtraso Principal: {ap}x\n"
                    msg_telegram += f"Base C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}\nAtraso C: {ac}x | Atraso M: {am}x\n\n"
                    achou_algo = True

    if achou_algo: enviar_telegram("🛸 <b>DRONE PENTÁGONO - RUPTURAS DETECTADAS</b> 🛸\n\n" + msg_telegram)
    elif total_salvos > 0: enviar_telegram(f"🟢 <b>ROTAÇÃO CONCLUÍDA</b>\n{total_salvos} novos sorteios salvos. Mercado estável.")

if __name__ == "__main__":
    rodar_drone()
