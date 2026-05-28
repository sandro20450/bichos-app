import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =============================================================================
# --- 1. CONFIGURAÇÕES E CSS ULTRA-RÁPIDO ---
# =============================================================================
st.set_page_config(page_title="Pentágono V65.34 - Caça 9D", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.home-box { border-radius: 8px; padding: 12px; margin-bottom: 15px; text-align: center; border: 1px solid #444; background-color: #111; }
.rodape-tatico { position: fixed; bottom: 0; left: 0; width: 100%; background-color: #000; color: #ffcc00; text-align: center; padding: 10px; font-size: 14px; border-top: 2px solid #ff4b4b; z-index: 9999; font-weight: bold;}
.block-container { padding-bottom: 80px; }
div.stButton > button { width: 100%; border-radius: 8px; font-weight: bold; min-height: 45px; border: 1px solid #555; }
.alerta-supremo { background-color: rgba(255,0,255,0.1); border: 1px solid #ff00ff; color: #ff00ff; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 12px; }
.alerta-verde { background-color: rgba(0,255,0,0.1); border: 1px solid #00ff00; color: #00ff00; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 12px; }
.alerta-azul { background-color: rgba(0,153,255,0.1); border: 1px solid #0099ff; color: #0099ff; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 12px; }
.alerta-amarelo { background-color: rgba(255,102,0,0.1); border: 1px solid #ff6600; color: #ff6600; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 12px; }
.sniper-titulo { font-size: 13px; font-weight: bold; color: #fff; margin-bottom: 8px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 5px; background-color: rgba(0,0,0,0.5); }
.sniper-dado { font-size: 12px; color: #ccc; margin: 6px 0; }
.sniper-valor { font-weight: bold; font-size: 15px; color: #fff; }
</style>
""", unsafe_allow_html=True)

def aplicar_estilos_ui(cor_neon):
    st.markdown(f"""
    <style>
        .titulo-container {{ display: flex; align-items: center; gap: 15px; margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px;}}
        .titulo-texto {{ margin: 0; font-size: 34px; font-weight: bold; color: #ffffff; }}
        .quantum-container {{ --uib-size: 40px; --uib-speed: 1.75s; position: relative; height: var(--uib-size); width: var(--uib-size); animation: q-rotate 7s linear infinite; }}
        @keyframes q-rotate {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        .q-particle {{ position: absolute; height: 100%; width: 100%; }}
        .q-particle::before {{ content: ''; position: absolute; height: 17%; width: 17%; border-radius: 50%; background-color: {cor_neon}; box-shadow: 0 0 10px {cor_neon}; animation: q-orbit var(--uib-speed) linear infinite; }}
        @keyframes q-orbit {{ 0% {{ transform: translate(20px); }} 50% {{ transform: translate(-20px); }} 100% {{ transform: translate(20px); }} }}
    </style>
    """, unsafe_allow_html=True)

def configurar_ui_pagina(titulo, cor):
    aplicar_estilos_ui(cor)
    st.markdown(f"""
    <div class="titulo-container">
        <div class="quantum-container"><div class="q-particle"></div></div>
        <h1 class="titulo-texto">{titulo}</h1>
    </div>
    """, unsafe_allow_html=True)

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

COLUNAS_DF = ["P1", "P2", "P3", "P4", "P5"]
TITULOS_PREMIOS = ["1º PRÊMIO", "2º PRÊMIO", "3º PRÊMIO", "4º PRÊMIO", "5º PRÊMIO"]

def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds).open("CentralBichos")
    except: return None

@st.cache_data(ttl=600, show_spinner=False)
def carregar_dados_em_memoria(banca_nome):
    sh = conectar_sheets()
    if not sh: return pd.DataFrame()
    try:
        ws = sh.worksheet(MAPA_ABAS[banca_nome])
        dados = ws.get_all_values()
        if len(dados) < 2: return pd.DataFrame()
        df = pd.DataFrame(dados[1:])
        df = df.iloc[:, :7]
        df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
        df = df[df["P1"].astype(str).str.strip() != ""]
        return df
    except: return pd.DataFrame()

def exibir_banner_sorteio(df, banca):
    if not df.empty:
        ult_nome = str(df.iloc[-1]["Sorteio"])
        st.markdown(f"""
        <div style="background-color: #0e1117; border: 1px solid #4CAF50; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
            <span style='color: #4CAF50; font-size: 11px; font-weight: bold;'>📡 ÚLTIMA ATUALIZAÇÃO LIDA DA PLANILHA:</span><br>
            <span style='color: white; font-size: 18px; font-weight: bold;'>{banca} - {ult_nome}</span>
        </div>
        """, unsafe_allow_html=True)

def get_grupo_int(m):
    try:
        d = int(str(m)[-2:])
        return 25 if d == 0 else math.ceil(d/4)
    except: return None

# =============================================================================
# 🐺 NOVO MOTOR: CAÇA 9D POR ANOMALIA (EXCLUSÃO DE DÍGITO FRIO)
# =============================================================================
def processar_caca_9d_anomalia(df, coluna):
    valores = df[coluna].astype(str).tolist()
    validos = []
    
    # Filtrar apenas dados válidos
    for val in valores:
        m = val.strip().zfill(4)
        if m != "----" and m != "0nan" and m != "nan" and m.strip():
            try:
                _ = int(m)
                validos.append(m)
            except: pass
            
    if len(validos) < 2: return None
    
    # Analisar os dois últimos sorteios (O Gatilho)
    c1 = validos[-1][-3:] # Centena do sorteio mais recente
    c2 = validos[-2][-3:] # Centena do penúltimo sorteio
    
    # Se a centena tiver menos que 3 dígitos únicos, significa que houve duplicação ou triplicação
    if len(set(c1)) < 3 and len(set(c2)) < 3:
        seen_digits = set()
        cold_digit = None
        
        # Rastreio reverso: lendo de baixo para cima
        for val in reversed(validos):
            centena = val[-3:]
            for char in centena:
                d = int(char)
                if d not in seen_digits:
                    seen_digits.add(d)
                    if len(seen_digits) == 9:
                        # Achamos os 9 primeiros dígitos a aparecer. O que sobrou é o dígito frio!
                        cold_digit = (set(range(10)) - seen_digits).pop()
                        break
            if cold_digit is not None:
                break
                
        if cold_digit is not None:
            # Formação de Ataque (Decrescente)
            seq = [str((cold_digit - i) % 10) for i in range(9)]
            seq_str = " - ".join(seq)
            excluido = (cold_digit + 1) % 10 # O excluído é sempre o vizinho posterior
            
            return cold_digit, seq_str, excluido
            
    return None

# =============================================================================
# 👻 MOTORES DE CÁLCULO E HEDGE 
# =============================================================================
def gerar_matrizes_taticas():
    esquadroes = []
    cms = []
    cms.append({'c_min': 0, 'c_max': 499, 'm_min': 0, 'm_max': 4999})
    cms.append({'c_min': 500, 'c_max': 999, 'm_min': 5000, 'm_max': 9999})
    
    for cm in cms:
        for g in range(1, 14):
            alvos = set(range(g, g + 13))
            esquadroes.append({'alvos': alvos, 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G13: {str(g).zfill(2)}-{str(g+12).zfill(2)}", 'lim': 9, **cm})
        
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
    
    cur_p, cur_c, cur_m = 0, 0, 0
    max_p, max_c, max_m = 0, 0, 0
    
    valores = df_analise[coluna].astype(str).tolist()
    
    for val in valores:
        milhar = val.strip().zfill(4)
        if milhar == "----" or milhar == "0nan" or milhar == "nan" or not milhar: continue
            
        try:
            m = int(milhar)
            c = int(milhar[-3:])
            d = int(milhar[-2:])
            u = int(milhar[-1:])
        except: continue
        
        g = 25 if d == 0 else math.ceil(d/4)
        
        hit_p = False
        if modo == 'grupo' and g in alvos: hit_p = True
        elif modo == 'dezena' and d in alvos: hit_p = True
        elif modo == 'unidade' and u in alvos: hit_p = True
        elif modo == 'centena' and c in alvos: hit_p = True
        elif modo == 'milhar' and m in alvos: hit_p = True 
        
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

def deduplicar_alvos(lista):
    vistos = set(); resultado = []
    for item in lista:
        ta = item.get('tipo_ataque', '')
        if "MILHAR" in ta: 
            sig = f"{item['banca']}_{item['premio']}_M_{item['cfg']['m_min']}"
        elif "CENTENA" in ta: 
            sig = f"{item['banca']}_{item['premio']}_C_{item['cfg']['c_min']}"
        else: 
            sig = f"{item['banca']}_{item['premio']}_{item['cfg']['nome']}"
        
        if sig not in vistos:
            vistos.add(sig); resultado.append(item)
    return resultado

def get_hedge_grupos(df, col, cfg_matriz, col_delays):
    grupos = list(cfg_matriz['alvos'])
    scores = {g: 0 for g in grupos}
    mass_max = max([col_delays.get('G: ÍMPARES', 0), col_delays.get('G: PARES', 0), col_delays.get('D: ALTAS (51-00)', 0), col_delays.get('D: BAIXAS (01-50)', 0)])

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
        uni_max = max([col_delays.get('U: ÍMPARES', 0), col_delays.get('U: PARES', 0), col_delays.get('U: ALTAS (6-0)', 0), col_delays.get('U: BAIXAS (1-5)', 0)])
        if uni_max >= 3:
            if col_delays.get('U: ÍMPARES', 0) >= 3:
                for g in grupos:
                    if (g % 10) % 2 == 0: scores[g] += 1
            if col_delays.get('U: PARES', 0) >= 3:
                for g in grupos:
                    if (g % 10) % 2 != 0: scores[g] += 1

    sorted_g = sorted(grupos, key=lambda x: scores[x], reverse=True)
    eliminar = [g for g in sorted_g[:2] if scores[g] > 0] 

    if not eliminar: return None 

    seguro = {}
    valores = df[col].astype(str).tolist()
    
    for g in eliminar:
        dezenas = [g*4 - 3, g*4 - 2, g*4 - 1, g*4]
        if g == 25: dezenas = [97, 98, 99, 0]
        max_d_delay = -1; best_d = -1
        
        for d in dezenas:
            delay_d = 0
            for val in reversed(valores):
                m = val.strip().zfill(4)
                if m == "----" or m == "0nan" or m == "nan": continue
                try: dez_val = int(m[-2:])
                except: dez_val = -1
                if dez_val == d: break
                delay_d += 1
            if delay_d > max_d_delay: max_d_delay = delay_d; best_d = d
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
        "U: ÍMPARES": ("Grupo Par", [2,4,6,8,10,12,14,16,18,20,22,24])
    }
    if cfg_nome not in opostos: return None
        
    desc_oposto, lista_grupos = opostos[cfg_nome]
    max_delay = -1; best_g = -1
    valores = df[col].astype(str).tolist()
    
    for g in lista_grupos:
        delay_g = 0
        for val in reversed(valores):
            m = val.strip().zfill(4)
            if m == "----" or m == "0nan" or m == "nan": continue
            try: d = int(m[-2:])
            except: continue
            g_val = 25 if d == 0 else math.ceil(d/4)
            if g_val == g: break
            delay_g += 1
        if delay_g > max_delay: max_delay = delay_g; best_g = g
            
    return best_g, max_delay, desc_oposto

def direcao_pendulo(prev, curr):
    if prev == curr: return "="
    dist_c = (curr - prev) % 25
    dist_d = (prev - curr) % 25
    if 1 <= dist_c <= 6: return "C"; 
    if 1 <= dist_d <= 6: return "D"; 
    return "-" 

def processar_pendulo(df, coluna):
    all_groups = []
    valores = df[coluna].astype(str).tolist()
    for val in valores:
        m = val.strip().zfill(4)
        if m != "----" and m != "0nan" and m != "nan" and m.strip():
            try:
                d = int(m[-2:])
                g = 25 if d == 0 else math.ceil(d/4)
                all_groups.append(g)
            except: pass
                
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
            
    max_streak = 0; temp_streak = 0; temp_dir = None
    for d in dirs_history:
        if d in ["C", "D"]:
            if d == temp_dir: temp_streak += 1
            else: temp_dir = d; temp_streak = 1
            if temp_streak > max_streak: max_streak = temp_streak
        else:
            temp_dir = None; temp_streak = 0
            
    dirs = dirs_history[-5:] 
    last_g = all_groups[-1]
    
    if curr_streak >= 5:
        if curr_streak == 5: status = "🚨 SATURAÇÃO ALTA"
        elif curr_streak == 6: status = "🔥 SATURAÇÃO EXTREMA"
        else: status = f"☢️ SATURAÇÃO CRÍTICA"
        
        jogos = []; curr = last_g
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
        return status, jogos, all_groups[-6:], dirs, curr_streak, max_streak, curr_dir
        
    return "Estável", [], all_groups[-6:], dirs, curr_streak, max_streak, curr_dir

def extrair_dia(banca, data_alvo):
    url = f"{BANCAS_CONFIG[banca]}{data_alvo.strftime('%Y-%m-%d')}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        tabelas = soup.find_all('table')
        resultados = []
        vistos_assinaturas = set()
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
                assinatura = "".join(milhares)
                if assinatura not in vistos_assinaturas and milhares[0] != "----":
                    vistos_assinaturas.add(assinatura)
                    resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

# =============================================================================
# --- INTERFACE ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=60)
    st.header("Pentágono V65.34")
    if st.button("FORÇAR ATUALIZAÇÃO", type="primary"):
        st.cache_data.clear()
        st.success("✅ Memória do radar limpa!")
    menu = st.radio("Selecione Tática:", ["🏠 Visão Geral (Home)", "🎯 Scanner de Raio-X", "🧲 Armadilha do Pêndulo", "📡 Extração Central"])

if menu == "🏠 Visão Geral (Home)":
    configurar_ui_pagina("Central AWACS", "#00ffff")
    
    if st.button("INICIAR VARREDURA GLOBAL", type="primary"):
        with st.spinner("Processando histórico e escaneando anomalias..."):
            alvos_teto = []
            alvos_alerta = []
            alertas_pendulo = []
            alertas_caca_9d = [] # NOVO: Lista para a Caça 9D
            todos_esq = gerar_matrizes_taticas()
            
            for banca_nome in BANCAS_CONFIG.keys():
                df = carregar_dados_em_memoria(banca_nome)
                if df.empty: continue
                ultimo_sorteio = str(df.iloc[-1]["Sorteio"])
                
                for i, col in enumerate(COLUNAS_DF):
                    if banca_nome == "Tradicional" and col != "P1": continue
                    
                    # 1. PÊNDULO
                    resultado_pend = processar_pendulo(df, col)
                    if resultado_pend:
                        status, jogos, draws, dirs, curr_streak, max_streak, curr_dir = resultado_pend
                        if status != "Estável":
                            alertas_pendulo.append({"banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "status": status, "jogos": jogos, "draws": draws, "dirs": dirs, "curr_streak": curr_streak, "max_streak": max_streak, "curr_dir": curr_dir})
                    
                    # 2. CAÇA 9D POR ANOMALIA (GATILHO IMEDIATO)
                    resultado_9d = processar_caca_9d_anomalia(df, col)
                    if resultado_9d:
                        cold_digit, seq_str, excluido = resultado_9d
                        alertas_caca_9d.append({"banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "cold_digit": cold_digit, "seq": seq_str, "excluido": excluido})

                metrics_cache = {}
                for cfg in todos_esq:
                    for i, col in enumerate(COLUNAS_DF):
                        if banca_nome == "Tradicional" and col != "P1": continue
                        ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        metrics_cache[(cfg['nome'], cfg['c_min'], col)] = (ap, ac, am, mp, mc, mm)
                
                for cfg in todos_esq:
                    for i, col in enumerate(COLUNAS_DF):
                        if banca_nome == "Tradicional" and col != "P1": continue
                        ap, ac, am, mp, mc, mm = metrics_cache[(cfg['nome'], cfg['c_min'], col)]
                        ap_lim = cfg['lim'] 
                        
                        estado_alvo = None; prio = 99; tipo_ataque = ""; alerta_html = ""
                        
                        if am >= 9 and ac >= 9 and ap >= ap_lim: estado_alvo = "TETO"; prio = 1; tipo_ataque = "TOTAL"; alerta_html = "<div class='alerta-verde'>🔥 ATAQUE TOTAL (G+C+M) - TETO ATINGIDO</div>"
                        elif am >= 9: estado_alvo = "TETO"; prio = 2; tipo_ataque = "MILHAR"; alerta_html = f"<div class='alerta-verde'>🔵 ATAQUE MILHAR ({am}x) - TETO ATINGIDO</div>"
                        elif ac >= 9: estado_alvo = "TETO"; prio = 3; tipo_ataque = "CENTENA"; alerta_html = f"<div class='alerta-verde'>🟢 ATAQUE CENTENA ({ac}x) - TETO ATINGIDO</div>"
                        elif cfg['modo'] == 'unidade' and ap >= 9: estado_alvo = "TETO"; prio = 4; tipo_ataque = "UNIDADE"; alerta_html = "<div class='alerta-verde'>🔥 ATAQUE UNIDADE - TETO ATINGIDO</div>"
                        elif ap >= ap_lim: estado_alvo = "TETO"; prio = 5; tipo_ataque = "ALVO_PRINCIPAL"; alerta_html = f"<div class='alerta-verde'>🟢 ATAQUE FORTE ({cfg['modo'].upper()}) - TETO ATINGIDO</div>"
                        elif am >= 7 and ac >= 7 and ap >= (ap_lim - 2): estado_alvo = "ALERTA"; prio = 6; tipo_ataque = "TOTAL"; alerta_html = f"<div class='alerta-amarelo'>🟠 ALERTA: APROXIMAÇÃO DE TETO TOTAL</div>"
                        elif am >= 7: estado_alvo = "ALERTA"; prio = 7; tipo_ataque = "MILHAR"; alerta_html = f"<div class='alerta-amarelo'>🟠 ALERTA: MILHAR PRÓXIMO AO TETO ({am}/9)</div>"
                        elif ac >= 7: estado_alvo = "ALERTA"; prio = 8; tipo_ataque = "CENTENA"; alerta_html = f"<div class='alerta-amarelo'>🟠 ALERTA: CENTENA PRÓXIMA AO TETO ({ac}/9)</div>"
                        elif cfg['modo'] == 'unidade' and ap >= 7: estado_alvo = "ALERTA"; prio = 9; tipo_ataque = "UNIDADE"; alerta_html = f"<div class='alerta-amarelo'>🟠 ALERTA: UNIDADE PRÓXIMA AO TETO ({ap}/9)</div>"
                        elif ap >= (ap_lim - 2): estado_alvo = "ALERTA"; prio = 10; tipo_ataque = "ALVO_PRINCIPAL"; alerta_html = f"<div class='alerta-amarelo'>🟠 ALERTA: {cfg['modo'].upper()} PRÓXIMO AO TETO ({ap}/{ap_lim})</div>"

                        if estado_alvo:
                            if estado_alvo == "TETO":
                                teto_alvo = 9 if tipo_ataque in ["MILHAR", "CENTENA", "TOTAL"] else ap_lim
                                recorde_alvo = mp
                                if tipo_ataque == "MILHAR": recorde_alvo = mm
                                elif tipo_ataque == "CENTENA": recorde_alvo = mc
                                elif tipo_ataque == "TOTAL": recorde_alvo = max(mp, mc, mm)
                                
                                if recorde_alvo > teto_alvo + 2:
                                    espera_sugerida = teto_alvo + 2
                                    alerta_html += f"<div style='background:rgba(255,0,0,0.1); border:1px solid #ff0000; color:#ff0000; padding:6px; border-radius:5px; font-weight:bold; margin-top:8px; font-size:11px;'>🚨 PERIGO DE ANOMALIA:<br>Recorde Histórico é {recorde_alvo}x. Risco de quebra de Martingale. Sugestão: Aguarde o atraso chegar a {espera_sugerida}x ou aplique gestão mínima.</div>"
                            
                            if cfg['modo'] == 'grupo' and cfg['tipo'] == 'seq':
                                col_delays = {k_name: val[0] for (k_name, k_col, k_cm), val in metrics_cache.items() if k_col == col and k_cm == cfg['c_min']}
                                hedge_data = get_hedge_grupos(df, col, cfg, col_delays)
                                if hedge_data:
                                    elim_str = ", ".join([str(x).zfill(2) for x in hedge_data['eliminar']])
                                    mant_str = ", ".join([str(x).zfill(2) for x in hedge_data['manter']])
                                    seg_list = [f"Dez {str(d).zfill(2)} ({delay}x)" for g, (d, delay) in hedge_data['seguro'].items()]
                                    alerta_html += f"<div style='background:rgba(255,255,255,0.05); padding:6px; margin-top:8px;'>🛡️ Cortar: G {elim_str} | Jogar: {mant_str}</div>"
                            else:
                                cob_data = get_cobertura_massa(df, col, cfg['nome'])
                                if cob_data:
                                    g_alvo, delay_g, desc_oposto = cob_data
                                    alerta_html += f"<div style='background:rgba(255,255,255,0.05); padding:6px; margin-top:8px;'>🛡️ Cobertura: O {desc_oposto} mais perigoso é o <b>G{str(g_alvo).zfill(2)}</b> ({delay_g}x).</div>"

                            op_data = {"prio": prio, "banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "ap": ap, "ac": ac, "am": am, "mp": mp, "mc": mc, "mm": mm, "alerta": alerta_html, "cfg": cfg, "tipo_ataque": tipo_ataque}
                            if estado_alvo == "TETO": alvos_teto.append(op_data)
                            elif estado_alvo == "ALERTA": alvos_alerta.append(op_data)
            
        alvos_teto = deduplicar_alvos(sorted(alvos_teto, key=lambda x: (x['prio'], -max(x['ap'], x['ac'], x['am']))))
        alvos_alerta = deduplicar_alvos(sorted(alvos_alerta, key=lambda x: (x['prio'], -max(x['ap'], x['ac'], x['am']))))
        
        # --- RENDERIZAÇÃO DA CAÇA 9D POR ANOMALIA ---
        if alertas_caca_9d:
            st.error(f"🐺 CAÇA 9D ANOMALIA (GATILHO IMEDIATO): {len(alertas_caca_9d)} Encontrados!")
            cols = st.columns(3)
            for idx, op in enumerate(alertas_caca_9d):
                with cols[idx % 3]:
                    st.markdown(f"""
                    <div class="home-box" style="border-color:#ff4b4b; box-shadow: 0 0 15px rgba(255,0,0,0.4);">
                        <div class="home-banca">🏦 {op['banca']}</div>
                        <div class="home-premio">🏆 {op['premio']}</div>
                        <div class="sniper-titulo" style="color:#ff4b4b;">🐺 GATILHO DUPLO DETECTADO</div>
                        <div class="sniper-dado">Dígito Frio (Base): <b style='color:#fff; font-size:16px;'>{op['cold_digit']}</b></div>
                        <div class="sniper-dado" style="margin-top:5px;"><b>Sequência de Ataque 9D:</b></div>
                        <div class="sniper-valor" style="color:#00ff00; font-size:18px;">{op['seq']}</div>
                        <div style="font-size:12px; color:#ff4b4b; margin-top:8px; font-weight:bold;">❌ Excluir Dígito: {op['excluido']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown("---") 

        # --- RENDERIZAÇÃO DOS OUTROS ALVOS ---
        if alvos_teto:
            st.success(f"🎯 ALVOS CRÍTICOS (TETO ATINGIDO): {len(alvos_teto)} Encontrados!")
            cols = st.columns(3)
            for idx, op in enumerate(alvos_teto):
                c_min, c_max, m_min, m_max = op['cfg']['c_min'], op['cfg']['c_max'], op['cfg']['m_min'], op['cfg']['m_max']
                ta = op.get('tipo_ataque', '')
                css_class = f"home-box-seq"
                
                if ta == 'UNIDADE': lbl_alvo, titulo, cm_html = "Unidade", op['cfg']['nome'], ""
                elif ta == 'MILHAR': lbl_alvo, titulo, cm_html = "Filtro", f"M: {str(m_min).zfill(4)} A {str(m_max).zfill(4)}", f"Centena: {op['ac']}x | Milhar: {op['am']}x"
                elif ta == 'CENTENA': lbl_alvo, titulo, cm_html = "Filtro", f"C: {str(c_min).zfill(3)} A {str(c_max).zfill(3)}", f"Centena: {op['ac']}x | Milhar: {op['am']}x"
                else: lbl_alvo, titulo, cm_html = "Atraso", op['cfg']['nome'], f"Centena: {op['ac']}x | Milhar: {op['am']}x"
                    
                with cols[idx % 3]:
                    st.markdown(f"""<div class="home-box {css_class}"><div class="home-banca">🏦 {op['banca']}</div><div class="home-premio">🏆 {op['premio']}</div><div class="sniper-titulo">{titulo}</div><div class="sniper-valor" style="color:#00ff00;">{op['ap']}x</div><div style="font-size:11px; color:#aaa;">{cm_html}</div>{op['alerta']}</div>""", unsafe_allow_html=True)
            st.markdown("---") 

        if alvos_alerta:
            st.warning(f"🟠 ALERTA DE APROXIMAÇÃO (FALTAM 1 OU 2 PONTOS): {len(alvos_alerta)} Encontrados!")
            cols = st.columns(3)
            for idx, op in enumerate(alvos_alerta):
                c_min, c_max, m_min, m_max = op['cfg']['c_min'], op['cfg']['c_max'], op['cfg']['m_min'], op['cfg']['m_max']
                ta = op.get('tipo_ataque', '')
                css_class = f"home-box-seq"
                
                if ta == 'UNIDADE': lbl_alvo, titulo, cm_html = "Unidade", op['cfg']['nome'], ""
                elif ta == 'MILHAR': lbl_alvo, titulo, cm_html = "Filtro", f"M: {str(m_min).zfill(4)} A {str(m_max).zfill(4)}", f"Centena: {op['ac']}x | Milhar: {op['am']}x"
                elif ta == 'CENTENA': lbl_alvo, titulo, cm_html = "Filtro", f"C: {str(c_min).zfill(3)} A {str(c_max).zfill(3)}", f"Centena: {op['ac']}x | Milhar: {op['am']}x"
                else: lbl_alvo, titulo, cm_html = "Atraso", op['cfg']['nome'], f"Centena: {op['ac']}x | Milhar: {op['am']}x"
                    
                with cols[idx % 3]:
                    st.markdown(f"""<div class="home-box {css_class}"><div class="home-banca">🏦 {op['banca']}</div><div class="home-premio">🏆 {op['premio']}</div><div class="sniper-titulo">{titulo}</div><div class="sniper-valor" style="color:#ff6600;">{op['ap']}x</div><div style="font-size:11px; color:#aaa;">{cm_html}</div>{op['alerta']}</div>""", unsafe_allow_html=True)

        if not alvos_teto and not alvos_alerta and not alertas_pendulo and not alertas_caca_9d: 
            st.success("🟢 MODO STEALTH: Não temos alvos no teto ou próximos a ele no momento. Mercado estável.")

elif menu == "🎯 Scanner de Raio-X":
    configurar_ui_pagina("Scanner de Raio-X", "#ffcc00")
    col1, col2, col3 = st.columns(3)
    with col1: banca_rx = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    with col2: categoria_rx = st.selectbox("Categoria:", ["Grupo (1 a 25)", "Dezena (00 a 99)", "Unidade (0 a 9)", "Filtros de Massa"])
    with col3:
        if categoria_rx == "Grupo (1 a 25)": alvo_rx = st.number_input("Qual?", min_value=1, max_value=25, value=1)
        elif categoria_rx == "Dezena (00 a 99)": alvo_rx = st.number_input("Qual?", min_value=0, max_value=99, value=0)
        elif categoria_rx == "Unidade (0 a 9)": alvo_rx = st.number_input("Qual?", min_value=0, max_value=9, value=0)
            
    if categoria_rx != "Filtros de Massa":
        if st.button("EXECUTAR RAIO-X INDIVIDUAL", type="primary"):
            df = carregar_dados_em_memoria(banca_rx)
            if df.empty: st.error("Sem dados.")
            else:
                exibir_banner_sorteio(df, banca_rx)
                cfg_rx = {'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999, 'lim': 0}
                if categoria_rx == "Grupo (1 a 25)": cfg_rx['alvos'] = {int(alvo_rx)}; cfg_rx['modo'] = 'grupo'; cfg_rx['nome'] = f"GRUPO {str(alvo_rx).zfill(2)}"
                elif categoria_rx == "Dezena (00 a 99)": cfg_rx['alvos'] = {int(alvo_rx)}; cfg_rx['modo'] = 'dezena'; cfg_rx['nome'] = f"DEZENA {str(alvo_rx).zfill(2)}"
                elif categoria_rx == "Unidade (0 a 9)": cfg_rx['alvos'] = {int(alvo_rx)}; cfg_rx['modo'] = 'unidade'; cfg_rx['nome'] = f"UNIDADE {alvo_rx}"
                
                cols_rx = st.columns(5)
                for i, col in enumerate(COLUNAS_DF):
                    ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg_rx)
                    with cols_rx[i]:
                        st.markdown(f"""<div class="home-box"><div class="home-premio">🏆 {TITULOS_PREMIOS[i]}</div><div class="sniper-valor" style="color:#ff4b4b;">{ap}x</div><div>Rec: {mp}x</div></div>""", unsafe_allow_html=True)
    else:
        if st.button("GERAR PLANILHA DE MASSA", type="primary"):
            df = carregar_dados_em_memoria(banca_rx)
            if df.empty: st.error("Sem dados.")
            else:
                filtros_lista = [
                    ("Milhares Baixas (0000-4999)", {'alvos': set(range(0, 5000)), 'modo': 'milhar', 'lim': 9}),
                    ("Milhares Altas (5000-9999)", {'alvos': set(range(5000, 10000)), 'modo': 'milhar', 'lim': 9}),
                    ("Centenas Baixas (000-499)", {'alvos': set(range(0, 500)), 'modo': 'centena', 'lim': 9}),
                    ("Centenas Altas (500-999)", {'alvos': set(range(500, 1000)), 'modo': 'centena', 'lim': 9}),
                    ("Grupos Ímpares", {'alvos': set(range(1, 26, 2)), 'modo': 'grupo', 'lim': 9}),
                    ("Grupos Pares", {'alvos': set(range(2, 26, 2)), 'modo': 'grupo', 'lim': 9}),
                    ("Dezenas Baixas (01-50)", {'alvos': set(range(1, 51)), 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Altas (51-00)", {'alvos': set(range(51, 100)) | {0}, 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Ímpares", {'alvos': {x for x in range(100) if x % 2 != 0}, 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Pares", {'alvos': {x for x in range(100) if x % 2 == 0}, 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Miolo (26-75)", {'alvos': set(range(26, 76)), 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Bordas", {'alvos': set(range(1, 26)) | set(range(76, 100)) | {0}, 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Finais Baixos (1-5)", {'alvos': {x for x in range(100) if x % 10 in [1, 2, 3, 4, 5]}, 'modo': 'dezena', 'lim': 9}),
                    ("Dezenas Finais Altos (6-0)", {'alvos': {x for x in range(100) if x % 10 in [6, 7, 8, 9, 0]}, 'modo': 'dezena', 'lim': 9}),
                    ("Unidades Baixas (1-5)", {'alvos': {1, 2, 3, 4, 5}, 'modo': 'unidade', 'lim': 9}),
                    ("Unidades Altas (6-0)", {'alvos': {6, 7, 8, 9, 0}, 'modo': 'unidade', 'lim': 9}),
                    ("Unidades Ímpares", {'alvos': {1, 3, 5, 7, 9}, 'modo': 'unidade', 'lim': 9}),
                    ("Unidades Pares", {'alvos': {0, 2, 4, 6, 8}, 'modo': 'unidade', 'lim': 9})
                ]
                bases_inv_8 = [[0,1,2,3,4,5,6,7], [1,2,3,4,5,6,7,8], [2,3,4,5,6,7,8,9], [3,4,5,6,7,8,9,0], [4,5,6,7,8,9,0,1], [5,6,7,8,9,0,1,2], [6,7,8,9,0,1,2,3], [7,8,9,0,1,2,3,4], [8,9,0,1,2,3,4,5], [9,0,1,2,3,4,5,6]]
                for b in bases_inv_8: filtros_lista.append((f"INV 8D ({b[0]} ao {b[-1]})", {'alvos': {int(f"{d1}{d2}") for d1 in b for d2 in b if d1 != d2}, 'modo': 'dezena', 'lim': 10}))
                bases_inv_9 = [[0,1,2,3,4,5,6,7,8], [1,2,3,4,5,6,7,8,9], [2,3,4,5,6,7,8,9,0], [3,4,5,6,7,8,9,0,1], [4,5,6,7,8,9,0,1,2], [5,6,7,8,9,0,1,2,3], [6,7,8,9,0,1,2,3,4], [7,8,9,0,1,2,3,4,5], [8,9,0,1,2,3,4,5,6], [9,0,1,2,3,4,5,6,7]]
                for b in bases_inv_9: filtros_lista.append((f"INV 9D ({b[0]} ao {b[-1]})", {'alvos': {int(f"{d1}{d2}{d3}") for d1 in b for d2 in b for d3 in b if d1 != d2 and d2 != d3 and d1 != d3}, 'modo': 'centena', 'lim': 10}))
                
                dados_tabela = []
                for nome_filtro, cfg in filtros_lista:
                    cfg.update({'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999})
                    linha = {"FILTRO": nome_filtro, "TETO": cfg['lim']}
                    for i, col in enumerate(COLUNAS_DF):
                        ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        linha[TITULOS_PREMIOS[i]] = f"{ap}x (R:{mp})"
                    dados_tabela.append(linha)
                
                exibir_banner_sorteio(df, banca_rx)
                st.dataframe(pd.DataFrame(dados_tabela), use_container_width=True, hide_index=True)

elif menu == "🧲 Armadilha do Pêndulo":
    configurar_ui_pagina("Armadilha do Pêndulo", "#ff00aa")
    banca_pendulo = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    if st.button("ANALISAR MOMENTUM CIRCULAR", type="primary"):
        df = carregar_dados_em_memoria(banca_pendulo)
        if df.empty: st.error("Sem dados.")
        else:
            exibir_banner_sorteio(df, banca_pendulo)
            cols = st.columns(5)
            for i, col in enumerate(COLUNAS_DF):
                resultado = processar_pendulo(df, col)
                with cols[i]:
                    if resultado:
                        status, jogos, draws, dirs, curr_streak, max_streak, curr_dir = resultado
                        setas = ["➡️" if d == "C" else "⬅️" if d == "D" else "⏸️" if d == "=" else "✖️" for d in dirs]
                        seq_visual = f"<span style='font-size:16px;'>{str(draws[0]).zfill(2)}</span> {setas[0]} <span style='font-size:16px;'>{str(draws[1]).zfill(2)}</span> {setas[1]} <span style='font-size:16px;'>{str(draws[2]).zfill(2)}</span> {setas[2]} <span style='font-size:16px;'>{str(draws[3]).zfill(2)}</span> {setas[3]} <span style='font-size:16px;'>{str(draws[4]).zfill(2)}</span> {setas[4]} <span style='font-size:16px; color:#ff4b4b;'>{str(draws[5]).zfill(2)}</span>"
                        cor_box = "#ff00aa" if curr_dir == "C" else "#00ffff"
                        st.markdown(f"""<div class="home-box" style="border-color:{cor_box};"><div class="home-premio">🏆 {TITULOS_PREMIOS[i]}</div><div class="sniper-dado">{seq_visual}</div><div class="sniper-dado">Saturação: {curr_streak}x (Rec: {max_streak})</div><div style="color:{cor_box}; font-weight:bold; font-size:11px;">{status}</div><div style="font-size:10px; color:#fff; margin-top:5px;">Alvos: {', '.join(jogos)}</div></div>""", unsafe_allow_html=True)
                    else: st.write("Dados insuficientes.")

elif menu == "📡 Extração Central":
    configurar_ui_pagina("Extração Central", "#00ff00")
    dt = st.date_input("Data:", value=date.today())
    col1, col2 = st.columns(2)
    with col1:
        banca_ex = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
        if st.button("COLETA INDIVIDUAL", type="primary"):
            res = extrair_dia(banca_ex, dt)
            if res:
                sh = conectar_sheets()
                ws = sh.worksheet(MAPA_ABAS[banca_ex])
                existentes = ws.get_all_values()
                set_exist = {f"{str(r[0]).strip()}_{''.join(str(x).strip() for x in r[2:7])}" for r in existentes if len(r) >= 7}
                p_ins = [l for l in res if f"{str(l[0]).strip()}_{''.join(str(x).strip() for x in l[2:7])}" not in set_exist]
                if p_ins: ws.append_rows(p_ins, value_input_option="RAW"); st.success(f"✅ {len(p_ins)} novos registros salvos."); st.cache_data.clear() 
                else: st.info("Base de dados já atualizada. Nenhum resultado novo encontrado.")
            else: st.error("Sem dados para extrair hoje nesta banca.")
    with col2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if st.button("EXTRAÇÃO GLOBAL", type="primary"):
            painel_status = st.empty()
            painel_status.info("Varrendo servidores da web e validando assinaturas genéticas... Aguarde.")
            
            sh = conectar_sheets()
            if not sh: 
                painel_status.error("Erro Crítico de Conexão com o Google Sheets.")
            else:
                total_salvos = 0
                bancas_atualizadas = []
                for banca_alvo in BANCAS_CONFIG.keys():
                    res = extrair_dia(banca_alvo, dt)
                    if res:
                        ws = sh.worksheet(MAPA_ABAS[banca_alvo])
                        existentes = ws.get_all_values()
                        set_exist = {f"{str(r[0]).strip()}_{''.join(str(x).strip() for x in r[2:7])}" for r in existentes if len(r) >= 7}
                        p_ins = [l for l in res if f"{str(l[0]).strip()}_{''.join(str(x).strip() for x in l[2:7])}" not in set_exist]
                        if p_ins: 
                            ws.append_rows(p_ins, value_input_option="RAW")
                            total_salvos += len(p_ins)
                            bancas_atualizadas.append(f"✅ **{banca_alvo}:** {len(p_ins)} novos registros inseridos.")
                        else: 
                            bancas_atualizadas.append(f"ℹ️ **{banca_alvo}:** Base já está atualizada (0 novos).")
                    else: 
                        bancas_atualizadas.append(f"⚠️ **{banca_alvo}:** Nenhum dado encontrado no site para hoje.")
                
                painel_status.empty() 
                
                st.markdown("### 📊 Relatório de Extração:")
                for b_msg in bancas_atualizadas:
                    st.markdown(b_msg)
                    
                if total_salvos > 0: 
                    st.cache_data.clear()
                    st.success(f"🎯 EXTRAÇÃO GLOBAL CONCLUÍDA! Total de {total_salvos} novos registros.")
                else: 
                    st.info("🔄 EXTRAÇÃO GLOBAL CONCLUÍDA! Nenhum registro novo no momento.")

st.markdown("""<div class="rodape-tatico">🎯 GATILHOS: M/C Baixas/Altas=9x | Dezenas, Unidades e Filtros=9x | 13 Grupos=9x | Inv 8D/9D=10x | Pêndulo=5x</div>""", unsafe_allow_html=True)
