import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =============================================================================
# --- 1. CONFIGURAÇÕES E CONEXÃO GOOGLE SHEETS ---
# =============================================================================
st.set_page_config(page_title="Pentágono V28.1 - Automação Sheets", page_icon="🎯", layout="wide")

# Função para conectar na planilha CentralBichos
def conectar_sheets():
    try:
        # Pega as credenciais dos Secrets do Streamlit
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        # Abre a planilha
        return client.open("CentralBichos")
    except Exception as e:
        st.error(f"Erro na conexão com Google Sheets: {e}")
        return None

# --- CORREÇÃO TÁTICA: NOVO MAPA DE ABAS (FOCO EM MILHAR) ---
MAPA_ABAS = {
    "Tradicional": "TRADICIONAL_MILHAR",
    "Caminho da Sorte": "CAMINHO_MILHAR",
    "Monte Carlos": "MONTE_MILHAR",
    "Lotep": "LOTEP_MILHAR"
}

st.markdown("""
<style>
    .stApp { background-color: #1e1e1e; color: #f0f0f0; }
    h1, h2, h3 { color: #4CAF50 !important; }
    .stButton > button { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 8px; }
    hr { border-color: #4CAF50; opacity: 0.3; }
</style>
""", unsafe_allow_html=True)

BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-",
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-",
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-",
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

# =============================================================================
# --- 2. MOTORES DE EXTRAÇÃO ---
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
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b'])
            txt_prev = prev.get_text().upper() if prev else ""
            if "FEDERAL" in txt_prev or "FEDERAL" in tab.get_text().upper(): continue 
            nome = txt_prev.split("-")[0].strip() if prev else "Sorteio"
            
            milhares = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhar = nums[0].zfill(4) if nums and len(nums[0]) >= 3 else "----"
                    milhares.append(milhar)
                    
            if len(milhares) >= 5:
                # Formato final para a planilha: Data, Horário, 1º, 2º, 3º, 4º, 5º
                resultados.append([
                    data_alvo.strftime('%Y-%m-%d'),
                    nome,
                    milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]
                ])
        return resultados
    except: return []

# =============================================================================
# --- 3. MENU LATERAL ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=80)
    st.header("🎯 Pentágono V28.1")
    menu = st.radio("Selecione a Operação:", ["📡 Extração & Automação", "🧠 Oráculo de Padrões"])

# =============================================================================
# --- 4. TELA 1: EXTRAÇÃO E SALVAMENTO AUTOMÁTICO ---
# =============================================================================
if menu == "📡 Extração & Automação":
    st.title("📡 Automação CentralBichos")
    banca_sel = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    dt_alvo = st.date_input("Data do Sorteio:", value=date.today())
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔍 Apenas Visualizar", use_container_width=True):
            dados = extrair_dia(banca_sel, dt_alvo)
            if dados:
                df = pd.DataFrame(dados, columns=["Data", "Horário", "1º", "2º", "3º", "4º", "5º"])
                st.table(df)
            else: st.error("Nenhum dado encontrado.")

    with col2:
        if st.button("🚀 EXTRAIR E SALVAR NA PLANILHA", use_container_width=True):
            with st.spinner("Conectando e salvando..."):
                dados = extrair_dia(banca_sel, dt_alvo)
                if dados:
                    sh = conectar_sheets()
                    if sh:
                        aba_nome = MAPA_ABAS[banca_sel]
                        ws = sh.worksheet(aba_nome)
                        ws.append_rows(dados)
                        st.success(f"✅ {len(dados)} sorteios salvos com sucesso na aba {aba_nome}!")
                else: st.error("Erro ao extrair dados do site.")

# =============================================================================
# --- 5. TELA 2: ORÁCULO DE MARKOV ---
# =============================================================================
elif menu == "🧠 Oráculo de Padrões":
    st.title("🧠 Oráculo de Markov")
    link_csv = st.text_input("🔗 Link CSV da Planilha (para leitura):")
    if link_csv:
        try:
            df_sheets = pd.read_csv(link_csv, header=None)
            df_sheets.columns = [f"Col {i}" for i in range(len(df_sheets.columns))]
            st.success(f"✅ Histórico Carregado: {len(df_sheets)} linhas.")
            
            col_gat = st.selectbox("Coluna do Gatilho:", df_sheets.columns)
            val_gat = st.text_input("Número Gatilho:")
            col_som = st.selectbox("Coluna da Sombra (Próximo Jogo):", df_sheets.columns)
            
            if st.button("Caçar Padrões"):
                if val_gat:
                    resultados = []
                    for i in range(len(df_sheets)-1):
                        if str(val_gat) in str(df_sheets.iloc[i][col_gat]):
                            res = str(df_sheets.iloc[i+1][col_som])
                            if res and res.lower() != 'nan': resultados.append(res)
                    if resultados:
                        freq = pd.Series(resultados).value_counts().reset_index()
                        freq.columns = ["O Que Saiu no Sorteio Seguinte", "Frequência (Vezes)"]
                        st.markdown(f"**ALERTA:** Gatilho encontrado {len(resultados)} vezes!")
                        st.dataframe(freq.head(10), use_container_width=True, hide_index=True)
                    else: st.warning("Nada encontrado para este gatilho no sorteio seguinte.")
                else:
                    st.error("Digite o número do gatilho!")
        except Exception as e: st.error(f"Erro ao carregar link CSV: {e}")
