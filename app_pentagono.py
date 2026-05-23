import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import itertools

# =============================================================================
# --- 1. CONFIGURAÇÕES, CSS E CONEXÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono V65.17 - Artilharia 9D", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.home-box { border-radius: 8px; padding: 12px; margin-bottom: 15px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.6); border: 1px solid; }
.home-box-seq { background-color: #111111; border-color: #444444; } 
.home-box-impar { background-color: #2a0a18; border-color: #ff0055; } 
.home-box-par { background-color: #0a1b2a; border-color: #00aaff; } 
.home-box-dez { background-color: #1a1f00; border-color: #ffcc00; } 
.home-box-uni { background-color: #2d001d; border-color: #ff00aa; } 
.home-box-lab { background-color: #001f3f; border-color: #00ffff; } 
.home-box-pendulo { background-color: #1a1a2e; border-color: #e94560; } 

.home-banca { font-size: 16px; font-weight: bold; color: #fff; margin-bottom: 2px; text-transform: uppercase; }
.home-horario { font-size: 11px; color: #aaa; margin-top: -2px; margin-bottom: 8px; font-weight: normal; }
.home-premio { font-size: 13px; color: #4CAF50; margin-bottom: 10px; font-weight: bold; }
.sniper-titulo { font-size: 12px; font-weight: bold; color: #fff; margin-bottom: 8px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 5px; background-color: rgba(0,0,0,0.5); border-radius: 4px; padding: 5px;}
.sniper-dado { font-size: 12px; color: #ccc; margin: 6px 0; line-height: 1.2; }
.sniper-valor { font-weight: bold; font-size: 14px; color: #fff; }
.banner-info { background-color: #0e1117; border: 1px solid #4CAF50; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px; }

.alerta-supremo { background-color: #330033; border: 1px solid #ff00ff; color: #ff00ff; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
.alerta-verde { background-color: #003300; border: 1px solid #00ff00; color: #00ff00; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
.alerta-azul { background-color: #001a33; border: 1px solid #0099ff; color: #0099ff; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }
.alerta-amarelo { background-color: rgba(0,0,0,0.5); border: 1px solid #ffcc00; color: #ffcc00; padding: 6px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 11px; }

.rodape-tatico {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    background-color: rgba(17, 17, 17, 0.95);
    color: #ffcc00;
    text-align: center;
    padding: 12px;
    font-size: 15px;
    font-weight: bold;
    border-top: 2px solid #ff4b4b;
    z-index: 9999;
}
.block-container { padding-bottom: 80px; }
</style>
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
        <div class="banner-info">
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
# 👻 MOTORES DE ANÁLISE E HEDGE (DESDOBRAMENTO)
# =============================================================================
def gerar_matrizes_taticas():
    esquadroes = []
    cms = []
    for c in range(7): cms.append({'c_min': c*100, 'c_max': c*100+399, 'm_min': c*1000, 'm_max': c*1000+3999})
    for cm in cms:
        # 15 Grupos e 12 Grupos
        for g in range(1, 12):
            alvos = set(range(g, g + 15))
            esquadroes.append({'alvos': alvos, 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G: {str(g).zfill(2)}-{str(g+14).zfill(2)}", 'lim': 7, **cm})
        for g in range(1, 15):
            alvos = set(range(g, g + 12))
            esquadroes.append({'alvos': alvos, 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G12: {str(g).zfill(2)}-{str(g+11).zfill(2)}", 'lim': 10, **cm})
        
        # Filtros e Dezenas (Teto 9)
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
        
        # INJEÇÃO: INVERSÃO 7 DÍGITOS (TETO 12x)
        bases_inv_7 = [[0,1,2,3,4,5,6], [1,2,3,4,5,6,7], [2,3,4,5,6,7,8], [3,4,5,6,7,8,9], [4,5,6,7,8,9,0], [5,6,7,8,9,0,1], [6,7,8,9,0,1,2], [7,8,9,0,1,2,3], [8,9,0,1,2,3,4], [9,0,1,2,3,4,5]]
        for b in bases_inv_7:
            alvos_inv = {int(f"{d1}{d2}") for d1 in b for d2 in b if d1 != d2}
            nome_inv = f"D: INV 7D ({b[0]} AO {b[-1]})"
            esquadroes.append({'alvos': alvos_inv, 'modo': 'dezena', 'tipo': 'dez', 'nome': nome_inv, 'lim': 12, **cm})

        # NOVA INJEÇÃO: INVERSÃO 9 DÍGITOS (CENTENAS - TETO 9x)
        bases_inv_9 = [[0,1,2,3,4,5,6,7,8], [1,2,3,4,5,6,7,8,9], [2,3,4,5,6,7,8,9,0], [3,4,5,6,7,8,9,0,1], [4,5,6,7,8,9,0,1,2], [5,6,7,8,9,0,1,2,3], [6,7,8,9,0,1,2,3,4], [7,8,9,0,1,2,3,4,5], [8,9,0,1,2,3,4,5,6], [9,0,1,2,3,4,5,6,7]]
        for b in bases_inv_9:
            alvos_inv_c = {int(f"{d1}{d2}{d3}") for d1 in b for d2 in b for d3 in b if d1 != d2 and d2 != d3 and d1 != d3}
            nome_inv_c = f"C: INV 9D ({b[0]} AO {b[-1]})"
            esquadroes.append({'alvos': alvos_inv_c, 'modo': 'centena', 'tipo': 'seq', 'nome': nome_inv_c, 'lim': 9, **cm})

    esquadroes_unidade = [
        {'alvos': {1, 2, 3, 4, 5}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: BAIXAS (1-5)", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {6, 7, 8, 9, 0}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ALTAS (6-0)", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {1, 3, 5, 7, 9}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ÍMPARES", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {0, 2, 4, 6, 8}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: PARES", 'lim': 9, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999}
    ]
    esquadroes.extend(esquadroes_unidade)
    return esquadroes

def calcular_metricas_fantasma(df_analise, coluna, cfg, janela=50):
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
        elif modo == 'centena' and c in alvos: hit_p = True # NOVO GATILHO CENTENA
        
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
    df_janela = df_analise.tail(janela)
    cur_p, cur_c, cur_m, max_p, max_c, max_m = 0, 0, 0, 0, 0, 0
    for i in range(len(df_janela)):
        milhar = str(df_janela.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "nan": continue
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:]); m = int(milhar); d = int(milhar[-2:]); u = int(milhar[-1:])
        except: c, m, d, u = -1, -1, -1, -1
        hit_p = False
        if modo == 'grupo' and g is not None and g in alvos: hit_p = True
        elif modo == 'dezena' and d in alvos: hit_p = True
        elif modo == 'unidade' and u in alvos: hit_p = True
        elif modo == 'centena' and c in alvos: hit_p = True # NOVO GATILHO CENTENA
        
        cur_p = 0 if hit_p else cur_p + 1
        max_p = max(max_p, cur_p)
        cur_c = 0 if (c_min <= c <= c_max) else cur_c + 1
        max_c = max(max_c, cur_c)
        cur_m = 0 if (m_min <= m <= m_max) else cur_m + 1
        max_m = max(max_m, cur_m)
    return atr_p, atr_c, atr_m, max(max_p, atr_p), max(max_c, atr_c), max(max_m, atr_m)

def deduplicar_alvos(lista):
    vistos = set(); resultado = []
    for item in lista:
        ta = item.get('tipo_ataque', '')
        if ta == "MILHAR": sig = f"{item['banca']}_{item['premio']}_M_{item['cfg']['m_min']}"
        elif ta == "CENTENA": sig = f"{item['banca']}_{item['premio']}_C_{item['cfg']['c_min']}"
        else: sig = f"{item['banca']}_{item['premio']}_{item['cfg']['nome']}"
        if sig not in vistos:
            vistos.add(sig); resultado.append(item)
    return resultado

# 🛡️ MOTOR DE DESDOBRAMENTO (HEDGE)
def get_hedge_grupos(df, col, cfg_matriz, col_delays):
    grupos = list(cfg_matriz['alvos'])
    scores = {g: 0 for g in grupos}

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

    if not eliminar:
        return None 

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
            if g is not None:
                all_groups.append(g) 
                
    if len(all_groups) < 6: return None
    draws = all_groups[-6:] 
    dirs_history = []
    for i in range(1, len(all_groups)):
        dirs_history.append(direcao_pendulo(all_groups[i-1], all_groups[i]))
        
    curr_streak = 0
    curr_dir = dirs_history[-1]
    if curr_dir in ["C", "D"]:
        for d in reversed(dirs_history):
            if d == curr_dir: curr_streak += 1
            else: break
            
    max_streak = 0
    temp_streak = 0
    temp_dir = None
    for d in dirs_history:
        if d in ["C", "D"]:
            if d == temp_dir: temp_streak += 1
            else:
                temp_dir = d
                temp_streak = 1
            if temp_streak > max_streak: max_streak = temp_streak
        else:
            temp_dir = None
            temp_streak = 0
            
    dirs = dirs_history[-5:] 
    last_g = draws[-1]
    
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
        return status, jogos, draws, dirs, curr_streak, max_streak, curr_dir
        
    return "Estável", [], draws, dirs, curr_streak, max_streak, curr_dir

# =============================================================================
# --- MOTOR DE EXTRAÇÃO BLINDADO ---
# =============================================================================
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

# =============================================================================
# --- INTERFACE ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=60)
    st.header("Pentágono V65.17")
    
    if st.button("🔄 FORÇAR ATUALIZAÇÃO", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.success("✅ Base de dados atualizada! A memória do radar foi limpa.")
        
    menu = st.radio("Selecione Tática:", ["🏠 Visão Geral (Home)", "🎯 Scanner de Raio-X", "🧲 Armadilha do Pêndulo", "📡 Extração Central"])

if menu == "🏠 Visão Geral (Home)":
    st.title("🚨 Central AWACS - Desdobramento Sniper")
    st.info("Varredura Inteligente Ativada. Rastreadores 7D e 9D (Artilharia de Centenas) operacionais.")
    if st.button("🚀 INICIAR VARREDURA GLOBAL", use_container_width=True, type="primary"):
        with st.spinner("Triando alvos e calculando os seguros de retaguarda..."):
            oportunidades, recordes, alertas_pendulo = [], [], []
            todos_esq = gerar_matrizes_taticas()
            
            for banca_nome in BANCAS_CONFIG.keys():
                df = carregar_dados_em_memoria(banca_nome)
                if df.empty: continue
                ultimo_sorteio = str(df.iloc[-1]["Sorteio"])
                
                # 1. Armadilha Pêndulo
                for i, col in enumerate(COLUNAS_DF):
                    if banca_nome == "Tradicional" and col != "P1": continue
                    resultado_pend = processar_pendulo(df, col)
                    if resultado_pend:
                        status, jogos, draws, dirs, curr_streak, max_streak, curr_dir = resultado_pend
                        if status != "Estável":
                            alertas_pendulo.append({"banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "status": status, "jogos": jogos, "draws": draws, "dirs": dirs, "curr_streak": curr_streak, "max_streak": max_streak, "curr_dir": curr_dir})
                
                # 2. Pré-Cálculo de Atrasos
                metrics_cache = {}
                for cfg in todos_esq:
                    for i, col in enumerate(COLUNAS_DF):
                        if banca_nome == "Tradicional" and col != "P1": continue
                        
                        ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg)
                        metrics_cache[(cfg['nome'], col)] = (ap, ac, am, mp, mc, mm)
                
                # 3. Exibição AWACS
                for cfg in todos_esq:
                    for i, col in enumerate(COLUNAS_DF):
                        if (cfg['nome'], col) not in metrics_cache: continue
                        ap, ac, am, mp, mc, mm = metrics_cache[(cfg['nome'], col)]
                        ap_lim = cfg['lim'] 
                        
                        is_anomaly = False; prio = 99; alerta = ""; tipo_ataque = ""
                        
                        if am >= 13 and ac >= 13 and ap >= ap_lim:
                            is_anomaly = True; prio = 1; tipo_ataque = "TOTAL"; alerta = f"<div class='alerta-supremo'>🔥 ATAQUE TOTAL (G+C+M)</div>"
                        elif am >= 13:
                            is_anomaly = True; prio = 2; tipo_ataque = "MILHAR"; alerta = f"<div class='alerta-azul'>🔵 ATAQUE MILHAR ({am}x)</div>"
                        elif ac >= 13:
                            is_anomaly = True; prio = 3; tipo_ataque = "CENTENA"; alerta = f"<div class='alerta-verde'>🟢 ATAQUE CENTENA ({ac}x)</div>"
                        elif cfg['modo'] == 'unidade' and ap >= 9:
                            is_anomaly = True; prio = 4; tipo_ataque = "UNIDADE"; alerta = f"<div class='alerta-supremo' style='border-color:#ff00aa; color:#ff00aa;'>🔥 ATAQUE UNIDADE</div>"
                        elif ap >= ap_lim:
                            is_anomaly = True; prio = 5; tipo_ataque = "ALVO_PRINCIPAL"; alerta = f"<div class='alerta-amarelo'>🟡 ATAQUE FORTE ({cfg['modo'].upper()})</div>"

                        if is_anomaly:
                            # Hedge
                            if cfg['modo'] == 'grupo' and cfg['tipo'] == 'seq':
                                col_delays = {k_name: val[0] for (k_name, k_col), val in metrics_cache.items() if k_col == col}
                                hedge_data = get_hedge_grupos(df, col, cfg, col_delays)
                                
                                if hedge_data:
                                    elim_str = ", ".join([str(x).zfill(2) for x in hedge_data['eliminar']])
                                    mant_str = ", ".join([str(x).zfill(2) for x in hedge_data['manter']])
                                    seg_list = [f"Dez {str(d).zfill(2)} ({delay}x)" for g, (d, delay) in hedge_data['seguro'].items()]
                                    seg_str = " | ".join(seg_list)
                                    
                                    alerta += f"""<div style='background:rgba(255,255,255,0.05); padding:6px; border-radius:4px; margin-top:8px;'>
                                        <div style='color:#ffcc00; font-size:11px; font-weight:bold; margin-bottom:3px;'>🛡️ DESDOBRAMENTO TÁTICO</div>
                                        <div style='color:#ff4b4b; font-size:11px;'>❌ Cortar: G {elim_str}</div>
                                        <div style='color:#4CAF50; font-size:11px; margin-top:2px;'>✅ Jogar: {mant_str} ({len(hedge_data['manter'])}G)</div>
                                        <div style='color:#FF851B; font-size:11px; margin-top:4px;'>🆘 Seguro: {seg_str}</div>
                                    </div>"""
                                else:
                                    alerta += f"""<div style='background:rgba(255,255,255,0.05); padding:6px; border-radius:4px; margin-top:8px;'>
                                        <div style='color:#ffcc00; font-size:11px; font-weight:bold;'>🛡️ DESDOBRAMENTO TÁTICO</div>
                                        <div style='color:#ccc; font-size:11px;'>Filtros Neutros. Jogue a Matriz Integral.</div>
                                    </div>"""

                            oportunidades.append({"prio": prio, "banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "ap": ap, "ac": ac, "am": am, "mp": mp, "mc": mc, "mm": mm, "alerta": alerta, "cfg": cfg, "tipo_ataque": tipo_ataque})
                        
                        elif ap == mp and mp >= ap_lim - 1:
                            tipo_rec = "ALVO_PRINCIPAL"; alerta_rec = f"<div class='alerta-amarelo' style='border-color:#FF851B; color:#FF851B;'>🏆 RECORDE ALCANÇADO</div>"
                            recordes.append({"prio": 99, "banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "ap": ap, "ac": ac, "am": am, "mp": mp, "mc": mc, "mm": mm, "alerta": alerta_rec, "cfg": cfg, "tipo_ataque": tipo_rec})
                        elif am == mm and mm >= 9:
                            tipo_rec = "MILHAR"; alerta_rec = f"<div class='alerta-amarelo' style='border-color:#FF851B; color:#FF851B;'>🏆 RECORDE MILHAR</div>"
                            recordes.append({"prio": 99, "banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "ap": ap, "ac": ac, "am": am, "mp": mp, "mc": mc, "mm": mm, "alerta": alerta_rec, "cfg": cfg, "tipo_ataque": tipo_rec})
                        elif ac == mc and mc >= 9:
                            tipo_rec = "CENTENA"; alerta_rec = f"<div class='alerta-amarelo' style='border-color:#FF851B; color:#FF851B;'>🏆 RECORDE CENTENA</div>"
                            recordes.append({"prio": 99, "banca": banca_nome, "ultimo_sorteio": ultimo_sorteio, "premio": TITULOS_PREMIOS[i], "ap": ap, "ac": ac, "am": am, "mp": mp, "mc": mc, "mm": mm, "alerta": alerta_rec, "cfg": cfg, "tipo_ataque": tipo_rec})
            
            oportunidades = deduplicar_alvos(sorted(oportunidades, key=lambda x: (x['prio'], -max(x['ap'], x['ac'], x['am']))))
            recordes = deduplicar_alvos(sorted(recordes, key=lambda x: (-max(x['ap'], x['ac'], x['am']))))
            
            if alertas_pendulo:
                st.success(f"🧲 ALERTA GRAVITACIONAL: {len(alertas_pendulo)} Pêndulos Saturados Detectados!")
                cols_pend = st.columns(3)
                for idx, pend in enumerate(alertas_pendulo):
                    with cols_pend[idx % 3]:
                        status, jogos, draws, dirs = pend['status'], pend['jogos'], pend['draws'], pend['dirs']
                        curr_streak, max_streak, curr_dir = pend['curr_streak'], pend['max_streak'], pend['curr_dir']
                        
                        setas = ["➡️" if d == "C" else "⬅️" if d == "D" else "⏸️" if d == "=" else "✖️" for d in dirs]
                        seq_visual = f"<span style='font-size:16px; font-weight:bold;'>{str(draws[0]).zfill(2)}</span> {setas[0]} " \
                                     f"<span style='font-size:16px; font-weight:bold;'>{str(draws[1]).zfill(2)}</span> {setas[1]} " \
                                     f"<span style='font-size:16px; font-weight:bold;'>{str(draws[2]).zfill(2)}</span> {setas[2]} " \
                                     f"<span style='font-size:16px; font-weight:bold;'>{str(draws[3]).zfill(2)}</span> {setas[3]} " \
                                     f"<span style='font-size:16px; font-weight:bold;'>{str(draws[4]).zfill(2)}</span> {setas[4]} " \
                                     f"<span style='font-size:16px; font-weight:bold; color:#ff4b4b;'>{str(draws[5]).zfill(2)}</span>"
                                     
                        cor_box = "border-color: #ff00aa;" if curr_dir == "C" else "border-color: #00ffff;"
                        lista_jogos = ", ".join(jogos)
                        
                        st.markdown(f"""
                        <div class="home-box home-box-pendulo" style="{cor_box}">
                            <div class="home-banca">🏦 {pend['banca']}</div>
                            <div class="home-horario">🕒 ÚLTIMO: {pend['ultimo_sorteio']}</div>
                            <div class="home-premio">🏆 {pend['premio']}</div>
                            <div class="sniper-dado" style="margin-bottom:10px;">{seq_visual}</div>
                            <div class="sniper-dado" style="text-align:center; margin-top:-5px; margin-bottom:10px;">
                                Saturação: <span class="sniper-valor" style="color:#ff4b4b;">{curr_streak}x</span> (Rec: {max_streak})
                            </div>
                            <div class="alerta-supremo" style="{cor_box}">{status}<br> {'Direção: Crescente' if curr_dir == 'C' else 'Direção: Decrescente'}</div>
                            <div class="sniper-dado" style="margin-top:10px; color:#fff;">Atirar em 15 Grupos {'Anteriores' if curr_dir == 'C' else 'Seguintes'}:</div>
                            <div class="sniper-valor" style="color:#ffcc00; font-size:12px; word-wrap: break-word;">{lista_jogos}</div>
                        </div>
                        """, unsafe_allow_html=True)
                st.markdown("---")
            
            if oportunidades:
                st.success(f"🎯 ALVOS TRAVADOS: {len(oportunidades)} Oportunidades de Ruptura Encontradas!")
                cols = st.columns(3)
                for idx, op in enumerate(oportunidades):
                    c_min, c_max, m_min, m_max = op['cfg']['c_min'], op['cfg']['c_max'], op['cfg']['m_min'], op['cfg']['m_max']
                    ta = op.get('tipo_ataque', '')
                    css_class = f"home-box-{op['cfg']['tipo']}"
                    
                    if ta == 'UNIDADE':
                        lbl_alvo = "Unidade"; sub_titulo = "ALVO EXCLUSIVO: UNIDADE"; titulo = op['cfg']['nome']
                        dado_principal = f"<span style='float:right;'><span class='sniper-valor' style='color:#ff4b4b;'>{op['ap']}x</span> (Rec: {op['mp']})</span>"
                        cm_html = """Centena: <span style="float:right;color:#555;">---</span><br>Milhar: <span style="float:right;color:#555;">---</span>"""
                    elif ta == 'MILHAR':
                        lbl_alvo = "Filtro Base"; sub_titulo = f"C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}"; titulo = f"🎯 FOCO: MILHAR {str(m_min).zfill(4)} AO {str(m_max).zfill(4)}"
                        dado_principal = f"<span style='float:right;color:#555;'>---</span>"
                        cm_html = f"""Centena: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ac']>=13 else '#4CAF50'};">{op['ac']}x</span> (Rec: {op['mc']})</span><br>Milhar: <span style="float:right;"><span class="sniper-valor" style="color:#ff4b4b;">{op['am']}x</span> (Rec: {op['mm']})</span>"""
                        css_class = "home-box-seq" 
                    elif ta == 'CENTENA':
                        lbl_alvo = "Filtro Base"; sub_titulo = f"M: {str(m_min).zfill(4)} ao {str(m_max).zfill(4)}"; titulo = f"🎯 FOCO: CENTENA {str(c_min).zfill(3)} AO {str(c_max).zfill(3)}"
                        dado_principal = f"<span style='float:right;color:#555;'>---</span>"
                        cm_html = f"""Centena: <span style="float:right;"><span class="sniper-valor" style="color:#ff4b4b;">{op['ac']}x</span> (Rec: {op['mc']})</span><br>Milhar: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['am']>=13 else '#4CAF50'};">{op['am']}x</span> (Rec: {op['mm']})</span>"""
                        css_class = "home-box-seq"
                    else:
                        lbl_alvo = "Grupo" if op['cfg']['modo'] == 'grupo' else ("Centena" if op['cfg']['modo'] == 'centena' else "Dezena")
                        sub_titulo = f"C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}<br>M: {str(m_min).zfill(4)} ao {str(m_max).zfill(4)}"
                        titulo = op['cfg']['nome']
                        dado_principal = f"<span style='float:right;'><span class='sniper-valor' style='color:{'#ff4b4b' if op['ap']>=op['cfg']['lim'] else '#4CAF50'};'>{op['ap']}x</span> (Rec: {op['mp']})</span>"
                        cm_html = f"""Centena: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ac']>=13 else '#4CAF50'};">{op['ac']}x</span> (Rec: {op['mc']})</span><br>Milhar: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['am']>=13 else '#4CAF50'};">{op['am']}x</span> (Rec: {op['mm']})</span>"""
                        
                    with cols[idx % 3]:
                        st.markdown(f"""<div class="home-box {css_class}"><div class="home-banca">🏦 {op['banca']}</div><div class="home-horario">🕒 ÚLTIMO: {op['ultimo_sorteio']}</div><div class="home-premio">🏆 {op['premio']}</div><div class="sniper-titulo">{titulo}<br>{sub_titulo}</div><div class="sniper-dado" style="text-align:left;">{lbl_alvo}: {dado_principal}<br>{cm_html}</div>{op['alerta']}</div>""", unsafe_allow_html=True)
                st.markdown("---") 
            
            if recordes:
                st.warning("⚠️ RECORDES HISTÓRICOS ALCANÇADOS (Radar Secundário):")
                cols = st.columns(3)
                for idx, op in enumerate(recordes):
                    c_min, c_max, m_min, m_max = op['cfg']['c_min'], op['cfg']['c_max'], op['cfg']['m_min'], op['cfg']['m_max']
                    ta = op.get('tipo_ataque', '')
                    css_class = f"home-box-{op['cfg']['tipo']}"
                    
                    if ta == 'UNIDADE':
                        lbl_alvo = "Unidade"; sub_titulo = "ALVO EXCLUSIVO: UNIDADE"; titulo = op['cfg']['nome']
                        dado_principal = f"<span style='float:right;'><span class='sniper-valor' style='color:#ff4b4b;'>{op['ap']}x</span> (Rec: {op['mp']})</span>"
                        cm_html = """Centena: <span style="float:right;color:#555;">---</span><br>Milhar: <span style="float:right;color:#555;">---</span>"""
                    elif ta == 'MILHAR':
                        lbl_alvo = "Filtro Base"; sub_titulo = f"C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}"; titulo = f"🏆 RECORDE MILHAR {str(m_min).zfill(4)} AO {str(m_max).zfill(4)}"
                        dado_principal = f"<span style='float:right;color:#555;'>---</span>"
                        cm_html = f"""Centena: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ac']==op['mc'] else '#aaa'};">{op['ac']}x</span> (Rec: {op['mc']})</span><br>Milhar: <span style="float:right;"><span class="sniper-valor" style="color:#ff4b4b;">{op['am']}x</span> (Rec: {op['mm']})</span>"""
                        css_class = "home-box-seq"
                    elif ta == 'CENTENA':
                        lbl_alvo = "Filtro Base"; sub_titulo = f"M: {str(m_min).zfill(4)} ao {str(m_max).zfill(4)}"; titulo = f"🏆 RECORDE CENTENA {str(c_min).zfill(3)} AO {str(c_max).zfill(3)}"
                        dado_principal = f"<span style='float:right;color:#555;'>---</span>"
                        cm_html = f"""Centena: <span style="float:right;"><span class="sniper-valor" style="color:#ff4b4b;">{op['ac']}x</span> (Rec: {op['mc']})</span><br>Milhar: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['am']==op['mm'] else '#aaa'};">{op['am']}x</span> (Rec: {op['mm']})</span>"""
                        css_class = "home-box-seq"
                    else:
                        lbl_alvo = "Grupo" if op['cfg']['modo'] == 'grupo' else ("Centena" if op['cfg']['modo'] == 'centena' else "Dezena")
                        sub_titulo = f"C: {str(c_min).zfill(3)} ao {str(c_max).zfill(3)}<br>M: {str(m_min).zfill(4)} ao {str(m_max).zfill(4)}"
                        titulo = op['cfg']['nome']
                        dado_principal = f"<span style='float:right;'><span class='sniper-valor' style='color:{'#ff4b4b' if op['ap']==op['mp'] else '#aaa'};'>{op['ap']}x</span> (Rec: {op['mp']})</span>"
                        cm_html = f"""Centena: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['ac']==op['mc'] else '#aaa'};">{op['ac']}x</span> (Rec: {op['mc']})</span><br>Milhar: <span style="float:right;"><span class="sniper-valor" style="color:{'#ff4b4b' if op['am']==op['mm'] else '#aaa'};">{op['am']}x</span> (Rec: {op['mm']})</span>"""
                        
                    with cols[idx % 3]:
                        st.markdown(f"""<div class="home-box {css_class}"><div class="home-banca">🏦 {op['banca']}</div><div class="home-horario">🕒 ÚLTIMO: {op['ultimo_sorteio']}</div><div class="home-premio">🏆 {op['premio']}</div><div class="sniper-titulo">{titulo}<br>{sub_titulo}</div><div class="sniper-dado" style="text-align:left;">{lbl_alvo}: {dado_principal}<br>{cm_html}</div>{op['alerta']}</div>""", unsafe_allow_html=True)
            
            if not oportunidades and not alertas_pendulo and not recordes: 
                st.success("🟢 Modo Stealth: Nenhum alvo atingiu a zona de ruptura crítica ainda.")

elif menu == "🎯 Scanner de Raio-X":
    st.title("🎯 Scanner de Raio-X (Consulta Manual)")
    st.info("Consulte o atraso exato e o recorde histórico de qualquer alvo em todos os prêmios da banca escolhida.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        banca_rx = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    with col2:
        categoria_rx = st.selectbox("Categoria:", ["Grupo (1 a 25)", "Dezena (00 a 99)", "Unidade (0 a 9)", "Filtros de Massa"])
    with col3:
        if categoria_rx == "Grupo (1 a 25)":
            alvo_rx = st.number_input("Qual Grupo?", min_value=1, max_value=25, value=1)
        elif categoria_rx == "Dezena (00 a 99)":
            alvo_rx = st.number_input("Qual Dezena?", min_value=0, max_value=99, value=0)
        elif categoria_rx == "Unidade (0 a 9)":
            alvo_rx = st.number_input("Qual Unidade?", min_value=0, max_value=9, value=0)
        else:
            alvo_rx = st.selectbox("Qual Filtro?", [
                "Grupos Pares", "Grupos Ímpares", 
                "Dezenas Pares", "Dezenas Ímpares", 
                "Dezenas Baixas (01-50)", "Dezenas Altas (51-00)", 
                "Dezenas Miolo (26-75)", "Dezenas Bordas",
                "Dezenas Finais Baixos (1-5)", "Dezenas Finais Altos (6-0)",
                "Unidades Baixas (1-5)", "Unidades Altas (6-0)",
                "Unidades Ímpares", "Unidades Pares",
                "Inversão 7D Dezena (0 ao 6)", "Inversão 7D Dezena (1 ao 7)", "Inversão 7D Dezena (2 ao 8)", 
                "Inversão 7D Dezena (3 ao 9)", "Inversão 7D Dezena (4 ao 0)", "Inversão 7D Dezena (5 ao 1)", 
                "Inversão 7D Dezena (6 ao 2)", "Inversão 7D Dezena (7 ao 3)", "Inversão 7D Dezena (8 ao 4)", 
                "Inversão 7D Dezena (9 ao 5)",
                "Inversão 9D Centena (0 ao 8)", "Inversão 9D Centena (1 ao 9)", "Inversão 9D Centena (2 ao 0)", 
                "Inversão 9D Centena (3 ao 1)", "Inversão 9D Centena (4 ao 2)", "Inversão 9D Centena (5 ao 3)", 
                "Inversão 9D Centena (6 ao 4)", "Inversão 9D Centena (7 ao 5)", "Inversão 9D Centena (8 ao 6)", 
                "Inversão 9D Centena (9 ao 7)"
            ])
            
    if st.button("🔎 EXECUTAR RAIO-X", type="primary", use_container_width=True):
        with st.spinner(f"Escaneando todo o histórico da {banca_rx}..."):
            df = carregar_dados_em_memoria(banca_rx)
            if df.empty:
                st.error("Base de dados vazia. Execute uma extração central primeiro.")
            else:
                exibir_banner_sorteio(df, banca_rx)
                
                cfg_rx = {'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999, 'lim': 0}
                if categoria_rx == "Grupo (1 a 25)":
                    cfg_rx['alvos'] = {int(alvo_rx)}; cfg_rx['modo'] = 'grupo'; cfg_rx['nome'] = f"GRUPO {str(alvo_rx).zfill(2)}"
                elif categoria_rx == "Dezena (00 a 99)":
                    cfg_rx['alvos'] = {int(alvo_rx)}; cfg_rx['modo'] = 'dezena'; cfg_rx['nome'] = f"DEZENA {str(alvo_rx).zfill(2)}"
                elif categoria_rx == "Unidade (0 a 9)":
                    cfg_rx['alvos'] = {int(alvo_rx)}; cfg_rx['modo'] = 'unidade'; cfg_rx['nome'] = f"UNIDADE {alvo_rx}"
                else:
                    cfg_rx['nome'] = alvo_rx.upper()
                    if alvo_rx == "Grupos Pares": cfg_rx['alvos'] = set(range(2, 26, 2)); cfg_rx['modo'] = 'grupo'
                    elif alvo_rx == "Grupos Ímpares": cfg_rx['alvos'] = set(range(1, 26, 2)); cfg_rx['modo'] = 'grupo'
                    elif alvo_rx == "Dezenas Pares": cfg_rx['alvos'] = {x for x in range(100) if x % 2 == 0}; cfg_rx['modo'] = 'dezena'
                    elif alvo_rx == "Dezenas Ímpares": cfg_rx['alvos'] = {x for x in range(100) if x % 2 != 0}; cfg_rx['modo'] = 'dezena'
                    elif alvo_rx == "Dezenas Baixas (01-50)": cfg_rx['alvos'] = set(range(1, 51)); cfg_rx['modo'] = 'dezena'
                    elif alvo_rx == "Dezenas Altas (51-00)": cfg_rx['alvos'] = set(range(51, 100)) | {0}; cfg_rx['modo'] = 'dezena'
                    elif alvo_rx == "Dezenas Miolo (26-75)": cfg_rx['alvos'] = set(range(26, 76)); cfg_rx['modo'] = 'dezena'
                    elif alvo_rx == "Dezenas Bordas": cfg_rx['alvos'] = set(range(1, 26)) | set(range(76, 100)) | {0}; cfg_rx['modo'] = 'dezena'
                    
                    elif alvo_rx == "Dezenas Finais Baixos (1-5)": cfg_rx['alvos'] = {x for x in range(100) if x % 10 in [1, 2, 3, 4, 5]}; cfg_rx['modo'] = 'dezena'
                    elif alvo_rx == "Dezenas Finais Altos (6-0)": cfg_rx['alvos'] = {x for x in range(100) if x % 10 in [6, 7, 8, 9, 0]}; cfg_rx['modo'] = 'dezena'
                    
                    elif alvo_rx == "Unidades Baixas (1-5)": cfg_rx['alvos'] = {1, 2, 3, 4, 5}; cfg_rx['modo'] = 'unidade'
                    elif alvo_rx == "Unidades Altas (6-0)": cfg_rx['alvos'] = {6, 7, 8, 9, 0}; cfg_rx['modo'] = 'unidade'
                    elif alvo_rx == "Unidades Ímpares": cfg_rx['alvos'] = {1, 3, 5, 7, 9}; cfg_rx['modo'] = 'unidade'
                    elif alvo_rx == "Unidades Pares": cfg_rx['alvos'] = {0, 2, 4, 6, 8}; cfg_rx['modo'] = 'unidade'
                    
                    elif alvo_rx.startswith("Inversão 7D"):
                        nums_str = alvo_rx.replace("Inversão 7D Dezena (", "").replace(")", "").split(" ao ")
                        start_n = int(nums_str[0])
                        bases_list = [[0,1,2,3,4,5,6], [1,2,3,4,5,6,7], [2,3,4,5,6,7,8], [3,4,5,6,7,8,9], [4,5,6,7,8,9,0], [5,6,7,8,9,0,1], [6,7,8,9,0,1,2], [7,8,9,0,1,2,3], [8,9,0,1,2,3,4], [9,0,1,2,3,4,5]]
                        for b in bases_list:
                            if b[0] == start_n:
                                cfg_rx['alvos'] = {int(f"{d1}{d2}") for d1 in b for d2 in b if d1 != d2}
                                break
                        cfg_rx['modo'] = 'dezena'
                        
                    elif alvo_rx.startswith("Inversão 9D"):
                        nums_str = alvo_rx.replace("Inversão 9D Centena (", "").replace(")", "").split(" ao ")
                        start_n = int(nums_str[0])
                        bases_list_c = [[0,1,2,3,4,5,6,7,8], [1,2,3,4,5,6,7,8,9], [2,3,4,5,6,7,8,9,0], [3,4,5,6,7,8,9,0,1], [4,5,6,7,8,9,0,1,2], [5,6,7,8,9,0,1,2,3], [6,7,8,9,0,1,2,3,4], [7,8,9,0,1,2,3,4,5], [8,9,0,1,2,3,4,5,6], [9,0,1,2,3,4,5,6,7]]
                        for b in bases_list_c:
                            if b[0] == start_n:
                                cfg_rx['alvos'] = {int(f"{d1}{d2}{d3}") for d1 in b for d2 in b for d3 in b if d1 != d2 and d2 != d3 and d1 != d3}
                                break
                        cfg_rx['modo'] = 'centena'

                st.markdown(f"### 📡 Relatório de Escaneamento: <span style='color:#00ffff;'>{cfg_rx['nome']}</span>", unsafe_allow_html=True)
                
                if categoria_rx == "Grupo (1 a 25)":
                    st.info("🧠 **INTELIGÊNCIA TÁTICA:** Um Grupo seco tem **4% de chance** de acerto. A banca tem 96% de chance de fugir dele no sorteio. A zona de ruptura crítica do elástico ocorre lá pela casa dos **115x a 120x** de atraso.")
                elif categoria_rx == "Dezena (00 a 99)":
                    st.info("🧠 **INTELIGÊNCIA TÁTICA:** Uma Dezena seca tem apenas **1% de chance** de acerto. A banca tem 99% de chance de fugir. A zona de ruptura matemática crítica ocorre muito longe, lá pela casa dos **450x a 460x** de atraso.")
                elif categoria_rx == "Unidade (0 a 9)":
                    st.info("🧠 **INTELIGÊNCIA TÁTICA:** Uma Unidade seca tem **10% de chance** de acerto. O elástico atinge sua tensão máxima de ruptura lá pela casa dos **45x a 50x** de atraso.")
                elif alvo_rx.startswith("Inversão 7D"):
                    st.info("🧠 **INTELIGÊNCIA TÁTICA:** A Inversão 7D forma **42 Dezenas** e cobre **42% da roleta**. A chance da banca escapar zera estatisticamente por volta dos **12x de atraso**.")
                elif alvo_rx.startswith("Inversão 9D"):
                    st.info("🧠 **INTELIGÊNCIA TÁTICA:** A Inversão 9D forma **504 Centenas** e cobre **50,4% da roleta**. O poder de fogo é máximo e a zona de ruptura crítica acontece rapidamente aos **9x de atraso**.")
                else:
                    st.info("🧠 **INTELIGÊNCIA TÁTICA:** Filtros de Massa cobrem **50% da roleta**. A banca tem pouco espaço de fuga. A zona de ruptura matemática absoluta ocorre entre **7x e 9x**.")
                
                cols_rx = st.columns(5)
                for i, col in enumerate(COLUNAS_DF):
                    ap, ac, am, mp, mc, mm = calcular_metricas_fantasma(df, col, cfg_rx)
                    
                    with cols_rx[i]:
                        cor_atraso = "#ff4b4b" if ap >= 7 else "#4CAF50" 
                        st.markdown(f"""
                        <div class="home-box" style="background-color:#111; border-color:#444;">
                            <div class="home-premio">🏆 {TITULOS_PREMIOS[i]}</div>
                            <div class="sniper-dado" style="font-size:13px; margin-top:10px;">ATRASO ATUAL:</div>
                            <div class="sniper-valor" style="color:{cor_atraso}; font-size:26px;">{ap}x</div>
                            <div class="sniper-dado" style="margin-top:10px;">RECORDE MÁXIMO:</div>
                            <div class="sniper-valor" style="color:#FF851B; font-size:18px;">{mp}x</div>
                        </div>
                        """, unsafe_allow_html=True)

elif menu == "🧲 Armadilha do Pêndulo":
    st.title("🧲 Armadilha de Saturação (Pêndulo)")
    st.info("Analisa a física circular de **Passos Curtos (1 a 6 casas)** dos últimos 6 sorteios. Pulos longos (✖️) quebram a saturação.")
    banca_pendulo = st.selectbox("Selecione o Alvo de Rastreador Circular:", list(BANCAS_CONFIG.keys()))
    
    if st.button("🧲 ANALISAR MOMENTUM CIRCULAR", type="primary", use_container_width=True):
        with st.spinner(f"Calculando a distância circular na {banca_pendulo}..."):
            df = carregar_dados_em_memoria(banca_pendulo)
            if df.empty:
                st.error("Base de dados vazia. Faça uma extração primeiro.")
            else:
                exibir_banner_sorteio(df, banca_pendulo)
                st.markdown("### 📊 Resultado do Rastreador")
                cols = st.columns(5)
                for i, col in enumerate(COLUNAS_DF):
                    resultado = processar_pendulo(df, col)
                    with cols[i]:
                        if resultado:
                            status, jogos, draws, dirs, curr_streak, max_streak, curr_dir = resultado
                            setas = ["➡️" if d == "C" else "⬅️" if d == "D" else "⏸️" if d == "=" else "✖️" for d in dirs]
                            seq_visual = f"<span style='font-size:16px; font-weight:bold;'>{str(draws[0]).zfill(2)}</span> {setas[0]} " \
                                         f"<span style='font-size:16px; font-weight:bold;'>{str(draws[1]).zfill(2)}</span> {setas[1]} " \
                                         f"<span style='font-size:16px; font-weight:bold;'>{str(draws[2]).zfill(2)}</span> {setas[2]} " \
                                         f"<span style='font-size:16px; font-weight:bold;'>{str(draws[3]).zfill(2)}</span> {setas[3]} " \
                                         f"<span style='font-size:16px; font-weight:bold;'>{str(draws[4]).zfill(2)}</span> {setas[4]} " \
                                         f"<span style='font-size:16px; font-weight:bold; color:#ff4b4b;'>{str(draws[5]).zfill(2)}</span>"
                            
                            if status != "Estável":
                                cor_box = "border-color: #ff00aa;" if curr_dir == "C" else "border-color: #00ffff;"
                                lista_jogos = ", ".join(jogos)
                                
                                st.markdown(f"""
                                <div class="home-box home-box-pendulo" style="{cor_box}">
                                    <div class="home-premio">🏆 {TITULOS_PREMIOS[i]}</div>
                                    <div class="sniper-dado" style="margin-bottom:10px;">{seq_visual}</div>
                                    <div class="sniper-dado" style="text-align:center; margin-top:-5px; margin-bottom:10px;">
                                        Saturação: <span class="sniper-valor" style="color:#ff4b4b;">{curr_streak}x</span> (Rec: {max_streak})
                                    </div>
                                    <div class="alerta-supremo" style="{cor_box}">{status}<br> {'Direção: Crescente' if curr_dir == 'C' else 'Direção: Decrescente'}</div>
                                    <div class="sniper-dado" style="margin-top:10px; color:#fff;">Atirar em 15 Grupos {'Anteriores' if curr_dir == 'C' else 'Seguintes'}:</div>
                                    <div class="sniper-valor" style="color:#ffcc00; font-size:12px; word-wrap: break-word;">{lista_jogos}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <div class="home-box" style="background-color:#111; border-color:#333;">
                                    <div class="home-premio" style="color:#aaa;">🏆 {TITULOS_PREMIOS[i]}</div>
                                    <div class="sniper-dado" style="margin-bottom:10px; color:#666;">{seq_visual}</div>
                                    <div class="sniper-dado" style="text-align:center; margin-top:-5px; margin-bottom:10px;">
                                        Saturação: <span class="sniper-valor" style="color:#4CAF50;">{curr_streak}x</span> (Rec: {max_streak})
                                    </div>
                                    <div class="sniper-dado">Movimento Estável.<br>Sem saturação detectada.</div>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.write(f"Sem dados suficientes em {TITULOS_PREMIOS[i]}")

elif menu == "📡 Extração Central":
    st.title("📡 Extração de Resultados")
    dt = st.date_input("Data do Sorteio:", value=date.today())
    col1, col2 = st.columns(2)
    with col1:
        banca_ex = st.selectbox("Selecione o Alvo Individual:", list(BANCAS_CONFIG.keys()))
        if st.button("🚀 COLETA INDIVIDUAL", type="primary", use_container_width=True):
            with st.spinner(f"Conectando aos servidores da {banca_ex}..."):
                res = extrair_dia(banca_ex, dt)
                if res:
                    sh = conectar_sheets()
                    if sh:
                        ws = sh.worksheet(MAPA_ABAS[banca_ex])
                        existentes = ws.get_all_values()
                        set_exist = {f"{str(r[0]).strip()}_{str(r[1]).strip()}" for r in existentes if len(r) >= 2}
                        p_ins = [l for l in res if f"{str(l[0]).strip()}_{str(l[1]).strip()}" not in set_exist]
                        if p_ins: 
                            ws.append_rows(p_ins, value_input_option="RAW")
                            st.success(f"✅ {len(p_ins)} novos registros salvos.")
                            st.cache_data.clear() 
                        else: st.info("Base de dados já atualizada.")
                else: st.error("Sem dados para extrair.")
    with col2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🌍 EXTRAÇÃO GLOBAL", type="primary", use_container_width=True):
            with st.spinner("Iniciando varredura global em todos os servidores..."):
                sh = conectar_sheets()
                if not sh: st.error("Erro Crítico de Conexão.")
                else:
                    total_salvos = 0
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
                                st.success(f"✅ {banca_alvo}: {len(p_ins)} salvos.")
                            else: st.info(f"ℹ️ {banca_alvo}: Atualizada.")
                        else: st.warning(f"⚠️ {banca_alvo}: Sem dados.")
                    if total_salvos > 0:
                        st.cache_data.clear() 
                        st.success(f"🎯 MISSÃO CONCLUÍDA: {total_salvos} novos registros.")

st.markdown("""<div class="rodape-tatico">🎯 GATILHOS (Teto Máximo): M/C = 13x | Dezenas, Unidades e Filtros = 9x | 15 Grupos = 7x | 12 Grupos = 10x | Inversão 7D = 12x | Inversão 9D = 9x | Pêndulo = 5x</div>""", unsafe_allow_html=True)
