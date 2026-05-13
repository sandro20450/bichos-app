import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import numpy as np

# =============================================================================
# --- 1. CONFIGURAÇÕES, CSS E CONEXÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono V57.1 - Radar Compacto", page_icon="🎯", layout="wide")

st.markdown("""
<style>
/* Tabelas Compactas para as Zebras Individuais */
.tabela-compacta { width: 100%; border-collapse: collapse; text-align: center; font-size: 14px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
.tabela-compacta th { background-color: #330000; color: #ff4b4b; padding: 8px; border: 1px solid #444; font-size: 13px; }
.tabela-compacta td { padding: 6px; border: 1px solid #333; color: #fff; background-color: #121212; }
.td-cabecalho { color: #888 !important; font-size: 10px !important; background-color: #000 !important; }
.grupo-destaque { font-weight: bold; color: #4CAF50 !important; font-size: 16px; }

.banner-info { background-color: #0e1117; border: 1px solid #4CAF50; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px; }
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

# =============================================================================
# 🚀 SISTEMA DE CACHE: Mantém a velocidade ultra rápida
# =============================================================================
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

def get_grupo_str(m):
    try:
        d = int(str(m)[-2:])
        return "25" if d == 0 else str(math.ceil(d/4)).zfill(2)
    except: return None

# =============================================================================
# --- MOTOR DE EXTRAÇÃO (PRESERVADO) ---
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
# --- NOVA LÓGICA ULTRA RÁPIDA: ZEBRA INDIVIDUAL POR POSIÇÃO ---
# =============================================================================
def calcular_zebras_por_premio(df, coluna_premio):
    """Calcula matematicamente o atraso de cada grupo em uma coluna específica."""
    grupos_coluna = df[coluna_premio].astype(str).apply(get_grupo_str)
    atrasos = {}
    total_sorteios = len(grupos_coluna)
    
    for g in range(1, 26):
        g_str = str(g).zfill(2)
        # Encontra todos os índices onde este grupo saiu nesta coluna
        ocorrencias = np.where(grupos_coluna == g_str)[0]
        
        if len(ocorrencias) > 0:
            # O último índice é a vez mais recente que ele saiu
            ultimo_idx = ocorrencias[-1]
            atrasos[g_str] = total_sorteios - 1 - ultimo_idx
        else:
            # Se não saiu na janela de análise, o atraso é o total de sorteios
            atrasos[g_str] = total_sorteios
            
    # Ordena do grupo mais atrasado para o menos atrasado
    ranking = sorted(atrasos.items(), key=lambda x: x[1], reverse=True)
    return ranking[:6] # Retorna os 6 mais atrasados (Zebras)

# =============================================================================
# --- INTERFACE DE COMANDO ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=60)
    st.header("Pentágono V57.1")
    menu = st.radio("Selecione:", ["📊 Zebras por Prêmio (1º ao 5º)", "📡 Extração Central"])

if menu == "📊 Zebras por Prêmio (1º ao 5º)":
    st.title("🚨 Radar de Zebras Independentes")
    st.info("As tabelas abaixo mostram os 6 grupos mais atrasados em CADA UMA das 5 posições separadamente.")
    banca_ia = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    
    if st.button("VARREDURA DE ATRASOS (COMPACTA)", use_container_width=True, type="primary"):
        with st.spinner("Mapeando os 5 prêmios..."):
            df = carregar_dados_em_memoria(banca_ia)
            if not df.empty:
                exibir_banner_sorteio(df, banca_ia)
                
                # Vamos focar a matemática nos últimos 800 sorteios (muita precisão)
                df_radar = df.tail(800).reset_index(drop=True)
                
                colunas_df = ["P1", "P2", "P3", "P4", "P5"]
                titulos = ["1º PRÊMIO", "2º PRÊMIO", "3º PRÊMIO", "4º PRÊMIO", "5º PRÊMIO"]
                
                # Cria 5 colunas no Streamlit para colocar as tabelas lado a lado
                cols_ui = st.columns(5)
                
                for i in range(5):
                    # Puxa a matemática para aquela coluna específica (P1, P2...)
                    zebras_do_premio = calcular_zebras_por_premio(df_radar, colunas_df[i])
                    
                    with cols_ui[i]:
                        # Constrói a tabela HTML compacta para o prêmio
                        html = f"<table class='tabela-compacta'>"
                        html += f"<tr><th colspan='2'>🏆 {titulos[i]}</th></tr>"
                        html += f"<tr><td class='td-cabecalho'>GRUPO</td><td class='td-cabecalho'>ATRASO</td></tr>"
                        
                        for grupo, atraso in zebras_do_premio:
                            html += f"<tr><td class='grupo-destaque'>{grupo}</td><td>{atraso}x</td></tr>"
                            
                        html += "</table>"
                        st.markdown(html, unsafe_allow_html=True)
            else:
                st.error("Erro ao carregar base. Execute uma extração primeiro.")

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
