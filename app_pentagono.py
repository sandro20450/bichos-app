import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import itertools
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import LabelEncoder
import os
import base64

# =============================================================================
# --- 1. CONFIGURAÇÕES, CSS E CONEXÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono IA - Cobertura 12", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.flex-container { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-start; margin-bottom: 20px; }
.grupo-card { background-color: #001a00; border: 1px solid #4CAF50; border-radius: 6px; padding: 8px; text-align: center; flex: 1 1 60px; max-width: 90px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.grupo-card-zebra { background-color: #330000; border: 1px solid #ff4b4b; border-radius: 6px; padding: 8px; text-align: center; flex: 1 1 60px; max-width: 90px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.grupo-numero { font-size: 20px; font-weight: bold; color: #ffffff; margin: 3px 0; }
.grupo-pontos { font-size: 11px; color: #4CAF50; font-weight: bold; }
.grupo-pontos-zebra { font-size: 11px; color: #ff4b4b; font-weight: bold; }
.grupo-posicao { font-size: 9px; color: #aaaaaa; text-transform: uppercase; }
.backtest-box { background-color: #1a2634; padding: 10px; border-radius: 5px; border-left: 4px solid #2196F3; margin-bottom: 10px;}

/* Estilo para os cards de previsão da IA expandido para 12 */
.previsao-card { background-color: #001a00; border: 1px solid #4CAF50; border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 10px; min-height: 120px; }
.previsao-num { font-size: 28px; font-weight: bold; color: #4CAF50; line-height: 1.1; }
.previsao-chance { font-size: 12px; color: #aaa; }
.bicho-nome { font-size: 14px; color: #fff; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client.open("CentralBichos")
    except Exception as e:
        st.error(f"Erro na conexão com Google Sheets: {e}")
        return None

def salvar_sem_duplicar(ws, dados_novos):
    try:
        existentes = ws.get_all_values()
        set_existentes = set()
        for row in existentes:
            if len(row) >= 2:
                set_existentes.add(f"{str(row[0]).strip()}_{str(row[1]).strip()}")
        para_inserir = []
        duplicados = 0
        for linha in dados_novos:
            chave = f"{str(linha[0]).strip()}_{str(linha[1]).strip()}"
            if chave in set_existentes: duplicados += 1
            else:
                para_inserir.append(linha)
                set_existentes.add(chave)
        if para_inserir: ws.append_rows(para_inserir, value_input_option="RAW")
        return len(para_inserir), duplicados
    except: return 0, 0

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

def get_grupo_int(m):
    try:
        d = int(str(m)[-2:])
        return 25 if d == 0 else math.ceil(d/4)
    except: return None

def get_grupo_str(m):
    try:
        d = int(str(m)[-2:])
        return "25" if d == 0 else str(math.ceil(d/4)).zfill(2)
    except: return None

# =============================================================================
# --- 2. MENU E EXTRAÇÃO ---
# =============================================================================
# (Omitido para brevidade, manter exatamente igual ao V56.5 anterior)
# ... [Funções extrair_dia, etc.] ...

# =============================================================================
# --- 3. LOGICA IA PENTÁGONO (XGBOOST EXPANDIDO PARA 12) ---
# =============================================================================

# Dicionário de Bichos para exibição
BICHOS_DICT = {
    1:"Avestruz", 2:"Águia", 3:"Burro", 4:"Borboleta", 5:"Cachorro",
    6:"Cabra", 7:"Carneiro", 8:"Camelo", 9:"Cobra", 10:"Coelho",
    11:"Cavalo", 12:"Elefante", 13:"Galo", 14:"Gato", 15:"Jacaré",
    16:"Leão", 17:"Macaco", 18:"Porco", 19:"Pavão", 20:"Peru",
    21:"Touro", 22:"Tigre", 23:"Urso", 24:"Veado", 25:"Vaca"
}

# (Manter Menu Lateral e Telas 1 e 2 conforme versão anterior)
# ... [Lógica de Extração e Estatística Tradicional] ...

# =============================================================================
# --- 6. TELA 3: CÉREBRO IA PENTÁGONO (XGBOOST - 12 ALVOS) ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=80)
    st.header("🎯 Pentágono V56.5")
    menu = st.radio("Selecione a Base:", ["📡 Extração & Automação", "📊 Estatística Tradicional", "🤖 Radar IA Pentágono (XGBoost)"])

if menu == "🤖 Radar IA Pentágono (XGBoost)":
    st.title("🤖 Radar Preditivo Pentágono (12 Alvos IA)")
    banca_xgb = st.selectbox("Selecione a Banca Alvo para Previsão IA:", list(BANCAS_CONFIG.keys()), key="sel_banca_xgb")
    
    st.info("💡 Radar apontado exclusivamente para o 1º prêmio. O sistema agora exibe os 12 grupos com maior força estatística baseada em Gradiente Boosting.")
    
    if st.button("🚀 Ativar Cérebro Pentágono (Treinar IA)", use_container_width=True, type="primary"):
        with st.spinner("Calibrando IA para busca de 12 padrões..."):
            try:
                sh = conectar_sheets()
                if sh:
                    ws = sh.worksheet(MAPA_ABAS[banca_xgb])
                    dados_brutos = ws.get_all_values()
                    
                    if len(dados_brutos) < 50:
                        st.error("⚠️ Dados insuficientes (mínimo 50 sorteios).")
                    else:
                        df = pd.DataFrame(dados_brutos)
                        df = df.iloc[:, :7]
                        df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
                        df = df[df["P1"].astype(str).str.strip() != ""]
                        df['grupo_alvo'] = df['P1'].apply(get_grupo_int)
                        df = df.dropna(subset=['grupo_alvo']).copy()
                        
                        # Engenharia de Atributos
                        df['ant_1'] = df['grupo_alvo'].shift(1)
                        df['ant_2'] = df['grupo_alvo'].shift(2)
                        df['ant_3'] = df['grupo_alvo'].shift(3)
                        df_treino = df.dropna().tail(500)
                        
                        X = df_treino[['ant_1', 'ant_2', 'ant_3']]
                        y = df_treino['grupo_alvo']
                        
                        le = LabelEncoder()
                        y_encoded = le.fit_transform(y)
                        
                        modelo = xgb.XGBClassifier(objective='multi:softprob', n_estimators=100, max_depth=4, learning_rate=0.1)
                        modelo.fit(X, y_encoded)
                        
                        # Previsão dos 12 melhores
                        ultimos_3 = df['grupo_alvo'].tail(3).values
                        if len(ultimos_3) == 3:
                            entrada = pd.DataFrame({'ant_1':[ultimos_3[2]], 'ant_2':[ultimos_3[1]], 'ant_3':[ultimos_3[0]]})
                            probabilidades = modelo.predict_proba(entrada)[0]
                            
                            # TÁTICA: Pegamos os 12 maiores
                            top_12_idx = np.argsort(probabilidades)[::-1][:12]
                            
                            st.success(f"✅ Inteligência Calibrada! Alvos Localizados.")
                            st.markdown("### 🔮 Projeção dos 12 Grupos Mais Quentes (1º Prêmio):")
                            
                            # Grade 4x3 para visualização limpa
                            for row in range(4):
                                cols = st.columns(3)
                                for col in range(3):
                                    index_list = row * 3 + col
                                    if index_list < 12:
                                        idx = top_12_idx[index_list]
                                        grupo_real = int(le.inverse_transform([idx])[0])
                                        chance = probabilidades[idx] * 100
                                        nome_bicho = BICHOS_DICT.get(grupo_real, "---")
                                        
                                        with cols[col]:
                                            st.markdown(f"""
                                            <div class="previsao-card">
                                                <div style="color:#4CAF50; font-size:11px; font-weight:bold;">{index_list+1}º ALVO IA</div>
                                                <div class="previsao-num">{str(grupo_real).zfill(2)}</div>
                                                <div class="bicho-nome">{nome_bicho}</div>
                                                <div class="previsao-chance">Força: {chance:.1f}%</div>
                                            </div>
                                            """, unsafe_allow_html=True)
                        else:
                            st.warning("Histórico insuficiente na planilha.")
            except Exception as e:
                st.error(f"Erro Crítico: {e}")
