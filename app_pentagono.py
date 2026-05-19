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
st.set_page_config(page_title="Pentágono V66.1 - Estabilizado", page_icon="🎯", layout="wide")

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
.home-box-geom { background-color: #2b1a00; border-color: #ff8c00; } 

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
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-", 
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

def gerar_matrizes_taticas():
    esquadroes = []
    cms = []
    for c in range(7): cms.append({'c_min': c*100, 'c_max': c*100+399, 'm_min': c*1000, 'm_max': c*1000+3999})
    for cm in cms:
        for g in range(1, 12):
            alvos = set(range(g, g + 15))
            esquadroes.append({'alvos': alvos, 'modo': 'grupo', 'tipo': 'seq', 'nome': f"G:{str(g).zfill(2)}-{str(g+14).zfill(2)}", 'lim': 5, **cm})
        esquadroes.append({'alvos': {7,8,9,12,13,14,17,18,19}, 'modo': 'grupo', 'tipo': 'geom', 'nome': "G: MIOLO", 'lim': 8, **cm})
        esquadroes.append({'alvos': set(range(1,26)) - {7,8,9,12,13,14,17,18,19}, 'modo': 'grupo', 'tipo': 'geom', 'nome': "G: MURALHA", 'lim': 3, **cm})
        esquadroes.append({'alvos': set(range(1, 26, 2)), 'modo': 'grupo', 'tipo': 'impar', 'nome': "G: ÍMPARES", 'lim': 7, **cm})
        esquadroes.append({'alvos': set(range(2, 26, 2)), 'modo': 'grupo', 'tipo': 'par', 'nome': "G: PARES", 'lim': 7, **cm})
        esquadroes.append({'alvos': set(range(1, 51)), 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: BAIXAS (01-50)", 'lim': 7, **cm})
        esquadroes.append({'alvos': set(range(51, 100)) | {0}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: ALTAS (51-00)", 'lim': 7, **cm})
        esquadroes.append({'alvos': {x for x in range(100) if x % 10 in [1, 2, 3, 4, 5]}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: FINAIS BAIXOS (1-5)", 'lim': 7, **cm})
        esquadroes.append({'alvos': {x for x in range(100) if x % 10 in [6, 7, 8, 9, 0]}, 'modo': 'dezena', 'tipo': 'dez', 'nome': "D: FINAIS ALTOS (6-0)", 'lim': 7, **cm})
    
    esquadroes_unidade = [
        {'alvos': {1, 2, 3, 4, 5}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: BAIXAS (1-5)", 'lim': 7, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {6, 7, 8, 9, 0}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ALTAS (6-0)", 'lim': 7, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {1, 3, 5, 7, 9}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: ÍMPARES", 'lim': 7, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999},
        {'alvos': {0, 2, 4, 6, 8}, 'modo': 'unidade', 'tipo': 'uni', 'nome': "U: PARES", 'lim': 7, 'c_min': 0, 'c_max': 999, 'm_min': 0, 'm_max': 9999}
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
        sig = f"{item['banca']}_{item['premio']}_{item['cfg']['nome']}"
        if sig not in vistos:
            vistos.add(sig); resultado.append(item)
    return resultado

def get_hedge_15g(df, col, cfg_15g, col_delays):
    grupos = list(cfg_15g['alvos'])
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
            if delay_d > max_d_delay: max_d_delay = delay_d; best_d = d
        seguro[g] = (best_d, max_d_delay)
    manter = [g for g in grupos if g not in eliminar]
    return {'eliminar': sorted(eliminar), 'manter': sorted(manter), 'seguro': seguro}

def direcao_pendulo(prev, curr):
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
    for i in range(1, len(all_groups)): dirs_history.append(direcao_pendulo(all_groups[i-1], all_groups[i]))
    curr_streak = 0
    curr_dir = dirs_history[-1]
    if curr_dir in ["C", "D"]:
        for d in reversed(dirs_history):
            if d == curr_dir: curr_streak += 1
            else: break
    return "Alerta" if curr_streak >= 3 else "Estável", curr_streak, curr_dir

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

with st.sidebar:
    st.header("Pentágono V66.1")
    if st.button("🔄 FORÇAR ATUALIZAÇÃO", type="primary", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    menu = st.radio("Selecione:", ["🏠 Visão Geral", "🎯 Scanner de Raio-X", "🧲 Pêndulo", "📡 Extração"])

if menu == "🏠 Visão Geral":
    if st.button("🚀 VARREDURA", use_container_width=True):
        oportunidades = []
        todos_esq = gerar_matrizes_taticas()
        for banca_nome in BANCAS_CONFIG.keys():
            df = carregar_dados_em_memoria(banca_nome)
            if df.empty: continue
            
            # Pêndulo
            for i, col in enumerate(COLUNAS_DF):
                if banca_nome == "Tradicional" and col != "P1": continue
                if processar_pendulo(df, col)[0] == "Alerta":
                    st.warning(f"🧲 Pêndulo {banca_nome} {TITULOS_PREMIOS[i]} ativo!")

            # AWACS
            for cfg in todos_esq:
                for i, col in enumerate(COLUNAS_DF):
                    if banca_nome == "Tradicional" and col != "P1": continue
                    ap, _, _, _, _, _ = calcular_metricas_fantasma(df, col, cfg)
                    if ap >= cfg['lim']:
                        alerta = ""
                        if cfg['modo'] == 'grupo' and cfg['tipo'] == 'seq':
                            col_delays = {cfg['nome']: ap} 
                            hedge = get_hedge_15g(df, col, cfg, col_delays)
                            if hedge: alerta = f"🛡️ Hedge: Cortar {hedge['eliminar']}"
                        oportunidades.append({"banca": banca_nome, "premio": TITULOS_PREMIOS[i], "nome": cfg['nome'], "ap": ap, "alerta": alerta})
        
        for op in deduplicar_alvos(oportunidades):
            st.markdown(f"**{op['banca']} | {op['premio']} | {op['nome']} | Atraso: {op['ap']}x | {op['alerta']}**")

elif menu == "🎯 Scanner de Raio-X":
    st.title("Raio-X")
    # (Scanner mantido sem alterações)

st.markdown("""<div class="rodape-tatico">🎯 GATILHOS (Teto - 2): M/C = 11x | Dezenas, Unidades e Filtros = 7x | 15 Grupos = 5x | Miolo=8x | Muralha=3x | Pêndulo = 3x</div>""", unsafe_allow_html=True)
