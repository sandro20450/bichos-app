import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import math
import re
from datetime import date, timedelta

# =============================================================================
# --- 1. CONFIGURAÇÕES E ESTILIZAÇÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono V17 - Inteligência", page_icon="🎯", layout="wide")

BANCAS_CONFIG = {
    "Tradicional": {"url": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-"},
    "Caminho da Sorte": {"url": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-"},
    "Monte Carlos": {"url": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-"},
    "Lotep": {"url": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"}
}

st.markdown("""
<style>
    .stApp { background-color: #1e1e1e; color: #f0f0f0; }
    h1, h2, h3 { color: #4CAF50 !important; }
    .stButton > button { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 8px; }
    .metric-card { background-color: #2b2b2b; padding: 15px; border-radius: 10px; border-left: 5px solid #4CAF50; }
    .alerta-sniper { background-color: #2b0000; padding: 20px; border-radius: 10px; text-align: center; color: #ff4b4b; border: 2px solid #ff4b4b; margin-top: 20px; }
    hr { border-color: #4CAF50; opacity: 0.3; }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pentágono - Laboratório de Inteligência V17")

# =============================================================================
# --- 2. MEMÓRIA DE LONGO PRAZO (FREQUÊNCIA E RECORDES) ---
# =============================================================================
if 'stats' not in st.session_state:
    # Inicializa estatísticas para todos os dígitos 0-9
    st.session_state.stats = pd.DataFrame({
        "Dígito": [str(i) for i in range(10)],
        "Frequência": [0] * 10,
        "Recorde de Atraso": [0] * 10
    })

if 'memoria' not in st.session_state:
    st.session_state.memoria = {"ant": pd.DataFrame(), "atu": pd.DataFrame()}

# =============================================================================
# --- 3. MOTORES DE BUSCA E CÁLCULO ---
# =============================================================================
def extrair_dados(banca_nome, data_alvo):
    config = BANCAS_CONFIG[banca_nome]
    data_str = data_alvo.strftime("%Y-%m-%d")
    url = f"{config['url']}{data_str}"
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
            grupos_completos = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhar = nums[0].zfill(4) if nums and len(nums[0]) >= 3 else "----"
                    dezena = int(milhar[-2:]) if milhar != "----" else 0
                    grupo = str(25 if dezena == 0 else math.ceil(dezena/4)).zfill(2) if milhar != "----" else "--"
                    grupos_completos.append(f"{milhar} ({grupo})")
            
            if len(grupos_completos) >= 5:
                resultados.append({"Sorteio": f"{nome} ({data_alvo.strftime('%d/%m')})", "1º": grupos_completos[0], "2º": grupos_completos[1], "3º": grupos_completos[2], "4º": grupos_completos[3], "5º": grupos_completos[4], "Status": "⏳", "Atraso 1": "⏳", "Atraso 2": "⏳"})
        return pd.DataFrame(resultados), "Sucesso"
    except: return None, "Erro de Conexão"

def extrair_grupo(texto):
    if "(" in str(texto): return str(texto).split('(')[-1].replace(')', '').strip()
    return "00"

def extrair_unidades(linha):
    unidades = []
    for p in ["1º", "2º", "3º", "4º", "5º"]:
        val = str(linha.get(p, ""))
        if val and val[0].isdigit(): unidades.append(val.split()[0][-1])
    return unidades

# =============================================================================
# --- 4. INTERFACE E PROCESSAMENTO ---
# =============================================================================
with st.sidebar:
    banca_selecionada = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    if st.button("Limpar Memória de Recordes"):
        st.session_state.stats["Frequência"] = 0
        st.session_state.stats["Recorde de Atraso"] = 0
        st.rerun()

# --- Radar de Atrasos e Estatísticas ---
df_ant = st.session_state.memoria["ant"].copy()
df_atu = st.session_state.memoria["atu"].copy()

atrasos_g1 = {'0': 0, '1': 0, '2': 0, '9': 0}
atrasos_g2 = {'3': 0, '4': 0, '5': 0, '6': 0, '7': 0, '8': 0}

def processar_tabela(df, h_g1, h_g2, anterior_df=None):
    derrotas = 0
    for i in range(len(df)):
        linha = df.iloc[i]
        if not linha["1º"] or "⏳" in str(linha["1º"]): continue
        
        # Unidades
        u_sorteadas = extrair_unidades(linha)
        for digito in u_sorteadas:
            st.session_state.stats.loc[st.session_state.stats["Dígito"] == digito, "Frequência"] += 1
            
        for d in h_g1: h_g1[d] = 0 if d in u_sorteadas else h_g1[d] + 1
        for d in h_g2: h_g2[d] = 0 if d in u_sorteadas else h_g2[d] + 1
        
        # Atualiza Recordes
        for d, atr in {**h_g1, **h_g2}.items():
            rec = st.session_state.stats.loc[st.session_state.stats["Dígito"] == d, "Recorde de Atraso"].values[0]
            if atr > rec: st.session_state.stats.loc[st.session_state.stats["Dígito"] == d, "Recorde de Atraso"] = atr

        # Display Atraso
        d1 = max(h_g1, key=h_g1.get); df.at[i, "Atraso 1"] = f"{d1}-({h_g1[d1]})"
        d2 = max(h_g2, key=h_g2.get); df.at[i, "Atraso 2"] = f"{d2}-({h_g2[d2]})"
        
        # Status Vitória/Derrota
        linha_base = df.iloc[i-1] if i > 0 else (anterior_df.iloc[-1] if anterior_df is not None and not anterior_df.empty else None)
        if linha_base is not None and "⏳" not in str(linha_base["1º"]):
            base = [extrair_grupo(linha_base[f"{p}º"]) for p in [1, 2, 3, 4, 5]]
            a1, a2 = extrair_grupo(linha["1º"]), extrair_grupo(linha["2º"])
            if a1 in base or a2 in base: df.at[i, "Status"] = "🟢 Vitória"; derrotas = 0
            else: df.at[i, "Status"] = "❌ Derrota"; derrotas += 1
    return df, derrotas

# Processamento
df_ant, _ = processar_tabela(df_ant, atrasos_g1, atrasos_g2)
df_atu, d_consec = processar_tabela(df_atu, atrasos_g1, atrasos_g2, df_ant)

# --- Exibição das Tabelas ---
st.markdown("### ⏪ 1. Fechamento Anterior")
data_a = st.date_input("Data Ontem:", value=date.today()-timedelta(days=2))
if st.button("📡 Puxar Ontem"):
    d, m = extrair_dados(banca_selecionada, data_a)
    if d is not None: st.session_state.memoria["ant"] = d.tail(5).reset_index(drop=True); st.rerun()

st.data_editor(df_ant, use_container_width=True, hide_index=True)

st.markdown("### 🎯 2. Operação Atual")
data_p = st.date_input("Data Hoje:", value=date.today()-timedelta(days=1))
if st.button("📡 Puxar Hoje"):
    d, m = extrair_dados(banca_selecionada, data_p); st.session_state.memoria["atu"] = d; st.rerun()

st.data_editor(df_atu, use_container_width=True, hide_index=True)

# --- RELATÓRIO DE INTELIGÊNCIA ---
st.markdown("---")
st.markdown("### 📊 Relatório de Inteligência de Unidades (0-9)")
col_inf1, col_inf2 = st.columns([2, 1])

with col_inf1:
    st.write("Frequência e Recordes de Atraso:")
    st.dataframe(st.session_state.stats.sort_values("Frequência", ascending=False), use_container_width=True, hide_index=True)

with col_inf2:
    st.write("Alvos Sugeridos (Mais Atrasados):")
    d_atr = {**atrasos_g1, **atrasos_g2}
    mais_atrasado = max(d_atr, key=d_atr.get)
    st.metric("Número Crítico", mais_atrasado, f"Atraso: {d_atr[mais_atrasado]}")
    st.info("Acompanhe o 'Recorde de Atraso' para saber se o número está perto do seu limite histórico.")
