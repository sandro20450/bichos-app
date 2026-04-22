import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import math
import re
from datetime import date, timedelta

# =============================================================================
# --- 1. CONFIGURAÇÕES GERAIS E BANCAS ---
# =============================================================================
st.set_page_config(page_title="Pentágono Multi-Bancas", page_icon="🎯", layout="wide")

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
    .alerta-sniper {
        background-color: #2b0000; padding: 20px; border-radius: 10px; text-align: center;
        color: #ff4b4b; font-size: 1.3em; border: 2px solid #ff4b4b;
        box-shadow: 0px 0px 20px rgba(255, 75, 75, 0.4); margin-top: 20px;
    }
    .alerta-calmo {
        background-color: #002b0c; padding: 15px; border-radius: 10px; text-align: center;
        color: #4CAF50; border: 1px solid #4CAF50; margin-top: 20px;
    }
    hr { border-color: #4CAF50; opacity: 0.3; }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pentágono - Laboratório Multi-Bancas")

# =============================================================================
# --- 2. MOTOR EXTRATOR UNIVERSAL ---
# =============================================================================
def extrair_dados(banca_nome, data_alvo):
    config = BANCAS_CONFIG[banca_nome]
    data_str = data_alvo.strftime("%Y-%m-%d")
    url = f"{config['url']}{data_str}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return None, f"Erro de conexão ({res.status_code})"
        
        soup = BeautifulSoup(res.text, 'html.parser')
        tabelas = soup.find_all('table')
        resultados = []
        count = 1
        
        for tab in tabelas:
            nome_sorteio = ""
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b'])
            txt_prev = prev.get_text(strip=True) if prev else ""
            
            # Escudo Anti-Federal
            texto_tabela = tab.get_text().upper()
            if "FEDERAL" in txt_prev.upper() or "FEDERAL" in texto_tabela:
                continue 
                
            if prev: 
                txt_limpo = txt_prev.upper().replace("RESULTADO", "-").split("-")[0].strip()
                if txt_limpo: nome_sorteio = txt_limpo
            if not nome_sorteio: nome_sorteio = f"Ext. {count}"
                
            grupos_completos = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if not cols: continue
                
                txt_col = cols[0].lower()
                if any(x in txt_col for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    numeros = []
                    for c in cols[1:]: numeros.extend(re.findall(r'\d+', c))
                    
                    milhar, grupo = "", ""
                    for n in numeros:
                        if len(n) >= 3 and not milhar: milhar = n.zfill(4)
                        elif 0 < len(n) <= 2 and not grupo: grupo = n.zfill(2)
                            
                    if not grupo and milhar:
                        dez = int(milhar[-2:])
                        grupo = str(25 if dez == 0 else math.ceil(dez/4)).zfill(2)
                        
                    if not milhar: milhar = "----"
                    if not grupo: grupo = "--"
                    
                    grupos_completos.append(f"{milhar} ({grupo})")
            
            if len(grupos_completos) >= 5:
                resultados.append({
                    "Sorteio": f"{nome_sorteio} ({data_alvo.strftime('%d/%m')})",
                    "1º": grupos_completos[0], "2º": grupos_completos[1], "3º": grupos_completos[2], "4º": grupos_completos[3], "5º": grupos_completos[4],
                    "Status": "⏳",
                    "Atraso": "⏳"
                })
                count += 1
        
        if not resultados: return None, "Nenhuma tabela válida encontrada."
        return pd.DataFrame(resultados), "Sucesso"
    except Exception as e:
        return None, f"Falha no radar: {e}"

# =============================================================================
# --- 3. CONFIGURAÇÃO DE BANCAS E MEMÓRIA ---
# =============================================================================
with st.sidebar:
    st.header("🎮 Configurações")
    banca_selecionada = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))

if 'memoria' not in st.session_state:
    st.session_state.memoria = {"ant": pd.DataFrame(), "atu": pd.DataFrame()}

# --- Funções de Extração para os Cálculos ---
def extrair_grupo(texto):
    txt = str(texto)
    if "(" in txt: return txt.split('(')[-1].replace(')', '').strip().zfill(2)
    nums = re.findall(r'\d+', txt)
    return nums[-1].zfill(2) if nums else "00"

def extrair_unidades(linha):
    """Extrai o último dígito (unidade) de cada milhar da linha (1º ao 5º)."""
    unidades = []
    for p in ["1º", "2º", "3º", "4º", "5º"]:
        v = str(linha.get(p, "")).strip()
        m = re.search(r'^(\d+)', v) # Pega o primeiro bloco numérico (a milhar)
        if m: unidades.append(m.group(1)[-1]) # Extrai a última casa da milhar
    return unidades

# =============================================================================
# --- 4. MOTOR LÓGICO (BACKTEST + RADAR DE ATRASOS) ---
# =============================================================================
df_ant = st.session_state.memoria["ant"].copy()
df_atu = st.session_state.memoria["atu"].copy()

derrotas_consecutivas = 0
# Radar de Atrasos focando exclusivamente nos alvos do Comandante
atrasos_unidades = {'0': 0, '1': 0, '2': 0, '9': 0}

# --- Processa Tabela Anterior ---
if not df_ant.empty:
    df_ant.at[0, "Status"] = "---"
    for i in range(len(df_ant)):
        linha_alvo = df_ant.iloc[i]
        valida = linha_alvo["1º"] and "⏳" not in str(linha_alvo["1º"])
        
        # 1. Atualiza Atrasos da Milhar
        if valida:
            unidades_sorteadas = extrair_unidades(linha_alvo)
            for digito in atrasos_unidades.keys():
                if digito in unidades_sorteadas: atrasos_unidades[digito] = 0
                else: atrasos_unidades[digito] += 1
            
            digito_mais_atrasado = max(sorted(atrasos_unidades.keys()), key=lambda k: atrasos_unidades[k])
            df_ant.at[i, "Atraso"] = f"{digito_mais_atrasado}-({atrasos_unidades[digito_mais_atrasado]})"
        else:
            df_ant.at[i, "Atraso"] = "⏳"
            
        # 2. Atualiza Status Duque (Só do 2º jogo em diante)
        if i > 0:
            linha_base = df_ant.iloc[i-1]
            if not linha_base["1º"] or not valida:
                df_ant.at[i, "Status"] = "⏳"
            else:
                base = [extrair_grupo(linha_base[f"{p}º"]) for p in [1, 2, 3, 4, 5]]
                a1, a2 = extrair_grupo(linha_alvo["1º"]), extrair_grupo(linha_alvo["2º"])
                if a1 in base or a2 in base:
                    df_ant.at[i, "Status"] = "🟢 Vitória"
                    derrotas_consecutivas = 0
                else:
                    df_ant.at[i, "Status"] = "❌ Derrota"
                    derrotas_consecutivas += 1

# --- Processa Tabela Atual ---
if not df_atu.empty:
    for i in range(len(df_atu)):
        linha_alvo = df_atu.iloc[i]
        valida = linha_alvo["1º"] and "⏳" not in str(linha_alvo["1º"])
        
        # 1. Atualiza Atrasos da Milhar (Herdando os atrasos do dia anterior)
        if valida:
            unidades_sorteadas = extrair_unidades(linha_alvo)
            for digito in atrasos_unidades.keys():
                if digito in unidades_sorteadas: atrasos_unidades[digito] = 0
                else: atrasos_unidades[digito] += 1
            
            digito_mais_atrasado = max(sorted(atrasos_unidades.keys()), key=lambda k: atrasos_unidades[k])
            df_atu.at[i, "Atraso"] = f"{digito_mais_atrasado}-({atrasos_unidades[digito_mais_atrasado]})"
        else:
            df_atu.at[i, "Atraso"] = "⏳"

        # 2. Atualiza Status Duque
        if i == 0:
            if not df_ant.empty and "⏳" not in str(df_ant.iloc[-1]["1º"]): linha_base = df_ant.iloc[-1]
            else: 
                df_atu.at[i, "Status"] = "---"
                continue
        else: 
            linha_base = df_atu.iloc[i-1]
        
        if not linha_base["1º"] or not valida:
            df_atu.at[i, "Status"] = "⏳"
            continue
            
        base = [extrair_grupo(linha_base[f"{p}º"]) for p in [1, 2, 3, 4, 5]]
        a1, a2 = extrair_grupo(linha_alvo["1º"]), extrair_grupo(linha_alvo["2º"])
        
        if a1 in base or a2 in base:
            df_atu.at[i, "Status"] = "🟢 Vitória"
            derrotas_consecutivas = 0
        else:
            df_atu.at[i, "Status"] = "❌ Derrota"
            derrotas_consecutivas += 1

st.session_state.memoria["ant"] = df_ant
st.session_state.memoria["atu"] = df_atu

# =============================================================================
# --- 5. RENDERIZAÇÃO DAS TELAS ---
# =============================================================================
st.markdown(f"### ⏪ 1. Fechamento Anterior ({banca_selecionada})")
c1, c2, c3 = st.columns([1, 1, 2])
with c1: data_ant = st.date_input("Data Anterior:", value=date.today() - timedelta(days=2))
with c2: 
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📡 Puxar Histórico", use_container_width=True):
        with st.spinner("Puxando o histórico..."):
            df, msg = extrair_dados(banca_selecionada, data_ant)
            if df is not None:
                st.session_state.memoria["ant"] = df.tail(5).reset_index(drop=True)
                st.rerun()
            else: st.error(msg)
with c3:
    st.markdown("<br><span style='color:#aaa; font-size: 0.8em;'>Atraso focado nas unidades (0, 1, 2, 9).</span>", unsafe_allow_html=True)

df_ant_edit = st.data_editor(st.session_state.memoria["ant"], use_container_width=True, hide_index=True, key="ed_ant", 
                             column_config={"Status": st.column_config.TextColumn(disabled=True), "Atraso": st.column_config.TextColumn(disabled=True)})
if not df_ant.equals(df_ant_edit): 
    st.session_state.memoria["ant"] = df_ant_edit
    st.rerun()

st.markdown("<hr>", unsafe_allow_html=True)

st.markdown(f"### 🎯 2. Operação Atual ({banca_selecionada})")
c4, c5, c6 = st.columns([1, 1, 2])
with c4: data_atu = st.date_input("Data Principal:", value=date.today() - timedelta(days=1))
with c5:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📡 Puxar Dia Principal", use_container_width=True):
        with st.spinner("Puxando extrações completas..."):
            df, msg = extrair_dados(banca_selecionada, data_atu)
            if df is not None:
                st.session_state.memoria["atu"] = df
                st.rerun()
            else: st.error(msg)

df_atu_edit = st.data_editor(st.session_state.memoria["atu"], use_container_width=True, hide_index=True, key="ed_atu", 
                             column_config={"Status": st.column_config.TextColumn(disabled=True), "Atraso": st.column_config.TextColumn("Atraso (0,1,2,9)", disabled=True)})
if not df_atu.equals(df_atu_edit): 
    st.session_state.memoria["atu"] = df_atu_edit
    st.rerun()

if derrotas_consecutivas >= 4:
    st.markdown(f'<div class="alerta-sniper"><b>🚨 OPORTUNIDADE EM {banca_selecionada} 🚨</b><br>{derrotas_consecutivas} derrotas seguidas! Prepare o ataque.</div>', unsafe_allow_html=True)
elif derrotas_consecutivas > 0:
    st.markdown(f'<div class="alerta-calmo" style="color:#ffb74d; border-color:#ffb74d;">Monitorando: {derrotas_consecutivas} derrota(s) consecutiva(s)...</div>', unsafe_allow_html=True)
else:
    if not df_atu.empty or not df_ant.empty:
        st.markdown('<div class="alerta-calmo">Status Estável. Aguardando nova janela estatística.</div>', unsafe_allow_html=True)
