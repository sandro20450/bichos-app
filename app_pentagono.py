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
st.set_page_config(page_title="Pentágono V22 - Sniper de Grupos", page_icon="🎯", layout="wide")

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
    .panel-sniper { background-color: #001a00; padding: 20px; border-radius: 15px; border: 2px solid #4CAF50; text-align: center; margin-bottom: 10px; }
    .numero-destaque { font-size: 2.2em; font-weight: bold; color: #4CAF50; }
    .sub-texto { color: #aaa; font-size: 0.85em; }
    hr { border-color: #4CAF50; opacity: 0.3; }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pentágono - Estratégia de Grupos V22")

# =============================================================================
# --- 2. MEMÓRIA E ESTADOS SNIPER ---
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

def extrair_v22(val, tipo):
    # tipo: 'u' unidade, 'd' dezena, 'g' grupo
    txt = str(val)
    m = re.search(r'^(\d+)', txt)
    if m:
        num = m.group(1).zfill(4)
        if tipo == 'u': return num[-1]
        if tipo == 'd': return num[-2]
    if tipo == 'g' and "(" in txt:
        return txt.split('(')[-1].replace(')', '').strip()
    return None

# =============================================================================
# --- 4. MOTOR LÓGICO CONTÍNUO V22 ---
# =============================================================================
def recalcular_v22():
    # Reinicialização de Stats
    st.session_state.stats_unid = pd.DataFrame({"Dígito": [str(i) for i in range(10)], "Frequência": [0]*10, "Recorde": [0]*10})
    st.session_state.stats_dez = pd.DataFrame({"Dígito": [str(i) for i in range(10)], "Frequência": [0]*10, "Recorde": [0]*10})
    # Sniper Dezenas
    st.session_state.at_p1_d = {str(i): 0 for i in range(10)}; st.session_state.at_p2_d = {str(i): 0 for i in range(10)}
    st.session_state.fr_p12_d = {str(i): 0 for i in range(10)}
    # Sniper Grupos (01-25)
    st.session_state.at_p1_g = {str(i).zfill(2): 0 for i in range(1, 26)}; st.session_state.at_p2_g = {str(i).zfill(2): 0 for i in range(1, 26)}
    st.session_state.fr_p12_g = {str(i).zfill(2): 0 for i in range(1, 26)}

    hu, hd = {str(i): 0 for i in range(10)}, {str(i): 0 for i in range(10)}

    def processar(df_raw):
        if df_raw.empty: return pd.DataFrame()
        df = df_raw.copy()
        for i in range(len(df)):
            linha = df.iloc[i]
            if not linha["1º"] or "⏳" in str(linha["1º"]): continue
            
            u_l, d_l = [], []
            for p in ["1º", "2º", "3º", "4º", "5º"]:
                u, d = extrair_v22(linha[p], 'u'), extrair_v22(linha[p], 'd')
                if u: u_l.append(u); st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==u, "Frequência"] += 1
                if d: d_l.append(d); st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Frequência"] += 1
            
            for d in hu: hu[d] = 0 if d in u_l else hu[d]+1
            for d in hd: hd[d] = 0 if d in d_l else hd[d]+1
            
            for u, a in hu.items():
                if a > st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==u, "Recorde"].values[0]:
                    st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==u, "Recorde"] = a
            for d, a in hd.items():
                if a > st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Recorde"].values[0]:
                    st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Recorde"] = a
            
            df.at[i, "Atraso Dez"] = f"{max(hd, key=hd.get)}-({hd[max(hd, key=hd.get)]})"
            df.at[i, "Atraso Unid"] = f"{max(hu, key=hu.get)}-({hu[max(hu, key=hu.get)]})"

            # Sniper Lógica (1º e 2º)
            d1, d2 = extrair_v22(linha["1º"], 'd'), extrair_v22(linha["2º"], 'd')
            g1, g2 = extrair_v22(linha["1º"], 'g'), extrair_v22(linha["2º"], 'g')

            if d1: 
                for k in st.session_state.at_p1_d: st.session_state.at_p1_d[k] = 0 if k==d1 else st.session_state.at_p1_d[k]+1
                st.session_state.fr_p12_d[d1] += 1
            if d2:
                for k in st.session_state.at_p2_d: st.session_state.at_p2_d[k] = 0 if k==d2 else st.session_state.at_p2_d[k]+1
                st.session_state.fr_p12_d[d2] += 1
            
            if g1:
                for k in st.session_state.at_p1_g: st.session_state.at_p1_g[k] = 0 if k==g1 else st.session_state.at_p1_g[k]+1
                st.session_state.fr_p12_g[g1] += 1
            if g2:
                for k in st.session_state.at_p2_g: st.session_state.at_p2_g[k] = 0 if k==g2 else st.session_state.at_p2_g[k]+1
                st.session_state.fr_p12_g[g2] += 1
        return df

    st.session_state.memoria["ant"] = processar(st.session_state.raw_ant)
    st.session_state.memoria["atu"] = processar(st.session_state.raw_atu)

if st.session_state.raw_ant.empty and st.session_state.raw_atu.empty: recalcular_v22()

# =============================================================================
# --- 5. INTERFACE ---
# =============================================================================
with st.sidebar:
    banca = st.selectbox("Banca:", list(BANCAS_CONFIG.keys()))
    if st.button("Limpar Tudo"):
        st.session_state.raw_ant = pd.DataFrame(); st.session_state.raw_atu = pd.DataFrame()
        recalcular_v22(); st.rerun()

st.markdown("### ⏪ 1. Fechamento Anterior")
c1, c2, _ = st.columns([1, 1, 2])
with c1: dt_ant = st.date_input("Data Ontem:", value=date.today()-timedelta(days=2))
with c2: 
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📡 Puxar Ontem"):
        d, m = extrair_dados(banca, dt_ant)
        if d is not None: st.session_state.raw_ant = d.tail(5).reset_index(drop=True); recalcular_v22(); st.rerun()
st.data_editor(st.session_state.memoria["ant"], use_container_width=True, hide_index=True)

st.markdown("---")
st.markdown("### 🎯 2. Operação Atual")
c3, c4, _ = st.columns([1, 1, 2])
with c3: dt_atu = st.date_input("Data Hoje:", value=date.today()-timedelta(days=1))
with c4:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📡 Puxar Hoje"):
        d, m = extrair_dados(banca, dt_atu)
        if d is not None: st.session_state.raw_atu = d; recalcular_v22(); st.rerun()
st.data_editor(st.session_state.memoria["atu"], use_container_width=True, hide_index=True)

# =============================================================================
# --- 6. RELATÓRIOS SNIPER (DEZENAS E GRUPOS) ---
# =============================================================================
st.markdown("---")
def render_sniper(titulo, atraso_p1, atraso_p2, freq_p12):
    st.markdown(f"#### {titulo}")
    if sum(freq_p12.values()) > 0:
        r1 = sorted(atraso_p1.items(), key=lambda x: x[1], reverse=True)
        r2 = sorted(atraso_p2.items(), key=lambda x: x[1], reverse=True)
        mt = max(freq_p12.items(), key=lambda x: x[1])[0]
        s1, s2, s3 = st.columns(3)
        with s1: st.markdown(f'<div class="panel-sniper"><div class="sub-texto">1º PRÊMIO</div><div class="numero-destaque">{r1[0][0]} e {r1[1][0]}</div><div class="sub-texto">Atraso: ({r1[0][1]}) e ({r1[1][1]})</div></div>', unsafe_allow_html=True)
        with s2: st.markdown(f'<div class="panel-sniper"><div class="sub-texto">2º PRÊMIO</div><div class="numero-destaque">{r2[0][0]} e {r2[1][0]}</div><div class="sub-texto">Atraso: ({r2[0][1]}) e ({r2[1][1]})</div></div>', unsafe_allow_html=True)
        with s3: st.markdown(f'<div class="panel-sniper" style="border-color:#ffb74d;"><div class="sub-texto" style="color:#ffb74d;">MEIO TERMO (QUENTE)</div><div class="numero-destaque" style="color:#ffb74d;">{mt}</div><div class="sub-texto">Tendência no Top 2</div></div>', unsafe_allow_html=True)
    else: st.info("Aguardando dados para análise Sniper.")

render_sniper("🔭 SNIPER DE DEZENAS (1º e 2º)", st.session_state.at_p1_d, st.session_state.at_p2_d, st.session_state.fr_p12_d)
render_sniper("🦁 SNIPER DE GRUPOS (1º e 2º)", st.session_state.at_p1_g, st.session_state.at_p2_g, st.session_state.fr_p12_g)

st.markdown("---")
st.markdown("### 📊 Inteligência Geral")
ca, cb = st.columns(2)
with ca: st.write("**FREQUÊNCIA DEZENAS**"); st.dataframe(st.session_state.stats_dez.sort_values("Frequência", ascending=False), hide_index=True)
with cb: st.write("**FREQUÊNCIA UNIDADES**"); st.dataframe(st.session_state.stats_unid.sort_values("Frequência", ascending=False), hide_index=True)
