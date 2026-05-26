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
    "Monte Carlos": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}
COLUNAS_DF = ["P1", "P2", "P3", "P4", "P5"]
TITULOS_PREMIOS = ["1º PRÊMIO", "2º PRÊMIO", "3º PRÊMIO", "4º PRÊMIO", "5º PRÊMIO"]

# --- FUNÇÕES BÁSICAS DE CONEXÃO E EXTRAÇÃO ---
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    if len(mensagem) > 4000:
        partes = [mensagem[i:i+4000] for i in range(0, len(mensagem), 4000)]
        for parte in partes:
            requests.post(url, data={"chat_id": CHAT_ID, "text": parte, "parse_mode": "HTML"})
    else:
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

def get_grupo_int(m):
    try: d = int(str(m)[-2:]); return 25 if d == 0 else math.ceil(d/4)
    except: return None

# --- MESMOS MOTORES DO APP PENTÁGONO ---
def gerar_matrizes_taticas():
    esquadroes = []
    cms = []
    for c in range(7): cms.append({'c_min': c*100, 'c_max': c*100+399, 'm_min': c*1000, 'm_max': c*1000+3999})
    for cm in cms:
        for g in range(1, 12):
            esquadroes.append({'alvos': set(range(g, g + 15)), 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G: {str(g).zfill(2)}-{str(g+14).zfill(2)}", 'lim': 7, **cm})
        for g in range(1, 15):
            esquadroes.append({'alvos': set(range(g, g + 12)), 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G12: {str(g).zfill(2)}-{str(g+11).zfill(2)}", 'lim': 10, **cm})
        
        esquadroes.append({'alvos': set(range(1, 26, 2)), 'modo': 'grupo', 'tipo': 'impar', 'nome': "G: ÍMPARES", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(2, 26, 2)), 'modo': 'grupo', 'tipo': 'par', 'nome': "G: PARES", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(1, 51)), 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: BAIXAS (01-50)", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(51, 100)) | {0}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: ALTAS (51-00)", 'lim': 9, **cm})
        esquadroes.append({'alvos': {x for x in range(100) if x % 2 != 0}, 'modo': 'dezena', 'tipo': 'impar', 'nome': "D: ÍMPARES", 'lim': 9, **cm})
        esquadroes.append({'alvos': {x for x in range(100) if x % 2 == 0}, 'modo': 'dezena', 'tipo': 'par', 'nome': "D: PARES", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(26, 76)), 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: MIOLO (26-75)", 'lim': 9, **cm})
        esquadroes.append({'alvos': set(range(1, 26)) | set(range(76, 100)) | {0}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: BORDAS", 'lim': 9, **cm})
        esquadroes.append({'alvos': {x for x in range(100) if x % 10 in [1, 2, 3, 4, 5]}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: FINAIS BAIXOS (1-5)", 'lim': 9, **cm})
        esquadroes.append({'alvos': {x for x in range(100) if x % 10 in [6, 7, 8, 9, 0]}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: FINAIS ALTOS (6-0)", 'lim': 9, **cm})
        
        bases_inv_8 = [[0,1,2,3,4,5,6,7], [1,2,3,4,5,6,7,8], [2,3,4,5,6,7,8,9], [3,4,5,6,7,8,9,0], [4,5,6,7,8,9,0,1], [5,6,7,8,9,0,1,2], [6,7,8,9,0,1,2,3], [7,8,9,0,1,2,3,4], [8,9,0,1,2,3,4,5], [9,0,1,2,3,4,5,6]]
        for b in bases_inv_8:
            alvos_inv = {int(f"{d1}{d2}") for d1 in b for d2 in b if d1 != d2}
            esquadroes.append({'alvos': alvos_inv, 'modo': 'dezena', 'tipo': 'dez', 'nome': f"D: INV 8D ({b[0]} AO {b[-1]})", 'lim': 10, **cm})
            
        bases_inv_9 = [[0,1,2,3,4,5,6,7,8], [1,2,3,4,5,6,7,8,9], [2,3,4,5,6,7,8,9,0], [3,4,5,6,7,8,9,0,1], [4,5,6,7,8,9,0,1,2], [5,6,7,8,9,0,1,2,3], [6,7,8,9,0,1,2,3,4], [7,8,9,0,1,2,3,4,5], [8,9,0,1,2,3,4,5,6], [9,0,1,2,3,4,5,6,7]]
        for b in bases_inv_9:
            alvos_inv_c = {int(f"{d1}{d2}{d3}") for d1 in b for d2 in b for d3 in b if d1 != d2 and d2 != d3 and d1 != d3}
            esquadroes.append({'alvos': alvos_inv_c, 'modo': 'centena', 'tipo': 'seq', 'nome': f"C: INV 9D ({b[0]} AO {b[-1]})", 'lim': 10, **cm})
    
    esquadroes_unidade = [
        {'alvos': {1, 2, 3, 4, 5}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: BAIXAS (1-5)", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {6, 7, 8, 9, 0}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ALTAS (6-0)", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {1, 3, 5, 7, 9}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ÍMPARES", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {0, 2, 4, 6, 8}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: PARES", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999}
    ]
    esquadroes.extend(esquadroes_unidade)
    return esquadroes

def calcular_metricas_fantasma(df_analise, coluna, cfg):
    alvos, modo = cfg['alvos'], cfg['modo']
    c_min, c_max = cfg['c_min'], cfg['c_max']
    m_min, m_max = cfg['m_min'], cfg['m_max']
    atr_p, atr_c, atr_m = 0, 0, 0 
    achou_p, achou_c, achou_m = False, False, False
    for i in range(len(df_analise)-1, -1, -1):
        milhar = str(df_analise.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "nan" or not milhar.strip(): continue
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:]); m = int(milhar); d = int(milhar[-2:]); u = int(milhar[-1:]) 
        except: c, m, d, u = -1, -1, -1, -1
        hit_p = False
        if modo == 'grupo' and g is not None and g in alvos: hit_p = True
        elif modo == 'dezena' and d in alvos: hit_p = True
        elif modo == 'unidade' and u in alvos: hit_p = True
        elif modo == 'centena' and c in alvos: hit_p = True
        
        if not achou_p:
            if hit_p: achou_p = True
            else: atr_p += 1
        if not achou_c:
            if c_min <= c <= c_max: achou_c = True
            else: atr_c += 1
        if not achou_m:
            if m_min <= m <= m_max: achou_m = True
            else: atr_m += 1
        if achou_p and achou_c and achou_m: break
    return atr_p, atr_c, atr_m

def direcao_pendulo(prev, curr):
    if prev == curr: return "="
    dist_c = (curr - prev) % 25
    dist_d = (prev - curr) % 25
    if 1 <= dist_c <= 6: return "C"
    if 1 <= dist_d <= 6: return "D"
    return "-" 

def processar_pendulo(df, coluna):
    all_groups = []
    for i in range(len(df)):
        m = str(df.iloc[i][coluna]).zfill(4)
        if m != "----" and m != "nan" and m.strip():
            g = get_grupo_int(m)
            if g is not None: all_groups.append(g) 
                
    if len(all_groups) < 6: return None
    dirs_history = []
    for i in range(1, len(all_groups)):
        dirs_history.append(direcao_pendulo(all_groups[i-1], all_groups[i]))
        
    curr_streak = 0
    curr_dir = dirs_history[-1]
    if curr_dir in ["C", "D"]:
        for d in reversed(dirs_history):
            if d == curr_dir: curr_streak += 1
            else: break
            
    if curr_streak >= 5:
        jogos = []; curr = all_groups[-1]
        if curr_dir == "C":
            for _ in range(15):
                jogos.append(str(curr).zfill(2))
                curr -= 1
                if curr < 1: curr = 25
        else:
            for _ in range(15):
                jogos.append(str(curr).zfill(2))
                curr += 1
                if curr > 25: curr = 1
        return curr_streak, curr_dir, jogos
    return None

def get_hedge_grupos(df, col, cfg_matriz, metrics_cache):
    grupos = list(cfg_matriz['alvos'])
    scores = {g: 0 for g in grupos}

    col_delays = {k_name: val[0] for (k_name, k_col), val in metrics_cache.items() if k_col == col}

    mass_max = max([col_delays.get('G: ÍMPARES', 0), col_delays.get('G: PARES', 0),
                    col_delays.get('D: ALTAS (51-00)', 0), col_delays.get('D: BAIXAS (01-50)', 0)])

    if mass_max >= 3:
        if col_delays.get('G: ÍMPARES', 0) >= 3:
            for g in grupos:
                if g % 2 == 0: scores[g] += 1
        if col_delays.get('G: PARES', 0) >= 3:
            for g in grupos:
                if g % 2 != 0: scores[g] += 1
        if col_delays.get('D: ALTAS (51-00)', 0) >= 3:
            for g in grupos:
                if g <= 12: scores[g] += 1
        if col_delays.get('D: BAIXAS (01-50)', 0) >= 3:
            for g in grupos:
                if g >= 13: scores[g] += 1
    else:
        uni_max = max([col_delays.get('U: ÍMPARES', 0), col_delays.get('U: PARES', 0),
                       col_delays.get('U: ALTAS (6-0)', 0), col_delays.get('U: BAIXAS (1-5)', 0)])
        if uni_max >= 3:
            if col_delays.get('U: ÍMPARES', 0) >= 3:
                for g in grupos:
                    if (g % 10) % 2 == 0: scores[g] += 1
            if col_delays.get('U: PARES', 0) >= 3:
                for g in grupos:
                    if (g % 10) % 2 != 0: scores[g] += 1
            if col_delays.get('U: ALTAS (6-0)', 0) >= 3:
                for g in grupos:
                    if (g % 10) in [1,2,3,4,5]: scores[g] += 1
            if col_delays.get('U: BAIXAS (1-5)', 0) >= 3:
                for g in grupos:
                    if (g % 10) in [6,7,8,9,0]: scores[g] += 1

    sorted_g = sorted(grupos, key=lambda x: scores[x], reverse=True)
    eliminar = [g for g in sorted_g[:2] if scores[g] > 0] 

    if not eliminar: return None 

    seguro = {}
    for g in eliminar:
        dezenas = [g*4 - 3, g*4 - 2, g*4 - 1, g*4]
        if g == 25: dezenas = [97, 98, 99, 0]
        max_d_delay = -1
        best_d = -1
        for d in dezenas:
            delay_d = 0
            for i in range(len(df)-1, -1, -1):
                m = str(df.iloc[i][col]).zfill(4)
                if m == "----" or m == "nan": continue
                try: dez_val = int(m[-2:])
                except: dez_val = -1
                if dez_val == d: break
                delay_d += 1
            if delay_d > max_d_delay:
                max_d_delay = delay_d; best_d = d
        seguro[g] = (best_d, max_d_delay)

    manter = [g for g in grupos if g not in eliminar]
    return {'eliminar': sorted(eliminar), 'manter': sorted(manter), 'seguro': seguro}

def get_cobertura_massa(df, col, cfg_nome):
    opostos = {
        "G: PARES": ("Grupo Ímpar", [1,3,5,7,9,11,13,15,17,19,21,23,25]),
        "G: ÍMPARES": ("Grupo Par", [2,4,6,8,10,12,14,16,18,20,22,24]),
        "D: PARES": ("Grupo Ímpar", [1,3,5,7,9,11,13,15,17,19,21,23,25]),
        "D: ÍMPARES": ("Grupo Par", [2,4,6,8,10,12,14,16,18,20,22,24]),
        "D: ALTAS (51-00)": ("Grupo Baixo", list(range(1, 14))),
        "D: BAIXAS (01-50)": ("Grupo Alto", list(range(14, 26))),
        "U: PARES": ("Grupo Ímpar", [1,3,5,7,9,11,13,15,17,19,21,23,25]),
        "U: ÍMPARES": ("Grupo Par", [2,4,6,8,10,12,14,16,18,20,22,24]),
        "U: ALTAS (6-0)": ("Grupo Baixo", list(range(1, 14))),
        "U: BAIXAS (1-5)": ("Grupo Alto", list(range(14, 26)))
    }
    
    if cfg_nome not in opostos:
        return None
        
    desc_oposto, lista_grupos = opostos[cfg_nome]
    max_delay = -1
    best_g = -1
    
    for g in lista_grupos:
        delay_g = 0
        for i in range(len(df)-1, -1, -1):
            m = str(df.iloc[i][col]).zfill(4)
            if m == "----" or m == "nan": continue
            g_val = get_grupo_int(m)
            if g_val == g: break
            delay_g += 1
        if delay_g > max_delay:
            max_delay = delay_g
            best_g = g
            
    return best_g, max_delay, desc_oposto

# --- MOTOR PRINCIPAL DO DRONE ---
def rodar_drone():
    sh = conectar_sheets()
    if not sh: return
    
    dt = date.today()
    total_salvos = 0
    dados_bancas = {}
    
    for banca_nome, aba_nome in MAPA_ABAS.items():
        res = extrair_dia(banca_nome, dt)
        ws = sh.worksheet(aba_nome)
        if res:
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
    msg_telegram = ""
    achou_algo = False
    alvos_vistos = set()

    for banca_nome, df in dados_bancas.items():
        if df.empty: continue
        ultimo_sorteio = str(df.iloc[-1]["Sorteio"])

        for i, col in enumerate(COLUNAS_DF):
            if banca_nome == "Tradicional" and col != "P1": continue
            res_pendulo = processar_pendulo(df, col)
            if res_pendulo:
                curr_streak, curr_dir, jogos = res_pendulo
                dir_texto = "Decrescente" if curr_dir == "C" else "Crescente"
                
                sig_pendulo = f"PENDULO_{banca_nome}_{col}"
                if sig_pendulo not in alvos_vistos:
                    msg_telegram += f"🧲 <b>PÊNDULO ({curr_streak}x)</b>\n"
                    msg_telegram += f"🏦 {banca_nome} | 🏆 {TITULOS_PREMIOS[i]}\n"
                    msg_telegram += f"Direção: {dir_texto}\n"
                    msg_telegram += f"Jogar: {', '.join(jogos)}\n\n"
                    achou_algo = True
                    alvos_vistos.add(sig_pendulo)

        metrics_cache = {}
        for cfg in todos_esq:
            for i, col in enumerate(COLUNAS_DF):
                if banca_nome == "Tradicional" and col != "P1": continue
                ap, ac, am = calcular_metricas_fantasma(df, col, cfg)
                metrics_cache[(cfg['nome'], col)] = (ap, ac, am)

        for cfg in todos_esq:
            for i, col in enumerate(COLUNAS_DF):
                if (cfg['nome'], col) not in metrics_cache: continue
                ap, ac, am = metrics_cache[(cfg['nome'], col)]
                ap_lim = cfg['lim']
                
                is_anomaly = False
                tipo_ataque = ""
                
                if am >= 13 and ac >= 13 and ap >= ap_lim:
                    is_anomaly = True; tipo_ataque = "🔥 ATAQUE TOTAL (G+C+M)"
                elif am >= 13:
                    is_anomaly = True; tipo_ataque = f"🔵 ATAQUE MILHAR ({am}x)"
                elif ac >= 13:
                    is_anomaly = True; tipo_ataque = f"🟢 ATAQUE CENTENA ({ac}x)"
                elif cfg['modo'] == 'unidade' and ap >= 9:
                    is_anomaly = True; tipo_ataque = "🔥 ATAQUE UNIDADE"
                elif ap >= ap_lim:
                    is_anomaly = True; tipo_ataque = f"🟡 ATAQUE FORTE ({cfg['modo'].upper()})"

                if is_anomaly:
                    c_min, c_max, m_min, m_max = cfg['c_min'], cfg['c_max'], cfg['m_min'], cfg['m_max']
                    
                    if "MILHAR" in tipo_ataque:
                        sig = f"{banca_nome}_{col}_M_{m_min}"
                    elif "CENTENA" in tipo_ataque:
                        sig = f"{banca_nome}_{col}_C_{c_min}"
                    else:
                        sig = f"{banca_nome}_{col}_{cfg['nome']}"
                        
                    if sig in alvos_vistos: continue
                    alvos_vistos.add(sig)

                    msg_telegram += f"🎯 <b>{tipo_ataque}</b>\n"
                    msg_telegram += f"🏦 {banca_nome} ({ultimo_sorteio}) | 🏆 {TITULOS_PREMIOS[i]}\n"
                    msg_telegram += f"Alvo: <b>{cfg['nome']}</b>\n"
                    msg_telegram += f"Atraso Principal: {ap}x\n"
                    if "CENTENA" not in tipo_ataque and "MILHAR" not in tipo_ataque:
                        msg_telegram += f"Base C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)} | M: {str(m_min).zfill(4)} ao {str(m_max).zfill(4)}\n"
                    msg_telegram += f"Atraso C: {ac}x | Atraso M: {am}x\n"

                    if cfg['modo'] == 'grupo' and cfg['tipo'] == 'seq':
                        hedge_data = get_hedge_grupos(df, col, cfg, metrics_cache)
                        if hedge_data:
                            elim_str = ", ".join([str(x).zfill(2) for x in hedge_data['eliminar']])
                            mant_str = ", ".join([str(x).zfill(2) for x in hedge_data['manter']])
                            seg_list = [f"D:{str(d).zfill(2)} ({delay}x)" for g, (d, delay) in hedge_data['seguro'].items()]
                            seg_str = " | ".join(seg_list)
                            
                            msg_telegram += f"🛡️ <b>Desdobramento:</b>\n"
                            msg_telegram += f"❌ Cortar: G {elim_str}\n"
                            msg_telegram += f"✅ Jogar: {mant_str}\n"
                            msg_telegram += f"🆘 Seguro: {seg_str}\n"
                        else:
                            msg_telegram += f"🛡️ <b>Desdobramento:</b> Neutro. Jogar Integral.\n"
                    else:
                        # NOVO: MOTOR DE COBERTURA PARA DRONE
                        cob_data = get_cobertura_massa(df, col, cfg['nome'])
                        if cob_data:
                            g_alvo, delay_g, desc_oposto = cob_data
                            msg_telegram += f"🛡️ <b>Cobertura Tática:</b>\n"
                            msg_telegram += f"O {desc_oposto} mais perigoso é o <b>G{str(g_alvo).zfill(2)}</b> ({delay_g}x).\n"
                            msg_telegram += f"🎯 Aposta Sniper sugerida nele.\n"
                            
                    msg_telegram += "\n"
                    achou_algo = True

    if achou_algo:
        cabecalho = "🛸 <b>DRONE PENTÁGONO - RUPTURAS DETECTADAS</b> 🛸\n\n"
        enviar_telegram(cabecalho + msg_telegram)
    elif total_salvos > 0:
        enviar_telegram(f"🟢 <b>ROTAÇÃO CONCLUÍDA</b>\n{total_salvos} novos sorteios salvos. Mercado estável, sem alvos no teto máximo.")
    else:
        enviar_telegram("🟢 <b>ROTAÇÃO CONCLUÍDA (MODO FURTIVO)</b>\nNenhum sorteio novo nas bancas. Monitoramento ativo.")

if __name__ == "__main__":
    rodar_drone()
