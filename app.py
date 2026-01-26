import streamlit as st
import pandas as pd
from collections import Counter
import gspread
from google.oauth2.service_account import Credentials
import requests
from datetime import datetime, timedelta
import pytz
import time

# =============================================================================
# --- 1. CONFIGURAÇÕES ---
# =============================================================================
st.set_page_config(page_title="Central DUQUE (Tradicional)", page_icon="👑", layout="wide")

# Configuração da Banca Única
CONFIG_BANCA = {
    "display_name": "TRADICIONAL (Duque)",
    "logo_url": "https://cdn-icons-png.flaticon.com/512/1063/1063233.png", 
    "cor_fundo": "#2E004F", # Roxo Profundo
    "cor_texto": "#ffffff",
    "card_bg": "rgba(255, 255, 255, 0.1)",
    "horarios": "11:20 🔹 12:20 🔹 13:20 🔹 14:20 🔹 18:20 🔹 19:20 🔹 20:20 🔹 21:20 🔹 22:20 🔹 23:20"
}

# Estilo Visual
st.markdown(f"""
<style>
    [data-testid="stAppViewContainer"] {{ background-color: {CONFIG_BANCA['cor_fundo']}; }}
    h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {{ color: {CONFIG_BANCA['cor_texto']} !important; }}
    .stNumberInput input {{ color: white !important; }}
    [data-testid="stTable"] {{ color: white !important; }}
    .bola-duque {{ 
        display: inline-block; width: 60px; height: 35px; line-height: 35px; 
        border-radius: 15px; background-color: #ffd700; color: black !important; 
        text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; 
        box-shadow: 0 0 10px rgba(255, 215, 0, 0.5); 
    }}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO GOOGLE SHEETS ---
# =============================================================================
def conectar_planilha():
    # OBS: Certifique-se de que a aba se chama "TRADICIONAL" na sua planilha
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        try:
            sh = gc.open("CentralBichos")
            worksheet = sh.worksheet("TRADICIONAL")
            return worksheet
        except: return None
    return None

def carregar_dados():
    worksheet = conectar_planilha()
    if worksheet:
        dados_completos = worksheet.get_all_values()
        lista_duques = []
        try:
            for row in dados_completos:
                # Pega coluna A e B
                if len(row) >= 2 and row[0].isdigit() and row[1].isdigit():
                    g1 = int(row[0])
                    g2 = int(row[1])
                    # Ordena: (1, 12) é o mesmo que (12, 1)
                    par = tuple(sorted((g1, g2))) 
                    lista_duques.append(par)
        except: pass
        return lista_duques
    return []

def salvar_duque(b1, b2, horario):
    worksheet = conectar_planilha()
    if worksheet:
        try:
            data_hoje = datetime.now().strftime("%Y-%m-%d")
            # Salva na ordem digitada nas colunas A e B
            worksheet.append_row([int(b1), int(b2), str(horario), data_hoje])
            return True
        except: return False
    return False

def deletar_ultimo():
    worksheet = conectar_planilha()
    if worksheet:
        try:
            todos = worksheet.get_all_values()
            if len(todos) > 0:
                worksheet.delete_rows(len(todos))
                return True
        except: return False
    return False

# =============================================================================
# --- 3. LÓGICA MATEMÁTICA DO DUQUE ---
# =============================================================================

# 1. Mapeamento do Universo (325 Pares)
def gerar_universo_duques():
    todos = []
    for i in range(1, 26):
        for j in range(i, 26):
            todos.append((i, j)) 
    
    setor1, setor2, setor3 = [], [], []
    
    # Regra de Corte dos Setores
    for d in todos:
        if d <= (5, 15):
            setor1.append(d)
        elif d <= (11, 16):
            setor2.append(d)
        else:
            setor3.append(d)
            
    return todos, {"SETOR 1 (01-01 a 05-15)": setor1, "SETOR 2 (05-16 a 11-16)": setor2, "SETOR 3 (11-17 a 25-25)": setor3}

# 2. Motor de Análise
def analisar_estrategias(historico):
    if len(historico) < 10: return None
    
    todos, mapa_setores = gerar_universo_duques()
    
    # Frequência Geral (Ranking de Força)
    c_duques = Counter(historico)
    
    # --- DADOS PARA TABELA DE STRESS (SETORES) ---
    def calc_metrics(lista_alvo):
        # Atraso (Derrotas)
        atraso = 0
        max_atraso = 0
        tmp_atraso = 0
        
        # Sequencia (Vitórias)
        max_seq = 0
        tmp_seq = 0
        
        # Loop Reverso para Atraso Atual
        for x in reversed(historico):
            if x in lista_alvo: break
            atraso += 1
            
        # Loop Direto para Recordes
        for x in historico:
            if x in lista_alvo:
                tmp_seq += 1
                if tmp_atraso > max_atraso: max_atraso = tmp_atraso
                tmp_atraso = 0
            else:
                tmp_atraso += 1
                if tmp_seq > max_seq: max_seq = tmp_seq
                tmp_seq = 0
        # Checagens finais
        if tmp_atraso > max_atraso: max_atraso = tmp_atraso
        if tmp_seq > max_seq: max_seq = tmp_seq
        
        return atraso, max_atraso, max_seq

    # Gera DataFrame dos Setores
    dados_tabela = []
    atrasos_atuais = {}
    freqs_recentes = {} # Para BMA
    
    recorte_bma = historico[-20:] # Tendência recente
    
    for nome, lista in mapa_setores.items():
        curr_l, max_l, max_w = calc_metrics(lista)
        dados_tabela.append({
            "SETOR": nome,
            "ATRASO ATUAL": curr_l,
            "REC. ATRASO": max_l,
            "REC. VITÓRIA": max_w
        })
        atrasos_atuais[nome] = curr_l
        
        # Calc frequencia recente
        count = 0
        for x in recorte_bma:
            if x in lista: count += 1
        freqs_recentes[nome] = count

    df_stress = pd.DataFrame(dados_tabela)
    
    # --- ESTRATÉGIAS ---
    
    # Helper: Pegar os N melhores de uma lista
    def get_best(lista_candidatos, n):
        # Ordena por frequência histórica
        return sorted(lista_candidatos, key=lambda x: c_duques[x], reverse=True)[:n]

    # Estratégia 1: BMA (Crise + Tendencia)
    s_crise = max(atrasos_atuais, key=atrasos_atuais.get)
    s_trend = max(freqs_recentes, key=freqs_recentes.get)
    
    palpite_bma = []
    if s_crise == s_trend:
        palpite_bma = get_best(mapa_setores[s_crise], 126)
    else:
        p1 = get_best(mapa_setores[s_crise], 63)
        p2 = get_best(mapa_setores[s_trend], 63)
        palpite_bma = list(set(p1 + p2))
        
    # Estratégia 2: Setorizada (42 de cada)
    p_s1 = get_best(mapa_setores["SETOR 1 (01-01 a 05-15)"], 42)
    p_s2 = get_best(mapa_setores["SETOR 2 (05-16 a 11-16)"], 42)
    p_s3 = get_best(mapa_setores["SETOR 3 (11-17 a 25-25)"], 42)
    palpite_setor = list(set(p_s1 + p_s2 + p_s3))
    
    return df_stress, palpite_bma, palpite
