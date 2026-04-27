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
st.set_page_config(page_title="Pentágono V25 - Quadrantes", page_icon="🎯", layout="wide")

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
    .quad-card { background-color: #001a00; padding: 15px; border-radius: 10px; border: 1px solid #4CAF50; text-align: center; }
    .quad-alvo { background-color: #2b0000; padding: 15px; border-radius: 10px; border: 2px solid #ff4b4b; text-align: center; box-shadow: 0px 0px 15px rgba(255, 75, 75, 0.3); }
    .quad-titulo { font-size: 1.2em; font-weight: bold; color: #fff; margin-bottom: 5px; }
    .quad-dezenas { font-size: 0.85em; color: #aaa; margin-bottom: 10px; }
    .quad-metric { font-size: 1.8em; font-weight: bold; color: #4CAF50; }
    .quad-metric-alvo { font-size: 1.8em; font-weight: bold; color: #ff4b4b; }
    hr { border-color: #4CAF50; opacity: 0.3; }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pentágono - Laboratório Multi-Bancas V25")

# =============================================================================
# --- 2. MEMÓRIA E ESTADOS ---
# =============================================================================
if 'raw_ant' not in st.session_state: st.session_state.raw_ant = pd.DataFrame()
if 'raw_atu' not in st.session_state: st.session_state.raw_atu = pd.DataFrame()
if 'memoria' not in st.session_state: st.session_state.memoria = {"ant": pd.DataFrame(), "atu": pd.DataFrame()}
if 'atraso_quad' not in st.session_state: st.session_state.atraso_quad = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
if 'freq_quad' not in st.session_state: st.session_state.freq_quad = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}

# =============================================================================
# --- 3. MOTORES DE EXTRAÇÃO E CLASSIFICAÇÃO ---
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

def extrair_v25(val, tipo):
    txt = str(val); m = re.search(r'^(\d+)', txt)
    if m:
        num = m.group(1).zfill(4)
        if tipo == 'u': return num[-1]
        if tipo == 'd': return num[-2]
        if tipo == 'dc': return num[-2:] # Dezena Completa
    return None

# =============================================================================
# --- 4. MOTOR LÓGICO CONTÍNUO (COM QUADRANTES) ---
# =============================================================================
def recalcular_v25():
    st.session_state.stats_unid = pd.DataFrame({"Dígito": [str(i) for i in range(10)], "Frequência": [0]*10, "Recorde": [0]*10})
    st.session_state.stats_dez = pd.DataFrame({"Dígito": [str(i) for i in range(10)], "Frequência": [0]*10, "Recorde": [0]*10})
    st.session_state.freq_quad = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}

    hu, hd = {str(i): 0 for i in range(10)}, {str(i): 0 for i in range(10)}
    hq = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}

    def processar(df_raw):
        if df_raw.empty: return pd.DataFrame()
        df = df_raw.copy()
        for i in range(len(df)):
            linha = df.iloc[i]
            if not linha["1º"] or "⏳" in str(linha["1º"]): continue
            
            u_l, d_l, q_l = [], [], []
            for p in ["1º", "2º", "3º", "4º", "5º"]:
                u = extrair_v25(linha[p], 'u')
                d = extrair_v25(linha[p], 'd')
                dc = extrair_v25(linha[p], 'dc')
                
                if u: u_l.append(u); st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==u, "Frequência"] += 1
                if d: d_l.append(d); st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Frequência"] += 1
                if dc:
                    d_int, u_int = int(dc[0]), int(dc[1])
                    if d_int < 5 and u_int < 5: q_l.append("Q1")
                    elif d_int < 5 and u_int >= 5: q_l.append("Q2")
                    elif d_int >= 5 and u_int < 5: q_l.append("Q3")
                    elif d_int >= 5 and u_int >= 5: q_l.append("Q4")

            for x in hu: hu[x] = 0 if x in u_l else hu[x]+1
            for x in hd: hd[x] = 0 if x in d_l else hd[x]+1
            for q in hq: hq[q] = 0 if q in q_l else hq[q]+1
            
            for q in q_l: st.session_state.freq_quad[q] += 1
            
            for x, a in hu.items():
                if a > st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==x, "Recorde"].values[0]: st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==x, "Recorde"] = a
            for x, a in hd.items():
                if a > st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==x, "Recorde"].values[0]: st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==x, "Recorde"] = a
            
            df.at[i, "Atraso Dez"] = f"{max(hd, key=hd.get)}-({hd[max(hd, key=hd.get)]})"
            df.at[i, "Atraso Unid"] = f"{max(hu, key=hu.get)}-({hu[max(hu, key=hu.get)]})"
        return df

    st.session_state.memoria["ant"] = processar(st.session_state.raw_ant)
    st.session_state.memoria["atu"] = processar(st.session_state.raw_atu)
    st.session_state.atraso_quad = hq.copy()

if st.session_state.raw_ant.empty and st.session_state.raw_atu.empty: recalcular_v25()

# =============================================================================
# --- 5. INTERFACE ---
# =============================================================================
with st.sidebar:
    banca = st.selectbox("Banca:", list(BANCAS_CONFIG.keys()))
    if st.button("Limpar Tudo"): st.session_state.raw_ant = pd.DataFrame(); st.session_state.raw_atu = pd.DataFrame(); recalcular_v25(); st.rerun()

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
            recalcular_v25(); st.rerun()
st.data_editor(st.session_state.memoria["ant"], use_container_width=True, hide_index=True)

st.markdown("---")
st.markdown("### 🎯 2. Operação Atual")
c3, c4, _ = st.columns([1, 1, 2])
with c3: dt_atu = st.date_input("Data Hoje:", value=date.today()-timedelta(days=1))
with c4:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📡 Puxar Hoje"):
        d, m = extrair_dados(banca, dt_atu)
        if d is not None: st.session_state.raw_atu = d; recalcular_v25(); st.rerun()
st.data_editor(st.session_state.memoria["atu"], use_container_width=True, hide_index=True)

# =============================================================================
# --- 6. NOVO RELATÓRIO: FILTRO DE QUADRANTES ---
# =============================================================================
st.markdown("---")
st.markdown("### ✂️ Filtro de Quadrantes (A Grade de Exclusão)")
st.markdown("<p style='color:#aaa;'>Seu alvo tático: Elimine 75% da tabela focando apenas no <b>Quadrante em Alerta</b> (Maior Atraso).</p>", unsafe_allow_html=True)

quad_info = {
    "Q1": {"nome": "Baixo-Baixo", "dezenas": "00-04, 10-14 ... 40-44"},
    "Q2": {"nome": "Baixo-Alto", "dezenas": "05-09, 15-19 ... 45-49"},
    "Q3": {"nome": "Alto-Baixo", "dezenas": "50-54, 60-64 ... 90-94"},
    "Q4": {"nome": "Alto-Alto", "dezenas": "55-59, 65-69 ... 95-99"}
}

if sum(st.session_state.freq_quad.values()) > 0:
    max_atraso = max(st.session_state.atraso_quad.values())
    cols = st.columns(4)
    
    for idx, q in enumerate(["Q1", "Q2", "Q3", "Q4"]):
        atraso = st.session_state.atraso_quad[q]
        freq = st.session_state.freq_quad[q]
        
        css_class = "quad-alvo" if atraso == max_atraso else "quad-card"
        metric_class = "quad-metric-alvo" if atraso == max_atraso else "quad-metric"
        alerta_txt = "<div style='color:#ff4b4b; font-weight:bold; font-size:0.8em; margin-bottom:5px;'>🚨 ALVO DE ATAQUE</div>" if atraso == max_atraso else ""
        
        with cols[idx]:
            st.markdown(f"""
            <div class="{css_class}">
                {alerta_txt}
                <div class="quad-titulo">{q}: {quad_info[q]['nome']}</div>
                <div class="quad-dezenas">Ex: {quad_info[q]['dezenas']}</div>
                <div style="color:#ccc; font-size: 0.9em;">Atraso Atual</div>
                <div class="{metric_class}">{atraso}</div>
                <div style="color:#aaa; font-size: 0.8em; margin-top:5px;">Frequência: {freq}</div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("Puxe os dados das tabelas acima para renderizar a Grade de Exclusão.")

st.markdown("---")
st.markdown("### 📊 Inteligência Geral (1º ao 5º Prêmio)")
ca, cb = st.columns(2)
with ca: st.write("**FREQUÊNCIA DEZENAS**"); st.dataframe(st.session_state.stats_dez.sort_values("Frequência", ascending=False), hide_index=True)
with cb: st.write("**FREQUÊNCIA UNIDADES**"); st.dataframe(st.session_state.stats_unid.sort_values("Frequência", ascending=False), hide_index=True)
