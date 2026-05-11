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
st.set_page_config(page_title="Pentágono V56.6 - Ultra Rápido", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.flex-container { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-start; margin-bottom: 20px; }
.grupo-card { background-color: #001a00; border: 1px solid #4CAF50; border-radius: 6px; padding: 8px; text-align: center; flex: 1 1 60px; max-width: 90px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.grupo-card-zebra { background-color: #330000; border: 1px solid #ff4b4b; border-radius: 6px; padding: 8px; text-align: center; flex: 1 1 60px; max-width: 90px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.grupo-numero { font-size: 20px; font-weight: bold; color: #ffffff; margin: 3px 0; }
.grupo-pontos-zebra { font-size: 11px; color: #ff4b4b; font-weight: bold; }
.grupo-posicao { font-size: 9px; color: #aaaaaa; text-transform: uppercase; }
.backtest-box { background-color: #1a2634; padding: 10px; border-radius: 5px; border-left: 4px solid #ff4b4b; margin-bottom: 10px;}
.gatilho-ativo { background-color: #003300; border-left: 4px solid #00ff00; padding: 10px; margin-top: 10px; border-radius: 5px; color: #00ff00; font-weight: bold;}
.gatilho-espera { background-color: #1a1a1a; border-left: 4px solid #555555; padding: 10px; margin-top: 10px; border-radius: 5px; color: #aaaaaa; font-size: 13px;}

/* Cards IA */
.previsao-card { background-color: #001a00; border: 1px solid #4CAF50; border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 10px; min-height: 120px; }
.previsao-num { font-size: 28px; font-weight: bold; color: #4CAF50; line-height: 1.1; }
.previsao-chance { font-size: 12px; color: #aaa; }
.bicho-nome { font-size: 14px; color: #fff; font-weight: bold; }

/* Identificador de Sorteio */
.info-sorteio { background-color: #1a1a1a; padding: 12px; border-radius: 8px; border: 1px solid #4CAF50; text-align: center; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client.open("CentralBichos")
    except Exception as e:
        st.error(f"Erro na conexão: {e}")
        return None

def salvar_sem_duplicar(ws, dados_novos):
    try:
        existentes = ws.get_all_values()
        set_existentes = {f"{str(row[0]).strip()}_{str(row[1]).strip()}" for row in existentes if len(row) >= 2}
        para_inserir = [l for l in dados_novos if f"{str(l[0]).strip()}_{str(l[1]).strip()}" not in set_existentes]
        if para_inserir: ws.append_rows(para_inserir, value_input_option="RAW")
        return len(para_inserir), len(dados_novos) - len(para_inserir)
    except: return 0, 0

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
# --- 2. MOTOR DE EXTRAÇÃO ---
# =============================================================================
def extrair_dia(banca, data_alvo):
    url = f"{BANCAS_CONFIG[banca]}{data_alvo.strftime('%Y-%m-%d')}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        tabelas = soup.find_all('table')
        resultados = []
        for tab in tabelas:
            th_tag = tab.find('th')
            txt_th = th_tag.get_text().upper() if th_tag else ""
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b'])
            txt_prev = prev.get_text().upper() if prev else ""
            texto_alvo = txt_th if re.search(r'\d{2}:\d{2}h?|\d{2}h', txt_th) else txt_prev
            if "FEDERAL" in texto_alvo.upper(): continue
            match_hora = re.search(r'(\d{2}):(\d{2})h?|(\d{2})h', texto_alvo, re.IGNORECASE)
            nome = f"{match_hora.group(3)}:00" if match_hora and match_hora.group(3) else (f"{match_hora.group(1)}:{match_hora.group(2)}" if match_hora else "Extra")
            milhares = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhares.append(nums[0][:4].zfill(4) if nums and len(nums[0]) >= 3 else "----")
            if len(milhares) >= 5:
                resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

# =============================================================================
# --- 3. LÓGICA ESTATÍSTICA (SIMPLIFICADA) ---
# =============================================================================
def calcular_ranking_completo(df_analise):
    scores_tmp = {str(i).zfill(2): {'puxada': 0, 'ruptura': 0, 'semana': 0, 'total': 0} for i in range(1, 26)}
    atr_g = {str(i).zfill(2): {'t': 0, 'max': 0} for i in range(1, 26)}
    for i in range(len(df_analise)):
        g_v = get_grupo_str(df_analise.iloc[i]["P1"])
        if g_v:
            for k in atr_g:
                atr_g[k]['t'] = 0 if k == g_v else atr_g[k]['t'] + 1
                if atr_g[k]['t'] > atr_g[k]['max']: atr_g[k]['max'] = atr_g[k]['t']
    for k, v in atr_g.items():
        if v['t'] >= (v['max'] - 2) and v['t'] > 0: scores_tmp[k]['ruptura'] += 4  
    if len(df_analise) > 0:
        ult_g = get_grupo_str(df_analise.iloc[-1]["P1"])
        for i in range(len(df_analise)-1):
            if get_grupo_str(str(df_analise.iloc[i]["P1"]).zfill(4)) == ult_g:
                g_p1 = get_grupo_str(df_analise.iloc[i+1]["P1"])
                if g_p1: scores_tmp[g_p1]['puxada'] += 7 
    for k in scores_tmp: scores_tmp[k]['total'] = scores_tmp[k]['puxada'] + scores_tmp[k]['ruptura']
    ranking_tmp = sorted(scores_tmp.items(), key=lambda x: x[1]['total'], reverse=True)
    return [x[0] for x in ranking_tmp], scores_tmp

# =============================================================================
# --- 4. INTERFACE ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=60)
    st.header("🎯 Pentágono V56.6")
    menu = st.radio("Menu:", ["📡 Extração", "📊 Radar Zebra", "🤖 IA XGBoost"])

if menu == "📡 Extração":
    st.title("📡 Extração CentralBichos")
    banca_sel = st.selectbox("Banca:", list(BANCAS_CONFIG.keys()))
    dt_alvo = st.date_input("Data:", value=date.today())
    if st.button("🚀 EXTRAIR E SALVAR"):
        with st.spinner("Extraindo..."):
            dados = extrair_dia(banca_sel, dt_alvo)
            if dados:
                sh = conectar_sheets()
                if sh:
                    ws = sh.worksheet(MAPA_ABAS[banca_sel])
                    ins, rep = salvar_sem_duplicar(ws, dados)
                    st.success(f"✅ {ins} novos / {rep} repetidos.")
            else: st.error("Nenhum dado encontrado.")

elif menu == "📊 Radar Zebra":
    st.title("🚨 Radar de Exclusão: Zebra")
    banca_ia = st.selectbox("Banca:", list(BANCAS_CONFIG.keys()))
    if st.button("Processar Zebra"):
        sh = conectar_sheets()
        if sh:
            ws = sh.worksheet(MAPA_ABAS[banca_ia])
            dados = ws.get_all_values()
            df = pd.DataFrame(dados[1:], columns=dados[0])
            df = df[df["P1"].astype(str).str.strip() != ""]
            
            # Cálculo de Sequência da Zebra
            ranking_completo, scores = calcular_ranking_completo(df)
            pontos_cegos = ranking_completo[19:25]
            
            bool_cegos = []
            for i in range(len(df)-50, len(df)):
                df_passado = df.iloc[:i]
                rank_p, _ = calcular_ranking_completo(df_passado)
                cegos_p = rank_p[19:25]
                g1_real = get_grupo_str(df.iloc[i]["P1"])
                bool_cegos.append(True if g1_real in cegos_p else False)

            def contar_seq(lista):
                mv=0; ca=0
                for r in lista:
                    if r: ca+=1; mv=max(mv, ca)
                    else: ca=0
                return mv, ca

            v_max_c, v_atual_c = contar_seq(bool_cegos)
            
            st.markdown(f"""
            <div class="backtest-box">
                <b>Status da Zebra:</b> Recorde Histórico: {v_max_c}x | Atual: {v_atual_c}x
            </div>
            """, unsafe_allow_html=True)
            
            if v_atual_c >= (v_max_c - 1) and v_atual_c > 0:
                st.markdown(f'<div class="gatilho-ativo">🚀 GATILHO ATIVADO! Zebra no limite!</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="gatilho-espera">⏳ Zebra em fluxo normal.</div>', unsafe_allow_html=True)
            
            html = '<div class="flex-container">'
            for idx, g in enumerate(pontos_cegos):
                pts = scores[g]['total']
                html += f'<div class="grupo-card-zebra"><div class="grupo-posicao">{idx+20}º Zebra</div><div class="grupo-numero">{g}</div><div class="grupo-pontos-zebra">↑ {pts} pts</div></div>'
            st.markdown(html + '</div>', unsafe_allow_html=True)

elif menu == "🤖 IA XGBoost":
    st.title("🤖 IA Pentágono: Previsão 12 Alvos")
    banca_xgb = st.selectbox("Banca:", list(BANCAS_CONFIG.keys()))
    
    if st.button("🚀 Ativar IA"):
        with st.spinner("Treinando IA..."):
            sh = conectar_sheets()
            if sh:
                ws = sh.worksheet(MAPA_ABAS[banca_xgb])
                dados = ws.get_all_values()
                df = pd.DataFrame(dados[1:], columns=dados[0])
                df = df[df["P1"].astype(str).str.strip() != ""].tail(500)
                
                # --- IDENTIFICADOR DO ÚLTIMO SORTEIO ---
                ult_nome = str(df.iloc[-1]["Sorteio"])
                ult_data = str(df.iloc[-1]["Data"])
                st.markdown(f"""
                <div class="info-sorteio">
                    <span style='color: #4CAF50; font-weight: bold;'>📡 ÚLTIMO SORTEIO EXTRAÍDO:</span><br>
                    <span style='color: white; font-size: 18px;'>{banca_xgb} - {ult_nome} ({ult_data})</span>
                </div>
                """, unsafe_allow_html=True)

                df['g'] = df['P1'].apply(get_grupo_int)
                df = df.dropna(subset=['g'])
                df['ant_1'] = df['g'].shift(1); df['ant_2'] = df['g'].shift(2); df['ant_3'] = df['g'].shift(3)
                df_t = df.dropna()
                
                X = df_t[['ant_1', 'ant_2', 'ant_3']]
                le = LabelEncoder(); y = le.fit_transform(df_t['g'])
                
                # Otimizado para Velocidade
                grid = GridSearchCV(xgb.XGBClassifier(eval_metric='mlogloss'), {'max_depth':[3,4], 'n_estimators':[50,80]}, cv=2)
                grid.fit(X, y)
                
                prob = grid.best_estimator_.predict_proba(df[['ant_1','ant_2','ant_3']].tail(1))[0]
                top_12 = np.argsort(prob)[::-1][:12]
                
                st.markdown("### 🔮 Próximos 12 Alvos (1º Prêmio):")
                for r in range(4):
                    cols = st.columns(3)
                    for c in range(3):
                        i = r*3+c
                        if i < 12:
                            g_real = int(le.inverse_transform([top_12[i]])[0])
                            with cols[c]:
                                st.markdown(f"""<div class="previsao-card"><div style="color:#4CAF50; font-size:10px;">{i+1}º ALVO</div><div class="previsao-num">{str(g_real).zfill(2)}</div><div class="bicho-nome">{BICHOS_DICT[g_real]}</div><div class="previsao-chance">{prob[top_12[i]]*100:.1f}%</div></div>""", unsafe_allow_html=True)
