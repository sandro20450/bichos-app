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
st.set_page_config(page_title="Pentágono V18 - Posições", page_icon="🎯", layout="wide")

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
    hr { border-color: #4CAF50; opacity: 0.3; }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pentágono - Inteligência de Posições V18")

# =============================================================================
# --- 2. MEMÓRIA HISTÓRICA (UNIDADES E DEZENAS) ---
# =============================================================================
if 'stats_unid' not in st.session_state:
    st.session_state.stats_unid = pd.DataFrame({"Dígito": [str(i) for i in range(10)], "Frequência": [0]*10, "Recorde": [0]*10})
if 'stats_dez' not in st.session_state:
    st.session_state.stats_dez = pd.DataFrame({"Dígito": [str(i) for i in range(10)], "Frequência": [0]*10, "Recorde": [0]*10})

if 'memoria' not in st.session_state:
    st.session_state.memoria = {"ant": pd.DataFrame(), "atu": pd.DataFrame()}

# =============================================================================
# --- 3. MOTORES DE EXTRAÇÃO ---
# =============================================================================
def extrair_dados(banca_nome, data_alvo):
    config = BANCAS_CONFIG[banca_nome]; data_str = data_alvo.strftime("%Y-%m-%d")
    url = f"{config['url']}{data_str}"; headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser'); tabelas = soup.find_all('table')
        resultados = []
        for tab in tabelas:
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b'])
            txt_prev = prev.get_text().upper() if prev else ""
            if "FEDERAL" in txt_prev or "FEDERAL" in tab.get_text().upper(): continue 
            nome = txt_prev.split("-")[0].strip() if prev else "Sorteio"
            grupos = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhar = nums[0].zfill(4) if nums and len(nums[0]) >= 3 else "----"
                    dez = int(milhar[-2:]) if milhar != "----" else 0
                    g = str(25 if dez == 0 else math.ceil(dez/4)).zfill(2) if milhar != "----" else "--"
                    grupos.append(f"{milhar} ({g})")
            if len(grupos) >= 5:
                resultados.append({"Sorteio": f"{nome} ({data_alvo.strftime('%d/%m')})", "1º": grupos[0], "2º": grupos[1], "3º": grupos[2], "4º": grupos[3], "5º": grupos[4], "Atraso U1": "⏳", "Atraso U2": "⏳", "Atraso Dez": "⏳"})
        return pd.DataFrame(resultados), "Sucesso"
    except: return None, "Erro"

def extrair_digitos(linha):
    unidades, dezenas = [], []
    for p in ["1º", "2º", "3º", "4º", "5º"]:
        val = str(linha.get(p, "")); m = re.search(r'^(\d+)', val)
        if m:
            num = m.group(1).zfill(4)
            unidades.append(num[-1]); dezenas.append(num[-2])
    return unidades, dezenas

# =============================================================================
# --- 4. MOTOR LÓGICO DE ATRASOS E RECORDES ---
# =============================================================================
atr_u1 = {'0':0,'1':0,'2':0,'9':0}; atr_u2 = {'3':0,'4':0,'5':0,'6':0,'7':0,'8':0}; atr_dez = {str(i):0 for i in range(10)}

def processar(df, h1, h2, hd):
    for i in range(len(df)):
        linha = df.iloc[i]
        if not linha["1º"] or "⏳" in str(linha["1º"]): continue
        unids, dezs = extrair_digitos(linha)
        
        # Atualiza Frequências e Atrasos
        for u in unids: st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==u, "Frequência"] += 1
        for d in dezs: st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Frequência"] += 1
        
        for d in h1: h1[d] = 0 if d in unids else h1[d]+1
        for d in h2: h2[d] = 0 if d in unids else h2[d]+1
        for d in hd: hd[d] = 0 if d in dezs else hd[d]+1
        
        # Atualiza Recordes
        for d, a in {**h1, **h2}.items():
            if a > st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==d, "Recorde"].values[0]:
                st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==d, "Recorde"] = a
        for d, a in hd.items():
            if a > st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Recorde"].values[0]:
                st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Recorde"] = a
        
        # Colunas de Atraso
        m1 = max(h1, key=h1.get); df.at[i, "Atraso U1"] = f"{m1}-({h1[m1]})"
        m2 = max(h2, key=h2.get); df.at[i, "Atraso U2"] = f"{m2}-({h2[m2]})"
        md = max(hd, key=hd.get); df.at[i, "Atraso Dez"] = f"{md}-({hd[md]})"
    return df

# Processamento
st.session_state.memoria["ant"] = processar(st.session_state.memoria["ant"].copy(), atr_u1, atr_u2, atr_dez)
st.session_state.memoria["atu"] = processar(st.session_state.memoria["atu"].copy(), atr_u1, atr_u2, atr_dez)

# =============================================================================
# --- 5. INTERFACE ---
# =============================================================================
with st.sidebar:
    banca_selecionada = st.selectbox("Banca:", list(BANCAS_CONFIG.keys()))
    if st.button("Resetar Recordes"): st.session_state.stats_unid["Frequência"]=0; st.session_state.stats_unid["Recorde"]=0; st.session_state.stats_dez["Frequência"]=0; st.session_state.stats_dez["Recorde"]=0; st.rerun()

st.markdown("### ⏪ 1. Fechamento Anterior")
if st.button("📡 Puxar Ontem"):
    d, m = extrair_dados(banca_selecionada, date.today()-timedelta(days=2))
    if d is not None: st.session_state.memoria["ant"] = d.tail(5).reset_index(drop=True); st.rerun()
st.data_editor(st.session_state.memoria["ant"], use_container_width=True, hide_index=True)

st.markdown("### 🎯 2. Operação Atual")
if st.button("📡 Puxar Hoje"):
    d, m = extrair_dados(banca_selecionada, date.today()-timedelta(days=1)); st.session_state.memoria["atu"] = d; st.rerun()
st.data_editor(st.session_state.memoria["atu"], use_container_width=True, hide_index=True)

st.markdown("---")
st.markdown("### 📊 Relatório de Inteligência de Posições (Unidades vs Dezenas)")
col1, col2 = st.columns(2)
with col1:
    st.write("**Estatística: UNIDADES (Último Dígito)**")
    st.dataframe(st.session_state.stats_unid.sort_values("Frequência", ascending=False), use_container_width=True, hide_index=True)
with col2:
    st.write("**Estatística: DEZENAS (Penúltimo Dígito)**")
    st.dataframe(st.session_state.stats_dez.sort_values("Frequência", ascending=False), use_container_width=True, hide_index=True)
