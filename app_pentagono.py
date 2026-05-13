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
st.set_page_config(page_title="Pentágono V58.1 - Força-Tarefa", page_icon="🎯", layout="wide")

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
.sniper-dado { font-size: 13px; color: #aaa; margin: 8px 0; line-height: 1.1; }
.sniper-valor { font-weight: bold; font-size: 15px; color: #fff; }
.sniper-recorde { font-size: 10px; color: #666; display: block; margin-top: 2px; }

/* Cores de Alerta */
.alerta-supremo { background-color: #330033; border: 1px solid #ff00ff; color: #ff00ff; padding: 8px; border-radius: 5px; font-weight: bold; margin-top: 15px; font-size: 13px; }
.alerta-verde { background-color: #003300; border: 1px solid #00ff00; color: #00ff00; padding: 8px; border-radius: 5px; font-weight: bold; margin-top: 15px; font-size: 13px; }
.alerta-azul { background-color: #001a33; border: 1px solid #0099ff; color: #0099ff; padding: 8px; border-radius: 5px; font-weight: bold; margin-top: 15px; font-size: 13px; }
.alerta-amarelo { background-color: #332b00; border: 1px solid #ffcc00; color: #ffcc00; padding: 8px; border-radius: 5px; font-weight: bold; margin-top: 15px; font-size: 13px; }
.alerta-cinza { background-color: #222; border: 1px solid #555; color: #888; padding: 8px; border-radius: 5px; font-size: 12px; margin-top: 15px; }

/* Cabeçalhos dos 5 Esquadrões */
.titulo-esquadrao { text-align: center; font-weight: bold; padding: 10px; border-radius: 5px; margin-top: 20px; margin-bottom: 15px; text-transform: uppercase; }
.bg-alpha { background-color: #001f3f; border: 1px solid #0074D9; color: #7FDBFF; }
.bg-bravo { background-color: #3e1f00; border: 1px solid #FF851B; color: #FFDC00; }
.bg-charlie { background-color: #2e003e; border: 1px solid #B10DC9; color: #F012BE; }
.bg-delta { background-color: #003333; border: 1px solid #39CCCC; color: #7FDBFF; }
.bg-echo { background-color: #330000; border: 1px solid #FF4136; color: #FF851B; }
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
# --- MOTOR DO SNIPER (MÉTRICAS DINÂMICAS) ---
# =============================================================================
def calcular_metricas_sniper(df_analise, coluna, g_min, g_max, c_min, c_max, m_min, m_max, janela=50):
    atraso_grupo, atraso_centena, atraso_milhar = 0, 0, 0
    achou_g, achou_c, achou_m = False, False, False
    
    for i in range(len(df_analise)-1, -1, -1):
        milhar = str(df_analise.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "nan" or not milhar.strip(): continue
        
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:])
        except: c = -1
        try: m = int(milhar)
        except: m = -1
            
        if not achou_g:
            if g is not None and g_min <= g <= g_max: achou_g = True
            else: atraso_grupo += 1
        if not achou_c:
            if c_min <= c <= c_max: achou_c = True
            else: atraso_centena += 1
        if not achou_m:
            if m_min <= m <= m_max: achou_m = True
            else: atraso_milhar += 1
            
        if achou_g and achou_c and achou_m: break

    df_janela = df_analise.tail(janela)
    curr_g, curr_c, curr_m = 0, 0, 0
    max_g, max_c, max_m = 0, 0, 0
    
    for i in range(len(df_janela)):
        milhar = str(df_janela.iloc[i][coluna]).zfill(4)
        if milhar == "----" or milhar == "nan" or not milhar.strip(): continue
        
        g = get_grupo_int(milhar)
        try: c = int(milhar[-3:])
        except: c = -1
        try: m = int(milhar)
        except: m = -1
            
        if g is not None and g_min <= g <= g_max: curr_g = 0
        else: curr_g += 1
        if curr_g > max_g: max_g = curr_g
            
        if c_min <= c <= c_max: curr_c = 0
        else: curr_c += 1
        if curr_c > max_c: max_c = curr_c
            
        if m_min <= m <= m_max: curr_m = 0
        else: curr_m += 1
        if curr_m > max_m: max_m = curr_m

    max_g = max(max_g, atraso_grupo)
    max_c = max(max_c, atraso_centena)
    max_m = max(max_m, atraso_milhar)

    return atraso_grupo, atraso_centena, atraso_milhar, max_g, max_c, max_m

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
    st.header("Pentágono V58.1")
    menu = st.radio("Selecione:", ["🎯 Radar Sniper (5 Esquadrões)", "📊 Radar Zebra Clássico", "📡 Extração Central"])

if menu == "🎯 Radar Sniper (5 Esquadrões)":
    st.title("🎯 Centro de Comando de Operações (5 Esquadrões)")
    st.info("Monitoramento tático de 5 zonas matemáticas diferentes de probabilidade. (Todos ajustados para 60% Grupos / 40% Centenas e Milhares).")
    
    banca_ia = st.selectbox("Selecione a Banca para Mapeamento:", list(BANCAS_CONFIG.keys()))
    
    if st.button("INICIAR VARREDURA GERAL", use_container_width=True, type="primary"):
        with st.spinner("Varrendo os 5 Esquadrões em todos os prêmios..."):
            df = carregar_dados_em_memoria(banca_ia)
            if not df.empty:
                exibir_banner_sorteio(df, banca_ia)
                
                colunas_df = ["P1", "P2", "P3", "P4", "P5"]
                titulos = ["1º PRÊMIO", "2º PRÊMIO", "3º PRÊMIO", "4º PRÊMIO", "5º PRÊMIO"]
                
                # Limites base para os Alertas (Mantendo o rigor matemático)
                LIMITE_GRUPO = 4
                LIMITE_CENTENA = 5
                LIMITE_MILHAR = 5
                
                # Configurações dos Esquadrões
                # Todos agora usam exatos 15 Grupos, 400 Centenas e 4000 Milhares
                esquadroes = [
                    (1, 15, 600, 999, 6000, 9999, "bg-alpha", "⚔️ ESQUADRÃO ALPHA (G: 01-15 | C: 600-999 | M: 6000-9999)"),
                    (7, 21, 100, 499, 1000, 4999, "bg-bravo", "⚔️ ESQUADRÃO BRAVO (G: 07-21 | C: 100-499 | M: 1000-4999)"),
                    (11, 25, 0, 399, 0, 3999, "bg-charlie", "⚔️ ESQUADRÃO CHARLIE (G: 11-25 | C: 000-399 | M: 0000-3999)"),
                    (6, 20, 300, 699, 3000, 6999, "bg-delta", "⚔️ ESQUADRÃO DELTA (G: 06-20 | C: 300-699 | M: 3000-6999)"),
                    (4, 18, 500, 899, 5000, 8999, "bg-echo", "⚔️ ESQUADRÃO ECHO (G: 04-18 | C: 500-899 | M: 5000-8999)")
                ]
                
                for cfg in esquadroes:
                    g_min, g_max, c_min, c_max, m_min, m_max, css_class, titulo_esq = cfg
                    
                    st.markdown(f"<div class='titulo-esquadrao {css_class}'>{titulo_esq}</div>", unsafe_allow_html=True)
                    cols = st.columns(5)
                    
                    for i in range(5):
                        atr_g, atr_c, atr_m, max_g, max_c, max_m = calcular_metricas_sniper(df, colunas_df[i], g_min, g_max, c_min, c_max, m_min, m_max)
                        
                        if atr_g >= LIMITE_GRUPO and atr_c >= LIMITE_CENTENA and atr_m >= LIMITE_MILHAR:
                            veredito = "<div class='alerta-supremo'>🔥 ALERTA MÁXIMO<br><span style='font-size:10px;font-weight:normal;'>Jogue Grupos + Centenas + Milhares</span></div>"
                        elif atr_g >= LIMITE_GRUPO and atr_m >= LIMITE_MILHAR:
                            veredito = "<div class='alerta-azul'>🔵 ATAQUE MILHAR<br><span style='font-size:10px;font-weight:normal;'>Jogue Grupos e Milhares</span></div>"
                        elif atr_g >= LIMITE_GRUPO and atr_c >= LIMITE_CENTENA:
                            veredito = "<div class='alerta-verde'>🟢 ATAQUE CENTENA<br><span style='font-size:10px;font-weight:normal;'>Jogue Grupos e Centenas</span></div>"
                        elif atr_g >= LIMITE_GRUPO:
                            veredito = "<div class='alerta-amarelo'>🟡 ATAQUE PARCIAL<br><span style='font-size:10px;font-weight:normal;'>Jogue APENAS os Grupos</span></div>"
                        else:
                            veredito = "<div class='alerta-cinza'>⚪ AGUARDAR<br><span style='font-size:10px;'>Padrão Normal</span></div>"
                            
                        with cols[i]:
                            st.markdown(f"""
                            <div class="sniper-box">
                                <div class="sniper-titulo">{titulos[i]}</div>
                                <div class="sniper-dado">Grupos {str(g_min).zfill(2)}-{str(g_max).zfill(2)}: <span class="sniper-valor" style="color:{'#ff4b4b' if atr_g >= LIMITE_GRUPO else '#4CAF50'};">{atr_g}x</span><span class="sniper-recorde">Rec: {max_g}x</span></div>
                                <div class="sniper-dado">C: {str(c_min).zfill(3)}-{str(c_max).zfill(3)}: <span class="sniper-valor" style="color:{'#ff4b4b' if atr_c >= LIMITE_CENTENA else '#4CAF50'};">{atr_c}x</span><span class="sniper-recorde">Rec: {max_c}x</span></div>
                                <div class="sniper-dado">M: {str(m_min).zfill(4)}-{str(m_max).zfill(4)}: <span class="sniper-valor" style="color:{'#ff4b4b' if atr_m >= LIMITE_MILHAR else '#4CAF50'};">{atr_m}x</span><span class="sniper-recorde">Rec: {max_m}x</span></div>
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
