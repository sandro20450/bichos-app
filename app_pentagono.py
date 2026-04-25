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
st.set_page_config(page_title="Pentágono V20 - Sniper", page_icon="🎯", layout="wide")

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
    .panel-sniper { background-color: #001a00; padding: 20px; border-radius: 15px; border: 2px solid #4CAF50; text-align: center; }
    .numero-destaque { font-size: 2.5em; font-weight: bold; color: #4CAF50; }
    .sub-texto { color: #aaa; font-size: 0.9em; }
    hr { border-color: #4CAF50; opacity: 0.3; }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pentágono - Relatório Sniper V20")

# =============================================================================
# --- 2. MEMÓRIA HISTÓRICA E SNIPER ---
# =============================================================================
if 'stats_unid' not in st.session_state:
    st.session_state.stats_unid = pd.DataFrame({"Dígito": [str(i) for i in range(10)], "Frequência": [0]*10, "Recorde": [0]*10})
if 'stats_dez' not in st.session_state:
    st.session_state.stats_dez = pd.DataFrame({"Dígito": [str(i) for i in range(10)], "Frequência": [0]*10, "Recorde": [0]*10})
if 'memoria' not in st.session_state:
    st.session_state.memoria = {"ant": pd.DataFrame(), "atu": pd.DataFrame()}

# Dicionários de atraso por posição específica (Dezenas)
if 'atraso_p1_dez' not in st.session_state:
    st.session_state.atraso_p1_dez = {str(i): 0 for i in range(10)}
if 'atraso_p2_dez' not in st.session_state:
    st.session_state.atraso_p2_dez = {str(i): 0 for i in range(10)}
if 'freq_p1_p2_dez' not in st.session_state:
    st.session_state.freq_p1_p2_dez = {str(i): 0 for i in range(10)}

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

def extrair_digito_especifico(val, posicao):
    # posicao: -1 para unidade, -2 para dezena
    m = re.search(r'^(\d+)', str(val))
    if m:
        num = m.group(1).zfill(4)
        return num[posicao]
    return None

# =============================================================================
# --- 4. MOTOR LÓGICO E RELATÓRIO SNIPER ---
# =============================================================================
def processar_v20(df):
    hu = {str(i): 0 for i in range(10)}
    hd = {str(i): 0 for i in range(10)}
    
    for i in range(len(df)):
        linha = df.iloc[i]
        if not linha["1º"] or "⏳" in str(linha["1º"]): continue
        
        # Coleta de dígitos da linha (1º ao 5º)
        unids_linha = []
        dezs_linha = []
        for p in ["1º", "2º", "3º", "4º", "5º"]:
            u = extrair_digito_especifico(linha[p], -1)
            d = extrair_digito_especifico(linha[p], -2)
            if u: unids_linha.append(u)
            if d: dezs_linha.append(d)
        
        # Monitoramento Específico Sniper (1º e 2º Prêmio)
        dez_p1 = extrair_digito_especifico(linha["1º"], -2)
        dez_p2 = extrair_digito_especifico(linha["2º"], -2)
        
        if dez_p1:
            for d in st.session_state.atraso_p1_dez:
                st.session_state.atraso_p1_dez[d] = 0 if d == dez_p1 else st.session_state.atraso_p1_dez[d] + 1
            st.session_state.freq_p1_p2_dez[dez_p1] += 1
            
        if dez_p2:
            for d in st.session_state.atraso_p2_dez:
                st.session_state.atraso_p2_dez[d] = 0 if d == dez_p2 else st.session_state.atraso_p2_dez[d] + 1
            st.session_state.freq_p1_p2_dez[dez_p2] += 1

        # Resto das estatísticas (Unidades e Dezenas Gerais)
        for u in unids_linha: st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==u, "Frequência"] += 1
        for d in dezs_linha: st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Frequência"] += 1
        for u in hu: hu[u] = 0 if u in unids_linha else hu[u]+1
        for d in hd: hd[d] = 0 if d in dezs_linha else hd[d]+1
        
        # Recordes
        for u, a in hu.items():
            rec = st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==u, "Recorde"].values[0]
            if a > rec: st.session_state.stats_unid.loc[st.session_state.stats_unid["Dígito"]==u, "Recorde"] = a
        for d, a in hd.items():
            rec = st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Recorde"].values[0]
            if a > rec: st.session_state.stats_dez.loc[st.session_state.stats_dez["Dígito"]==d, "Recorde"] = a
            
        # Colunas
        md = max(hd, key=hd.get); df.at[i, "Atraso Dez"] = f"{md}-({hd[md]})"
        mu = max(hu, key=hu.get); df.at[i, "Atraso Unid"] = f"{mu}-({hu[mu]})"
    return df

# =============================================================================
# --- 5. INTERFACE ---
# =============================================================================
with st.sidebar:
    banca = st.selectbox("Banca:", list(BANCAS_CONFIG.keys()))
    if st.button("Limpar Histórico/Sniper"):
        st.session_state.atraso_p1_dez = {str(i):0 for i in range(10)}
        st.session_state.atraso_p2_dez = {str(i):0 for i in range(10)}
        st.session_state.freq_p1_p2_dez = {str(i):0 for i in range(10)}
        st.session_state.stats_unid["Frequência"]=0; st.session_state.stats_unid["Recorde"]=0
        st.session_state.stats_dez["Frequência"]=0; st.session_state.stats_dez["Recorde"]=0
        st.rerun()

st.markdown("### ⏪ 1. Fechamento Anterior")
c1, c2, _ = st.columns([1, 1, 2])
with c1: dt_ant = st.date_input("Data Ontem:", value=date.today()-timedelta(days=2))
with c2: 
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📡 Puxar Ontem"):
        d, m = extrair_dados(banca, dt_ant)
        if d is not None: st.session_state.memoria["ant"] = processar_v20(d.tail(5).reset_index(drop=True)); st.rerun()

st.data_editor(st.session_state.memoria["ant"], use_container_width=True, hide_index=True)

st.markdown("---")

st.markdown("### 🎯 2. Operação Atual")
c3, c4, _ = st.columns([1, 1, 2])
with c3: dt_atu = st.date_input("Data Hoje:", value=date.today()-timedelta(days=1))
with c4:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📡 Puxar Hoje"):
        d, m = extrair_dados(banca, dt_atu)
        if d is not None: st.session_state.memoria["atu"] = processar_v20(d); st.rerun()

st.data_editor(st.session_state.memoria["atu"], use_container_width=True, hide_index=True)

# =============================================================================
# --- 6. NOVO RELATÓRIO SNIPER (1º E 2º PRÊMIO) ---
# =============================================================================
st.markdown("---")
st.markdown("### 🔭 RELATÓRIO ESTRATÉGICO SNIPER (Dezenas 1º e 2º)")

# Cálculo dos Alvos
p1_rank = sorted(st.session_state.atraso_p1_dez.items(), key=lambda x: x[1], reverse=True)
p2_rank = sorted(st.session_state.atraso_p2_dez.items(), key=lambda x: x[1], reverse=True)
meio_termo_num = max(st.session_state.freq_p1_p2_dez.items(), key=lambda x: x[1])[0]

# Grid do Sniper
col_s1, col_s2, col_s3 = st.columns(3)

with col_s1:
    st.markdown(f"""
    <div class="panel-sniper">
        <div class="sub-texto">MAIS ATRASADOS 1º PRÊMIO</div>
        <div class="numero-destaque">{p1_rank[0][0]} e {p1_rank[1][0]}</div>
        <div class="sub-texto">Atraso: ({p1_rank[0][1]}) e ({p1_rank[1][1]})</div>
    </div>
    """, unsafe_allow_html=True)

with col_s2:
    st.markdown(f"""
    <div class="panel-sniper">
        <div class="sub-texto">MAIS ATRASADOS 2º PRÊMIO</div>
        <div class="numero-destaque">{p2_rank[0][0]} e {p2_rank[1][0]}</div>
        <div class="sub-texto">Atraso: ({p2_rank[0][1]}) e ({p2_rank[1][1]})</div>
    </div>
    """, unsafe_allow_html=True)

with col_s3:
    st.markdown(f"""
    <div class="panel-sniper" style="border-color: #ffb74d;">
        <div class="sub-texto" style="color: #ffb74d;">NÚMERO MEIO TERMO (QUENTE)</div>
        <div class="numero-destaque" style="color: #ffb74d;">{meio_termo_num}</div>
        <div class="sub-texto">Maior frequência no Top 2</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
st.markdown("### 📊 Relatório Geral de Inteligência")
ca, cb = st.columns(2)
with ca: st.write("**DEZENAS (Geral 1-5)**"); st.dataframe(st.session_state.stats_dez.sort_values("Frequência", ascending=False), hide_index=True)
with cb: st.write("**UNIDADES (Geral 1-5)**"); st.dataframe(st.session_state.stats_unid.sort_values("Frequência", ascending=False), hide_index=True)
