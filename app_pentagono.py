import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import re

# =============================================================================
# --- 1. CONFIGURAÇÕES E CONEXÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono IA - Comando Central", page_icon="🎯", layout="wide")

# Estilo para os cards de previsão
st.markdown("""
<style>
    .previsao-card { background-color: #001a00; border: 2px solid #4CAF50; border-radius: 10px; padding: 15px; text-align: center; margin-bottom: 10px; }
    .grupo-num { font-size: 32px; font-weight: bold; color: #4CAF50; }
    .chance-text { font-size: 14px; color: #aaa; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource(ttl=3600)
def get_gspread_client():
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], 
                scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    return None

def carregar_dados_banca(nome_aba):
    try:
        gc = get_gspread_client()
        if gc:
            ws = gc.open("Base_NoPrecinho").worksheet(nome_aba) # Nome conforme sua planilha
            dados = ws.get_all_values()
            df = pd.DataFrame(dados[1:], columns=dados[0])
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

# Tática: Converter milhar para grupo do bicho (1-25)
def milhar_para_grupo(milhar):
    try:
        dezena = int(str(milhar)[-2:])
        if dezena == 0: return 25
        import math
        return math.ceil(dezena / 4)
    except: return None

# =============================================================================
# --- 2. MOTOR DE INTELIGÊNCIA ARTIFICIAL (XGBOOST) ---
# =============================================================================
def treinar_ia_pentagono(df_banca):
    # Preparando os dados: pegando o P1 de cada sorteio
    df_banca = df_banca.copy()
    df_banca['grupo_alvo'] = df_banca['P1'].apply(milhar_para_grupo)
    df_banca = df_banca.dropna(subset=['grupo_alvo'])
    
    # Criando histórico (Features) - O que saiu antes influencia o agora
    df_banca['ant_1'] = df_banca['grupo_alvo'].shift(-1)
    df_banca['ant_2'] = df_banca['grupo_alvo'].shift(-2)
    df_banca['ant_3'] = df_banca['grupo_alvo'].shift(-3)
    
    df_treino = df_banca.dropna().head(500) # Usando os últimos 500 registros para treinar
    
    if len(df_treino) < 50:
        return None, 0
    
    X = df_treino[['ant_1', 'ant_2', 'ant_3']]
    y = df_treino['grupo_alvo'] - 1 # XGBoost inicia do zero
    
    # Treinamento Tático
    modelo = xgb.XGBClassifier(
        objective='multi:softprob', 
        num_class=25, 
        eval_metric='mlogloss',
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1
    )
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    modelo.fit(X_train, y_train)
    
    precisao = accuracy_score(y_test, modelo.predict(X_test))
    return modelo, precisao

# =============================================================================
# --- 3. INTERFACE DE COMANDO ---
# =============================================================================
with st.sidebar:
    st.image("noprecinho.png", width=120) # Sua logo
    st.title("PROJETO PENTÁGONO")
    modo = st.radio("Selecione o Radar:", ["📊 Estatística Tradicional", "🤖 Radar IA (XGBoost)"])
    st.markdown("---")
    banca = st.selectbox("🎯 Selecionar Banca:", ["TRADICIONAL_MILHAR", "LOTEP_MILHAR", "CAMINHO_MILHAR", "MONTE_MILHAR"])

if modo == "📊 Estatística Tradicional":
    st.header(f"Análise Estatística: {banca}")
    # Aqui entraria o seu código original de Scores e Pontos Cegos...
    df = carregar_dados_banca(banca)
    if not df.empty:
        st.dataframe(df.head(10), use_container_width=True)
    else:
        st.error("Falha ao carregar dados do quartel-general.")

elif modo == "🤖 Radar IA (XGBoost)":
    st.header(f"🤖 Radar Preditivo Pentágono - {banca}")
    st.info("O modelo XGBoost está analisando padrões de frequência e anomalias nas dezenas sorteadas.")
    
    df_ia = carregar_dados_banca(banca)
    
    if not df_ia.empty:
        if st.button("🚀 Ativar Cérebro Pentágono (Treinar IA)"):
            with st.spinner("Calibrando algoritmos de Gradiente Boosting..."):
                modelo, precisao = treinar_ia_pentagono(df_ia)
                
                if modelo:
                    st.success(f"IA Calibrada com Sucesso! Precisão Tática: {precisao*100:.2f}%")
                    
                    # Pegar os últimos 3 resultados reais para prever o próximo
                    df_recente = df_ia.copy()
                    df_recente['g'] = df_recente['P1'].apply(milhar_para_grupo)
                    ultimos_3 = df_recente.dropna(subset=['g'])['g'].head(3).values
                    
                    if len(ultimos_3) == 3:
                        entrada = pd.DataFrame({'ant_1': [ultimos_3[0]], 'ant_2': [ultimos_3[1]], 'ant_3': [ultimos_3[2]]})
                        probabilidades = modelo.predict_proba(entrada)[0]
                        
                        top_3 = np.argsort(probabilidades)[::-1][:3]
                        
                        st.markdown("### 🔮 Projeção para o Próximo Sorteio:")
                        cols = st.columns(3)
                        
                        bichos = {
                            1:"Avestruz", 2:"Águia", 3:"Burro", 4:"Borboleta", 5:"Cachorro",
                            6:"Cabra", 7:"Carneiro", 8:"Camelo", 9:"Cobra", 10:"Coelho",
                            11:"Cavalo", 12:"Elefante", 13:"Galo", 14:"Gato", 15:"Jacaré",
                            16:"Leão", 17:"Macaco", 18:"Porco", 19:"Pavão", 20:"Peru",
                            21:"Touro", 22:"Tigre", 23:"Urso", 24:"Veado", 25:"Vaca"
                        }
                        
                        for i, idx in enumerate(top_3):
                            grupo = idx + 1
                            chance = probabilidades[idx] * 100
                            nome_bicho = bichos.get(grupo, "Desconhecido")
                            
                            with cols[i]:
                                st.markdown(f"""
                                <div class="previsao-card">
                                    <div style="color:#4CAF50; font-size:14px; font-weight:bold;">{i+1}º PALPITE IA</div>
                                    <div class="grupo-num">{grupo}</div>
                                    <div style="color:white; font-size:18px;">{nome_bicho}</div>
                                    <div class="chance-text">Força do Padrão: {chance:.1f}%</div>
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.warning("Dados insuficientes para gerar a entrada da previsão.")
                else:
                    st.error("Dados insuficientes nesta banca para treinar o XGBoost.")
    else:
        st.error("Não foi possível acessar a base de dados.")
