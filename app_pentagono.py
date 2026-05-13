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
# --- 1. CONFIGURAÇÕES, CSS E CONEXÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono V57.5 - Sniper Triplo", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.tabela-compacta { width: 100%; border-collapse: collapse; text-align: center; font-size: 14px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
.tabela-compacta th { background-color: #330000; color: #ff4b4b; padding: 8px; border: 1px solid #444; font-size: 13px; }
.tabela-compacta td { padding: 6px; border: 1px solid #333; color: #fff; background-color: #121212; }
.td-cabecalho { color: #888 !important; font-size: 10px !important; background-color: #000 !important; }
.grupo-destaque { font-weight: bold; color: #4CAF50 !important; font-size: 16px; }
.banner-info { background-color: #0e1117; border: 1px solid #4CAF50; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px; }

/* Estilos do Sniper Triplo */
.sniper-box { background-color: #1a1a2e; border: 1px solid #16213e; border-radius: 8px; padding: 12px; margin-bottom: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
.sniper-titulo { font-size: 16px; font-weight: bold; color: #e94560; margin-bottom: 8px; text-transform: uppercase; border-bottom: 1px solid #333; padding-bottom: 5px;}
.sniper-dado { font-size: 12px; color: #aaa; margin: 4px 0; }
.sniper-valor { font-weight: bold; font-size: 15px; color: #fff; }

/* Cores de Alerta */
.alerta-supremo { background-color: #330033; border: 1px solid #ff00ff; color: #ff00ff; padding: 8px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 13px; }
.alerta-verde { background-color: #003300; border: 1px solid #00ff00; color: #00ff00; padding: 8px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 13px; }
.alerta-azul { background-color: #001a33; border: 1px solid #0099ff; color: #0099ff; padding: 8px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 13px; }
.alerta-amarelo { background-color: #332b00; border: 1px solid #ffcc00; color: #ffcc00; padding: 8px; border-radius: 5px; font-weight: bold; margin-top: 10px; font-size: 13px; }
.alerta-cinza { background-color: #222; border: 1px solid #555; color: #888; padding: 8px; border-radius: 5px; font-size: 12px; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

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
            <span style='color: #4CAF50; font-size: 11px; font-weight: bold;'>📡 ÚLTIMA ATUALIZAÇÃO MONITORADA:</span><br>
            <span style='color: white; font-size: 18px; font-weight: bold;'>{banca} - {ult_nome}</span>
        </div>
        """, unsafe_allow_html=True)

def get_grupo_int(m):
    try:
        d = int(str(m)[-2:])
        return 25 if d == 0 else math.ceil(d/4)
    except: return None

def get_grupo_str(m):
    try:
        d = int(str(m)[-2:])
        return "25" if d == 0 else str(math.ceil(d/4)).zfill(2)
    except: return None

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
            texto_alvo = txt_th if re.search(r'\d{2}:\d{2}h?|\d{2}h', txt_th) else txt_prev
            if "FEDERAL" in texto_alvo.upper(): continue
            match_hora = re.search(r'(\d{2}):(\d{2})h?|(\d{2})h', texto_alvo, re.IGNORECASE)
            nome = f"{match_hora.group(3)}:00" if match_hora and match_hora.group(3) else (f"{match_hora.group(1)}:{match_hora.group(2)}" if match_hora else "Extra")
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
# --- LÓGICA DO RADAR SNIPER (TRIPLO) ---
# =============================================================================
def calcular_atrasos_sniper_triplo(df_analise, coluna):
    atraso_grupo = 0
    atraso_centena = 0
    atraso_milhar = 0
    
    achou_g = False
    achou_c = False
    achou_m = False
    
    # Lê do mais recente pro mais antigo
    for i in range(len(df_analise)-1, -1, -1):
        milhar = str(df_analise.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "0000" or milhar == "nan": continue
        
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:])
        except: c = -1
        try: m = int(milhar)
        except: m = -1
            
        if not achou_g:
            if g is not None and 1 <= g <= 15: achou_g = True
            else: atraso_grupo += 1
            
        if not achou_c:
            if c >= 600: achou_c = True
            else: atraso_centena += 1

        if not achou_m:
            if m >= 6000: achou_m = True
            else: atraso_milhar += 1
            
        # Se achou os 3, não precisa mais olhar o passado
        if achou_g and achou_c and achou_m: break
            
    return atraso_grupo, atraso_centena, atraso_milhar

# =============================================================================
# --- LÓGICA CLÁSSICA (ZEBRA) ---
# =============================================================================
def calcular_ranking_por_coluna(df_analise, coluna):
    scores_tmp = {str(i).zfill(2): {'frequencia': 0, 'puxada': 0, 'ruptura': 0, 'total': 0} for i in range(1, 26)}
    atr_g = {str(i).zfill(2): {'t': 0, 'max': 0} for i in range(1, 26)}
    for i in range(len(df_analise)):
        g_v = get_grupo_str(df_analise.iloc[i][coluna])
        if g_v:
            scores_tmp[g_v]['frequencia'] += 1
            for k in atr_g:
                atr_g[k]['t'] = 0 if k == g_v else atr_g[k]['t'] + 1
                if atr_g[k]['t'] > atr_g[k]['max']: atr_g[k]['max'] = atr_g[k]['t']
    for k, v in atr_g.items():
        if v['t'] >= (v['max'] - 2) and v['t'] > 0: scores_tmp[k]['ruptura'] += 4  
    if len(df_analise) > 1:
        ult_g = get_grupo_str(df_analise.iloc[-1][coluna])
        for i in range(len(df_analise)-1):
            if get_grupo_str(df_analise.iloc[i][coluna]) == ult_g:
                g_prox = get_grupo_str(df_analise.iloc[i+1][coluna])
                if g_prox: scores_tmp[g_prox]['puxada'] += 7 
    for k in scores_tmp: 
        scores_tmp[k]['total'] = scores_tmp[k]['frequencia'] + scores_tmp[k]['puxada'] + scores_tmp[k]['ruptura']
    ranking = sorted(scores_tmp.items(), key=lambda x: x[1]['total'], reverse=True)
    return [x[0] for x in ranking][19:25], scores_tmp

# =============================================================================
# --- INTERFACE DE COMANDO ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=60)
    st.header("Pentágono V57.5")
    menu = st.radio("Selecione:", ["🎯 Radar Sniper (Triplo)", "📊 Radar Zebra Clássico", "📡 Extração Central"])

if menu == "🎯 Radar Sniper (Triplo)":
    st.title("🎯 Operação Interseção de Múltiplos Filtros")
    st.info("Monitora **Grupos (01-15)**, **Centenas (600-999)** e **Milhares (6000-9999)** simultaneamente.")
    
    banca_ia = st.selectbox("Selecione a Banca para Mapeamento:", list(BANCAS_CONFIG.keys()))
    
    if st.button("INICIAR VARREDURA SNIPER", use_container_width=True, type="primary"):
        with st.spinner("Analisando os 3 filtros nos 5 prêmios..."):
            df = carregar_dados_em_memoria(banca_ia)
            if not df.empty:
                exibir_banner_sorteio(df, banca_ia)
                
                colunas_df = ["P1", "P2", "P3", "P4", "P5"]
                titulos = ["1º PRÊMIO", "2º PRÊMIO", "3º PRÊMIO", "4º PRÊMIO", "5º PRÊMIO"]
                
                # Limites Matemáticos
                LIMITE_GRUPO = 4
                LIMITE_CENTENA = 5
                LIMITE_MILHAR = 5
                
                cols_ui = st.columns(5)
                
                for i in range(5):
                    atr_g, atr_c, atr_m = calcular_atrasos_sniper_triplo(df, colunas_df[i])
                    
                    # Logica de Veredito Triplo
                    if atr_g >= LIMITE_GRUPO and atr_c >= LIMITE_CENTENA and atr_m >= LIMITE_MILHAR:
                        veredito = "<div class='alerta-supremo'>🔥 ALERTA MÁXIMO<br><span style='font-size:10px;font-weight:normal;'>Jogue Grupos + Centenas + Milhares</span></div>"
                    elif atr_g >= LIMITE_GRUPO and atr_m >= LIMITE_MILHAR:
                        veredito = "<div class='alerta-azul'>🔵 ATAQUE MILHAR<br><span style='font-size:10px;font-weight:normal;'>Jogue Grupos e Milhares(6000-9999)</span></div>"
                    elif atr_g >= LIMITE_GRUPO and atr_c >= LIMITE_CENTENA:
                        veredito = "<div class='alerta-verde'>🟢 ATAQUE CENTENA<br><span style='font-size:10px;font-weight:normal;'>Jogue Grupos e Centenas(600-999)</span></div>"
                    elif atr_g >= LIMITE_GRUPO:
                        veredito = "<div class='alerta-amarelo'>🟡 ATAQUE PARCIAL<br><span style='font-size:10px;font-weight:normal;'>Jogue APENAS os Grupos 01-15</span></div>"
                    else:
                        veredito = "<div class='alerta-cinza'>⚪ AGUARDAR<br><span style='font-size:10px;'>Padrão Normal / Grupos Fortes</span></div>"
                        
                    with cols_ui[i]:
                        st.markdown(f"""
                        <div class="sniper-box">
                            <div class="sniper-titulo">{titulos[i]}</div>
                            <div class="sniper-dado">Grupos 01-15: <span class="sniper-valor" style="color:{'#ff4b4b' if atr_g >= LIMITE_GRUPO else '#4CAF50'};">{atr_g}x s/ sair</span></div>
                            <div class="sniper-dado">C: 600-999: <span class="sniper-valor" style="color:{'#ff4b4b' if atr_c >= LIMITE_CENTENA else '#4CAF50'};">{atr_c}x s/ sair</span></div>
                            <div class="sniper-dado">M: 6000-9999: <span class="sniper-valor" style="color:{'#ff4b4b' if atr_m >= LIMITE_MILHAR else '#4CAF50'};">{atr_m}x s/ sair</span></div>
                            {veredito}
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.error("Erro ao carregar base. Execute uma extração primeiro.")

elif menu == "📊 Radar Zebra Clássico":
    st.title("🚨 Radar de Zebras (Sistema Clássico)")
    banca_ia = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    if st.button("VARREDURA DE ZEBRAS", use_container_width=True):
        with st.spinner("Calculando pontuações reais..."):
            df = carregar_dados_em_memoria(banca_ia)
            if not df.empty:
                exibir_banner_sorteio(df, banca_ia)
                df_radar = df.tail(500).reset_index(drop=True)
                colunas_df = ["P1", "P2", "P3", "P4", "P5"]
                titulos = ["1º PRÊMIO", "2º PRÊMIO", "3º PRÊMIO", "4º PRÊMIO", "5º PRÊMIO"]
                cols_ui = st.columns(5)
                for i in range(5):
                    zebras_coluna, pontuacoes = calcular_ranking_por_coluna(df_radar, colunas_df[i])
                    with cols_ui[i]:
                        html = f"<table class='tabela-compacta'>"
                        html += f"<tr><th colspan='2'>🏆 {titulos[i]}</th></tr>"
                        html += f"<tr><td class='td-cabecalho'>GRUPO</td><td class='td-cabecalho'>PONTOS</td></tr>"
                        for grupo in zebras_coluna:
                            pts = pontuacoes[grupo]['total']
                            html += f"<tr><td class='grupo-destaque'>{grupo}</td><td>{pts} pts</td></tr>"
                        html += "</table>"
                        st.markdown(html, unsafe_allow_html=True)
            else:
                st.error("Erro ao carregar base. Execute uma extração.")

elif menu == "📡 Extração Central":
    st.title("📡 Extração e Automação")
    banca_ex = st.selectbox("Banca para Extração:", list(BANCAS_CONFIG.keys()))
    dt = st.date_input("Data do Sorteio:", value=date.today())
    if st.button("🚀 INICIAR COLETA", use_container_width=True):
        with st.spinner("Acessando servidores externos..."):
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
                        st.success(f"✅ Missão Cumprida: {len(p_ins)} novos registros salvos.")
                        carregar_dados_em_memoria.clear() 
                    else:
                        st.info("Todos os dados já estão no banco de dados.")
            else: st.error("Nenhum resultado disponível para esta data.")
