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
st.set_page_config(page_title="Pentágono V24 - Visão Limpa", page_icon="🎯", layout="wide")

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
    hr { border-color: #4CAF50; opacity: 0.3; }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pentágono - Laboratório Multi-Bancas V24")

# =============================================================================
# --- 2. MEMÓRIA E ESTADOS ---
# =============================================================================
if 'raw_ant' not in st.session_state: st.session_state.raw_ant = pd.DataFrame()
if 'raw_atu' not in st.session_state: st.session_state.raw_atu = pd.DataFrame()
if 'memoria' not in st.session_state: st.session_state.memoria = {"ant": pd.DataFrame(), "atu": pd.DataFrame()}

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
                resultados.append({
                    "Sorteio": f"{nome} ({data_alvo.strftime('%d/%m')})", 
                    "1º": grupos[0], "2º": grupos[1], "3º": grupos[2], "4º": grupos[3], "5º": grupos[4], 
                    "Atraso Dez": "⏳", "Atraso Unid": "⏳"
                })
        return pd.DataFrame(resultados), "Sucesso"
    except: return None, "Erro"

def extrair_v24(val, tipo):
    txt = str(val); m = re.search(r'^(\d+)', txt)
    if m:
        num = m.group(1).zfill(4)
        if tipo == 'u': return num[-1]
        if tipo == 'd': return num[-2]
    return None

# =============================================================================
# --- 4. MOTOR LÓGICO CONTÍNUO ---
# =============================================================================
def recalcular_v24():
    st.session_state.stats_unid = pd.DataFrame({"Dígito": [str(i) for i in range(10)], "Frequência": [0]*10, "Recorde": [0]*10})
    st.session_state.stats_dez = pd.DataFrame({"Dígito": [str(i) for i in range(10)], "Frequência": [0]*10, "Recorde": [0]*10})

    hu, hd = {str(i): 0 for i in range(10)}, {str(i): 0 for i in range(10)}

    def processar(df_raw):
        if df_raw.empty: return pd.DataFrame()
        df = df_raw.copy()
        for i in range(len(df)):
            linha = df.iloc[i]
            if not linha["1º"] or "⏳" in str(linha["1º"]): continue
            u_l, d_l = [], []
            for p in ["1º", "2º", "3º", "4º", "5º"]:
                u, d = extrair_v24(linha[p], 'u'), extrair_v24(linha[p], 'd')
                if u: u_l.append(u); st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==u, "Frequência"] += 1
                if d: d_l.append(d); st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Frequência"] += 1
            
            for d in hu: hu[d] = 0 if d in u_l else hu[d]+1
            for d in hd: hd[d] = 0 if d in d_l else hd[d]+1
            
            for u, a in hu.items():
                if a > st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==u, "Recorde"].values[0]: st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==u, "Recorde"] = a
            for d, a in hd.items():
                if a > st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Recorde"].values[0]: st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Recorde"] = a
            
            df.at[i, "Atraso Dez"] = f"{max(hd, key=hd.get)}-({hd[max(hd, key=hd.get)]})"
            df.at[i, "Atraso Unid"] = f"{max(hu, key=hu.get)}-({hu[max(hu, key=hu.get)]})"
        return df

    st.session_state.memoria["ant"] = processar(st.session_state.raw_ant)
    st.session_state.memoria["atu"] = processar(st.session_state.raw_atu)

if st.session_state.raw_ant.empty and st.session_state.raw_atu.empty: recalcular_v24()

# =============================================================================
# --- 5. INTERFACE ---
# =============================================================================
with st.sidebar:
    banca = st.selectbox("Banca:", list(BANCAS_CONFIG.keys()))
    if st.button("Limpar Tudo"): st.session_state.raw_ant = pd.DataFrame(); st.session_state.raw_atu = pd.DataFrame(); recalcular_v24(); st.rerun()

st.markdown("### ⏪ 1. Fechamento Anterior (Últimos 10)")
c1, c2, _ = st.columns([1, 1, 2])
with c1: dt_ant = st.date_input("Data Inicial:", value=date.today()-timedelta(days=2))
with c2: 
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📡 Puxar 10 Resultados"):
        with st.spinner("Escavando histórico..."):
            acumulado = pd.DataFrame()
            data_busca = dt_ant
            tentativas = 0
            while len(acumulado) < 10 and tentativas < 5:
                df, m = extrair_dados(banca, data_busca)
                if df is not None and not df.empty:
                    acumulado = pd.concat([df, acumulado], ignore_index=True)
                data_busca -= timedelta(days=1)
                tentativas += 1
            st.session_state.raw_ant = acumulado.tail(10).reset_index(drop=True)
            recalcular_v24(); st.rerun()
st.data_editor(st.session_state.memoria["ant"], use_container_width=True, hide_index=True)

st.markdown("---")
st.markdown("### 🎯 2. Operação Atual")
c3, c4, _ = st.columns([1, 1, 2])
with c3: dt_atu = st.date_input("Data Hoje:", value=date.today()-timedelta(days=1))
with c4:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📡 Puxar Hoje"):
        d, m = extrair_dados(banca, dt_atu)
        if d is not None: st.session_state.raw_atu = d; recalcular_v24(); st.rerun()
st.data_editor(st.session_state.memoria["atu"], use_container_width=True, hide_index=True)

st.markdown("---")
st.markdown("### 📊 Inteligência Geral (1º ao 5º Prêmio)")
ca, cb = st.columns(2)
with ca: st.write("**FREQUÊNCIA DEZENAS**"); st.dataframe(st.session_state.stats_dez.sort_values("Frequência", ascending=False), hide_index=True)
with cb: st.write("**FREQUÊNCIA UNIDADES**"); st.dataframe(st.session_state.stats_unid.sort_values("Frequência", ascending=False), hide_index=True)
