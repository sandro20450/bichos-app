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
st.set_page_config(page_title="Pentágono V31 - Especialista em Milhar", page_icon="🎯", layout="wide")

def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client.open("CentralBichos")
    except Exception as e:
        st.error(f"Erro na conexão com Google Sheets: {e}")
        return None

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
    .card-tatico { background-color: #001a00; padding: 20px; border-radius: 10px; border: 1px solid #4CAF50; margin-bottom: 15px; }
    .card-alerta { background-color: #2b0000; padding: 20px; border-radius: 10px; border: 1px solid #ff4b4b; margin-bottom: 15px; }
    .titulo-card { color: #ffb74d; font-weight: bold; font-size: 1.25em; margin-bottom: 10px;}
    .dado-destaque { font-size: 2em; font-weight: bold; color: #fff; }
    .label-destaque { color: #4CAF50; font-weight: bold; font-size: 1.1em; }
    .sub-dado { color: #aaa; font-size: 0.9em; margin-left: 10px; }
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
                resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

# =============================================================================
# --- 3. MENU LATERAL ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=80)
    st.header("🎯 Pentágono V31")
    menu = st.radio("Selecione a Base:", ["📡 Extração & Automação", "🔮 Conselheiro Tático (IA)"])

# =============================================================================
# --- 4. TELA 1: EXTRAÇÃO ---
# =============================================================================
if menu == "📡 Extração & Automação":
    st.title("📡 Automação CentralBichos")
    banca_sel = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    dt_alvo = st.date_input("Data do Sorteio:", value=date.today())
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔍 Apenas Visualizar", use_container_width=True):
            dados = extrair_dia(banca_sel, dt_alvo)
            if dados: st.table(pd.DataFrame(dados, columns=["Data", "Horário", "1º", "2º", "3º", "4º", "5º"]))
            else: st.error("Nenhum dado encontrado.")
    with col2:
        if st.button("🚀 EXTRAIR E SALVAR", use_container_width=True):
            with st.spinner("Conectando e salvando..."):
                dados = extrair_dia(banca_sel, dt_alvo)
                if dados:
                    sh = conectar_sheets()
                    if sh:
                        ws = sh.worksheet(MAPA_ABAS[banca_sel])
                        ws.append_rows(dados)
                        st.success(f"✅ {len(dados)} sorteios salvos na aba {MAPA_ABAS[banca_sel]}!")
                else: st.error("Erro ao extrair.")

# =============================================================================
# --- 5. TELA 2: CONSELHEIRO TÁTICO ---
# =============================================================================
elif menu == "🔮 Conselheiro Tático (IA)":
    st.title("🔮 Inteligência Artificial de Combate")
    st.markdown("Análise profunda de **Grupos** e **Unidades de Milhar** baseada no seu histórico.")
    
    link_csv = st.text_input("🔗 Link Público CSV do Google Sheets:")
    
    if link_csv:
        if st.button("Gerar Relatórios de Ataque", use_container_width=True):
            with st.spinner("Varrendo histórico e fatiando milhares..."):
                try:
                    df = pd.read_csv(link_csv, header=None)
                    df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
                    
                    def get_grupo(m):
                        try:
                            d = int(str(m)[-2:])
                            return "25" if d == 0 else str(math.ceil(d/4)).zfill(2)
                        except: return None
                    
                    # ---------------------------------------------------------
                    # CÁLCULO DE ATRASOS E RECORDES
                    # ---------------------------------------------------------
                    atr_g = {str(i).zfill(2): {'t': 0, 'max': 0} for i in range(1, 26)}
                    atr_um = {str(i): {'t': 0, 'max': 0} for i in range(10)} # Unidade de Milhar (1º dígito)
                    
                    for i in range(len(df)):
                        m_str = str(df.iloc[i]["P1"]).zfill(4)
                        if m_str == "nan" or "---" in m_str: continue
                        
                        g_val = get_grupo(m_str)
                        um_val = m_str[0] # 1º dígito
                        
                        if g_val:
                            for k in atr_g:
                                atr_g[k]['t'] = 0 if k == g_val else atr_g[k]['t'] + 1
                                if atr_g[k]['t'] > atr_g[k]['max']: atr_g[k]['max'] = atr_g[k]['t']
                        for k in atr_um:
                            atr_um[k]['t'] = 0 if k == um_val else atr_um[k]['t'] + 1
                            if atr_um[k]['t'] > atr_um[k]['max']: atr_um[k]['max'] = atr_um[k]['t']

                    # ---------------------------------------------------------
                    # MARKOV AUTOMÁTICO (ULTIMO SORTEIO)
                    # ---------------------------------------------------------
                    ult_m = str(df.iloc[-1]["P1"]).zfill(4)
                    ult_g = get_grupo(ult_m)
                    
                    prox_g, prox_um = [], []
                    for i in range(len(df)-1):
                        if get_grupo(str(df.iloc[i]["P1"]).zfill(4)) == ult_g:
                            p_m = str(df.iloc[i+1]["P1"]).zfill(4)
                            prox_g.append(get_grupo(p_m))
                            prox_um.append(p_m[0])
                            
                    t_g = pd.Series(prox_g).mode()[0] if prox_g else "N/A"
                    t_um = pd.Series(prox_um).mode()[0] if prox_um else "N/A"

                    # ---------------------------------------------------------
                    # RENDERS DOS RELATÓRIOS
                    # ---------------------------------------------------------
                    st.success(f"Base Carregada! Analisando após: {ult_m} (Grupo {ult_g})")

                    # PAINEL 1: MARKOV (PREVISÃO)
                    st.markdown(f"""
                    <div class="card-tatico">
                        <div class="titulo-card">🔮 1. Previsor Markov (Próximo Sorteio no 1º Prêmio)</div>
                        Historicamente, após o Grupo <b>{ult_g}</b> sair, a banca costuma soltar:<br><br>
                        <span class="label-destaque">🎯 GRUPO ALVO:</span> <span class="dado-destaque">{t_g}</span><br>
                        <span class="label-destaque">🎯 UNIDADE DE MILHAR ALVO (1º Dígito):</span> <span class="dado-destaque">{t_um}</span>
                    </div>
                    """, unsafe_allow_html=True)

                    # PAINEL 2: PONTO CRÍTICO (ATRASOS)
                    def gerar_alertas(dic, pref):
                        alertas = []
                        for k, v in dic.items():
                            if v['t'] > 0 and v['t'] >= (v['max'] - 2):
                                alertas.append(f"• {pref} **{k}** <span class='sub-dado'>(Atraso: {v['t']} | Recorde: {v['max']})</span>")
                        return "<br>".join(alertas) if alertas else "Tudo sob controle."

                    al_g = gerar_alertas(atr_g, "Grupo")
                    al_um = gerar_alertas(atr_um, "Unid. Milhar")

                    st.markdown(f"""
                    <div class="card-alerta">
                        <div class="titulo-card" style="color:#ff4b4b;">⏳ 2. Alerta de Ponto Crítico (Ruptura)</div>
                        Alvos em zona de risco (perto do recorde máximo de atraso):<br><br>
                        <div style="color:#fff;">
                        <b style="color:#ffb74d;">🦁 GRUPOS:</b><br>{al_g}<br><br>
                        <b style="color:#ffb74d;">🥇 UNIDADES DE MILHAR (1º Dígito):</b><br>{al_um}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Erro no processamento: {e}")
