import streamlit as st
import pandas as pd
from collections import Counter
import gspread
from google.oauth2.service_account import Credentials
import requests
from datetime import datetime, timedelta
import pytz
import time
import base64
import re
from bs4 import BeautifulSoup 

# ... (Configurações iniciais e funções auxiliares permanecem iguais) ...

# ... (Funções de banco de dados permanecem iguais) ...

# ... (Funções de lógica do robô, scraping, ranking, etc. permanecem iguais) ...

# --- MODIFICAÇÃO: Lógica do Monitor de Oportunidade ---

def monitorar_oportunidades(historico, banca):
    alertas = []

    # 1. Monitorar Top 12 -> Sugerir Bunker
    _, _, curr_streak_12, _ = gerar_backtest_e_status(historico, banca)
    if curr_streak_12 >= 2:
        alertas.append("⚡ OPORTUNIDADE: Top 12 falhou 2x ou mais. Jogue no Bunker agora!")

    # 2. Monitorar BMA (Crise + Tendência) -> Sugerir BMA
    _, _, _, _, risk_bma, curr_streak_bma = gerar_backtest_bma_crise_tendencia(historico)
    if curr_streak_bma >= risk_bma and curr_streak_bma > 0:
         alertas.append(f"🔥 OPORTUNIDADE BMA: Atingiu o recorde de derrotas ({curr_streak_bma}). Alta chance de reversão!")
    elif curr_streak_bma >= (risk_bma - 1) and risk_bma > 2: # Aviso prévio se estiver quase lá
         alertas.append(f"⚠️ ATENÇÃO BMA: Sequência de derrotas ({curr_streak_bma}) próxima do recorde ({risk_bma}). Prepare-se!")

    return alertas

# ... (Restante do código) ...

# --- INTERFACE PRINCIPAL ---

# ... (Sidebar e carregamento de dados) ...

if aba_ativa:
    historico, ultimo_horario_salvo = carregar_dados(aba_ativa)
    
    if len(historico) > 0:
        
        # ... (Cálculos das estratégias) ...

        # --- MONITOR DE OPORTUNIDADE (CHAMADA DA FUNÇÃO) ---
        alertas_oportunidade = monitorar_oportunidades(historico, banca_selecionada)

        # ... (Layout do aplicativo) ...

        # PAINEL DE CONTROLE (V64 - Com Monitor)
        with st.expander("📊 Painel de Controle (Local)", expanded=True):
            
            # --- EXIBIÇÃO DOS ALERTAS ---
            if alertas_oportunidade:
                for alerta in alertas_oportunidade:
                    if "⚡" in alerta or "🔥" in alerta:
                        st.success(alerta)
                    else:
                        st.warning(alerta)
            
            # ... (Abas e conteúdo do painel) ...
            
            # --- REMOÇÃO DO AVISO ANTIGO NO TOP 12 ---
            # Na aba Top 12, remover a parte que exibia pct_win_win e pct_loss_win
            # ...
