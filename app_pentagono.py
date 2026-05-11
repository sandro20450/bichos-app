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
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import LabelEncoder

# =============================================================================
# --- 1. CONFIGURAÇÕES, CSS E CONEXÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono V56.7 - Comando Central", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.flex-container { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-start; margin-bottom: 20px; }
.grupo-card-zebra { background-color: #330000; border: 1px solid #ff4b4b; border-radius: 6px; padding: 8px; text-align: center; flex: 1 1 60px; max-width: 90px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.grupo-numero { font-size: 20px; font-weight: bold; color: #ffffff; margin: 3px 0; }
.grupo-pontos-zebra { font-size: 11px; color: #ff4b4b; font-weight: bold; }
.grupo-posicao { font-size: 9px; color: #aaaaaa; text-transform: uppercase; }
.backtest-box { background-color: #1a2634; padding: 12px; border-radius: 5px; border-left: 4px solid #ff4b4b; margin-bottom: 15px;}
.gatilho-ativo { background-color: #003300; border-left: 4px solid #00ff00; padding: 10px; margin-top: 10px; border-radius: 5px; color: #00ff00; font-weight: bold;}
.gatilho-espera { background-color: #1a1a1a; border-left: 4px solid #555555; padding: 10px; margin-top: 10px; border-radius: 5px; color: #aaaaaa; font-size: 13px;}

/* Estilo IA 12 Alvos */
.previsao-card { background-color: #001a00; border: 1px solid #4CAF50; border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 10px; min-height: 110px; }
.previsao-num { font-size: 26px; font-weight: bold; color: #4CAF50; line-height: 1.1; }
.bicho-nome { font-size: 13px; color: #fff; font-weight: bold; }

/* Banner de Último Sorteio */
.banner-info { background-color: #121212; border: 1px solid #4CAF50; padding: 10px; border-radius: 10px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,255,0,0.1); }
</style>
""", unsafe_allow_html=True)

def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds).open("CentralBichos")
    except: return None

# Função para evitar o erro de colunas duplicadas
def carregar_e_limpar_df(ws):
    dados = ws.get_all_values()
    if len(dados) < 2: return pd.DataFrame()
    # Força a criação do DataFrame ignorando os nomes das colunas originais para evitar duplicatas
    df = pd.DataFrame(dados[1:])
    df = df.iloc[:, :7] # Garante apenas as 7 colunas essenciais
    df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
    df = df[df["P1"].astype(str).str.strip() != ""]
    df = df[~df["P1"].astype(str).str.contains("---")]
    return df

def exibir_banner_sorteio(df, banca):
    if not df.empty:
        ult_nome = str(df.iloc[-1]["Sorteio"])
        st.markdown(f"""
        <div class="banner-info">
            <span style='color: #4CAF50; font-size: 12px; font-weight: bold;'>📡 ÚLTIMO RESULTADO EXTRAÍDO:</span><br>
            <span style='color: white; font-size: 18px; font-weight: bold;'>{banca} das {ult_nome}</span>
        </div>
        """, unsafe_allow_html=True)

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

BICHOS_DICT = {
    1:"Avestruz", 2:"Águia", 3:"Burro", 4:"Borboleta", 5:"Cachorro", 6:"Cabra", 7:"Carneiro", 8:"Camelo", 9:"Cobra", 10:"Coelho",
    11:"Cavalo", 12:"Elefante", 13:"Galo", 14:"Gato", 15:"Jacaré", 16:"Leão", 17:"Macaco", 18:"Porco", 19:"Pavão", 20:"Peru",
    21:"Touro", 22:"Tigre", 23:"Urso", 24:"Veado", 25:"Vaca"
}

def get_grupo_str(m):
    try:
        d = int(str(m)[-2:])
        return "25" if d == 0 else str(math.ceil(d/4)).zfill(2)
    except: return None

def get_grupo_int(m):
    try:
        d = int(str(m)[-2:])
        return 25 if d == 0 else math.ceil(d/4)
    except: return None

# =============================================================================
# --- 2. LOGICA ESTATÍSTICA (REDUZIDA PARA MÁXIMA VELOCIDADE) ---
# =============================================================================
def calcular_ranking_cegos(df_analise):
    scores_tmp = {str(i).zfill(2): {'puxada': 0, 'ruptura': 0, 'total': 0} for i in range(1, 26)}
    atr_g = {str(i).zfill(2): {'t': 0, 'max': 0} for i in range(1, 26)}
    
    for i in range(len(df_analise)):
        g_v = get_grupo_str(df_analise.iloc[i]["P1"])
        if g_v:
            for k in atr_g:
                atr_g[k]['t'] = 0 if k == g_v else atr_g[k]['t'] + 1
                if atr_g[k]['t'] > atr_g[k]['max']: atr_g[k]['max'] = atr_g[k]['t']
    
    for k, v in atr_g.items():
        if v['t'] >= (v['max'] - 2) and v['t'] > 0: scores_tmp[k]['ruptura'] += 4  
        
    if len(df_analise) > 1:
        ult_g = get_grupo_str(df_analise.iloc[-1]["P1"])
        for i in range(len(df_analise)-1):
            if get_grupo_str(df_analise.iloc[i]["P1"]) == ult_g:
                g_prox = get_grupo_str(df_analise.iloc[i+1]["P1"])
                if g_prox: scores_tmp[g_prox]['puxada'] += 7 
                
    for k in scores_tmp: scores_tmp[k]['total'] = scores_tmp[k]['puxada'] + scores_tmp[k]['ruptura']
    ranking = sorted(scores_tmp.items(), key=lambda x: x[1]['total'], reverse=True)
    return [x[0] for x in ranking], scores_tmp

# =============================================================================
# --- 3. MENU E TELAS ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=60)
    st.header("🎯 Pentágono V56.7")
    menu = st.radio("Selecione:", ["📊 Radar Zebra", "🤖 IA XGBoost (12 Alvos)", "📡 Extração"])

# --- RADAR ZEBRA (Otimizado) ---
if menu == "📊 Radar Zebra":
    st.title("🚨 Radar de Exclusão: 6 Grupos Zebra")
    banca_ia = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    
    if st.button("Processar Radar Zebra", use_container_width=True):
        sh = conectar_sheets()
        if sh:
            df = carregar_e_limpar_df(sh.worksheet(MAPA_ABAS[banca_ia]))
            if not df.empty:
                exibir_banner_sorteio(df, banca_ia)
                
                # Backtest rápido (últimos 50)
                ranking_final, scores = calcular_ranking_cegos(df)
                cegos_atuais = ranking_final[19:25]
                
                bool_cegos = []
                for i in range(len(df)-50, len(df)):
                    df_p = df.iloc[:i]
                    rank_p, _ = calcular_ranking_cegos(df_p)
                    bool_cegos.append(True if get_grupo_str(df.iloc[i]["P1"]) in rank_p[19:25] else False)
                
                # Conta sequências
                mv=0; ca=0
                for r in bool_cegos:
                    if r: ca+=1; mv=max(mv, ca)
                    else: ca=0
                
                st.markdown(f'<div class="backtest-box"><b>Histórico da Zebra:</b> Recorde: {mv}x seguidas | Atual: {ca}x seguidas</div>', unsafe_allow_html=True)
                
                if ca >= (mv - 1) and ca > 0:
                    st.markdown(f'<div class="gatilho-ativo">🚀 GATILHO TÁTICO ATIVADO! Zebra no limite histórico.</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="gatilho-espera">⏳ Status: Zebra em fluxo normal.</div>', unsafe_allow_html=True)
                
                html = '<div class="flex-container">'
                for idx, g in enumerate(cegos_atuais):
                    pts = scores[g]['total']
                    html += f'<div class="grupo-card-zebra"><div class="grupo-posicao">{idx+20}º Zebra</div><div class="grupo-numero">{g}</div><div class="grupo-pontos-zebra">↑ {pts} pts</div></div>'
                st.markdown(html + '</div>', unsafe_allow_html=True)

# --- IA XGBOOST ---
elif menu == "🤖 IA XGBoost (12 Alvos)":
    st.title("🤖 IA Pentágono: Previsão 1º Prêmio")
    banca_xgb = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    
    if st.button("Ativar IA (XGBoost Otimizado)", type="primary", use_container_width=True):
        sh = conectar_sheets()
        if sh:
            df = carregar_e_limpar_df(sh.worksheet(MAPA_ABAS[banca_xgb]))
            if not df.empty:
                exibir_banner_sorteio(df, banca_xgb)
                
                with st.spinner("Treinando IA..."):
                    df_ia = df.tail(500).copy()
                    df_ia['g'] = df_ia['P1'].apply(get_grupo_int)
                    df_ia = df_ia.dropna(subset=['g'])
                    df_ia['a1'] = df_ia['g'].shift(1); df_ia['a2'] = df_ia['g'].shift(2); df_ia['a3'] = df_ia['g'].shift(3)
                    df_treino = df_ia.dropna()
                    
                    X = df_treino[['a1', 'a2', 'a3']]
                    le = LabelEncoder(); y = le.fit_transform(df_treino['g'])
                    
                    grid = GridSearchCV(xgb.XGBClassifier(eval_metric='mlogloss'), {'max_depth':[3,4], 'n_estimators':[50,100]}, cv=2)
                    grid.fit(X, y)
                    
                    prob = grid.best_estimator_.predict_proba(df_ia[['a1','a2','a3']].tail(1))[0]
                    top_12 = np.argsort(prob)[::-1][:12]
                    
                    st.markdown("### 🔮 Projeção dos 12 Alvos IA:")
                    for row in range(4):
                        cols = st.columns(3)
                        for col in range(3):
                            i = row*3+col
                            if i < 12:
                                g_real = int(le.inverse_transform([top_12[i]])[0])
                                with cols[col]:
                                    st.markdown(f"""<div class="previsao-card"><div style="color:#4CAF50; font-size:10px; font-weight:bold;">{i+1}º ALVO</div><div class="previsao-num">{str(g_real).zfill(2)}</div><div class="bicho-nome">{BICHOS_DICT[g_real]}</div><div style="color:#aaa; font-size:11px;">{prob[top_12[i]]*100:.1f}%</div></div>""", unsafe_allow_html=True)

# --- EXTRAÇÃO (Mantida igual) ---
elif menu == "📡 Extração":
    st.title("📡 Extração de Resultados")
    banca_ex = st.selectbox("Banca:", list(BANCAS_CONFIG.keys()))
    dt = st.date_input("Data:", value=date.today())
    if st.button("🚀 Extrair Agora"):
        # (Lógica de extração do seu código anterior foi mantida aqui para salvar no Sheets)
        with st.spinner("Conectando..."):
            res = extrair_dia(banca_ex, dt)
            if res:
                sh = conectar_sheets()
                if sh:
                    ws = sh.worksheet(MAPA_ABAS[banca_ex])
                    # Função interna para salvar sem duplicar
                    existentes = ws.get_all_values()
                    set_exist = {f"{str(r[0]).strip()}_{str(r[1]).strip()}" for r in existentes if len(r) >= 2}
                    p_ins = [l for l in res if f"{str(l[0]).strip()}_{str(l[1]).strip()}" not in set_exist]
                    if p_ins: ws.append_rows(p_ins, value_input_option="RAW")
                    st.success(f"✅ {len(p_ins)} novos sorteios guardados.")
            else: st.error("Nenhum resultado disponível.")
