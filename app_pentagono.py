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
    "Tradicional": {
        "url": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-",
    },
    "Caminho da Sorte": {
        "url": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-",
    },
    "Monte Carlos": {
        "url": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-",
    },
    "Lotep": {
        "url": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-",
    }
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
            # Tenta achar o nome/horário blindado contra falhas
            nome_sorteio = ""
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b'])
            if prev: 
                txt = prev.get_text(strip=True)
                txt_limpo = re.split(r'[-|Resultado]', txt)[0].strip()
                if txt_limpo: nome_sorteio = txt_limpo
            
            if not nome_sorteio:
                nome_sorteio = f"Ext. {count}"
                
            grupos = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if not cols: continue
                
                txt_col = cols[0].lower()
                if any(x in txt_col for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    g = ""
                    for c in cols[1:]:
                        n = ''.join(filter(str.isdigit, c))
                        if 0 < len(n) <= 2:
                            g = n.zfill(2)
                            break
                    if not g:
                        for c in cols[1:]:
                            n = ''.join(filter(str.isdigit, c))
                            if len(n) >= 3:
                                dez = int(n[-2:])
                                g = str(25 if dez == 0 else math.ceil(dez/4)).zfill(2)
                                break
                    if g: grupos.append(g)
            
            if len(grupos) >= 5:
                resultados.append({
                    "Sorteio": f"{nome_sorteio} ({data_alvo.strftime('%d/%m')})",
                    "1º": grupos[0], "2º": grupos[1], "3º": grupos[2], "4º": grupos[3], "5º": grupos[4],
                    "Status": "⏳"
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
    st.info(f"O sistema irá adaptar os horários para {banca_selecionada}.")

if 'memoria' not in st.session_state:
    st.session_state.memoria = {"ant": pd.DataFrame(), "atu": pd.DataFrame()}

# =============================================================================
# --- 4. MOTOR LÓGICO DE BACKTEST (EXECUÇÃO PRÉ-RENDER) ---
# =============================================================================
# A MÁGICA: O cálculo agora acontece ANTES de desenhar as tabelas na tela
df_ant = st.session_state.memoria["ant"].copy()
df_atu = st.session_state.memoria["atu"].copy()
derrotas_consecutivas = 0

# Avalia Tabela Anterior
if not df_ant.empty:
    df_ant.at[0, "Status"] = "---"
    for i in range(1, len(df_ant)):
        linha_base = df_ant.iloc[i-1]
        linha_alvo = df_ant.iloc[i]
        
        if not linha_base["1º"] or not linha_alvo["1º"]:
            df_ant.at[i, "Status"] = "⏳"
            continue
            
        base = [str(linha_base[f"{p}º"]) for p in [1, 2, 3, 4, 5]]
        a1, a2 = str(linha_alvo["1º"]), str(linha_alvo["2º"])
        
        if a1 in base or a2 in base:
            df_ant.at[i, "Status"] = "🟢 Vitória"
            derrotas_consecutivas = 0
        else:
            df_ant.at[i, "Status"] = "❌ Derrota"
            derrotas_consecutivas += 1

# Avalia Tabela Atual
if not df_atu.empty:
    for i in range(len(df_atu)):
        if i == 0:
            if not df_ant.empty: linha_base = df_ant.iloc[-1]
            else: 
                df_atu.at[i, "Status"] = "---"
                continue
        else: 
            linha_base = df_atu.iloc[i-1]
        
        linha_alvo = df_atu.iloc[i]
        
        if not linha_base["1º"] or not linha_alvo["1º"]:
            df_atu.at[i, "Status"] = "⏳"
            continue
            
        base = [str(linha_base[f"{p}º"]) for p in [1, 2, 3, 4, 5]]
        a1, a2 = str(linha_alvo["1º"]), str(linha_alvo["2º"])
        
        if a1 in base or a2 in base:
            df_atu.at[i, "Status"] = "🟢 Vitória"
            derrotas_consecutivas = 0
        else:
            df_atu.at[i, "Status"] = "❌ Derrota"
            derrotas_consecutivas += 1

# Salva os status calculados de volta na memória
st.session_state.memoria["ant"] = df_ant
st.session_state.memoria["atu"] = df_atu

# =============================================================================
# --- 5. RENDERIZAÇÃO DA INTERFACE (TELAS) ---
# =============================================================================
# --- Painel Anterior ---
st.markdown(f"### ⏪ 1. Fechamento Anterior ({banca_selecionada})")
c1, c2, c3 = st.columns([1, 1, 2])
with c1: 
    data_ant = st.date_input("Data Anterior:", value=date.today() - timedelta(days=2))
with c2: 
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📡 Puxar Histórico", use_container_width=True):
        with st.spinner("Puxando o histórico de ontem..."):
            df, msg = extrair_dados(banca_selecionada, data_ant)
            if df is not None:
                st.session_state.memoria["ant"] = df.tail(5).reset_index(drop=True)
                st.rerun()
            else: st.error(msg)
with c3:
    st.markdown("<br><span style='color:#aaa; font-size: 0.8em;'>Puxa apenas os últimos 5 sorteios.</span>", unsafe_allow_html=True)

# Tabela superior finalmente desenhada
df_ant_edit = st.data_editor(st.session_state.memoria["ant"], use_container_width=True, hide_index=True, key="ed_ant", column_config={"Status": st.column_config.TextColumn(disabled=True)})
if not df_ant.equals(df_ant_edit): # Se o usuário editar, recalcula
    st.session_state.memoria["ant"] = df_ant_edit
    st.rerun()

st.markdown("<hr>", unsafe_allow_html=True)

# --- Painel Principal ---
st.markdown(f"### 🎯 2. Operação Atual ({banca_selecionada})")
c4, c5, c6 = st.columns([1, 1, 2])
with c4: 
    data_atu = st.date_input("Data Principal:", value=date.today() - timedelta(days=1))
with c5:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📡 Puxar Dia Principal", use_container_width=True):
        with st.spinner("Puxando extrações completas..."):
            df, msg = extrair_dados(banca_selecionada, data_atu)
            if df is not None:
                st.session_state.memoria["atu"] = df
                st.rerun()
            else: st.error(msg)
with c6:
    st.markdown("<br><span style='color:#aaa; font-size: 0.8em;'>Tabela principal da operação.</span>", unsafe_allow_html=True)

# Tabela inferior finalmente desenhada
df_atu_edit = st.data_editor(st.session_state.memoria["atu"], use_container_width=True, hide_index=True, key="ed_atu", column_config={"Status": st.column_config.TextColumn(disabled=True)})
if not df_atu.equals(df_atu_edit): # Se o usuário editar, recalcula
    st.session_state.memoria["atu"] = df_atu_edit
    st.rerun()

# --- Alerta Sniper ---
if derrotas_consecutivas >= 4:
    st.markdown(f'<div class="alerta-sniper"><b>🚨 OPORTUNIDADE EM {banca_selecionada} 🚨</b><br>{derrotas_consecutivas} derrotas seguidas! Prepare o ataque.</div>', unsafe_allow_html=True)
elif derrotas_consecutivas > 0:
    st.markdown(f'<div class="alerta-calmo" style="color:#ffb74d; border-color:#ffb74d;">Monitorando: {derrotas_consecutivas} derrota(s) consecutiva(s)...</div>', unsafe_allow_html=True)
else:
    # Mostra verde se houver dados
    if not df_atu.empty or not df_ant.empty:
        st.markdown('<div class="alerta-calmo">Status Estável. Aguardando nova janela estatística.</div>', unsafe_allow_html=True)
