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

CONFIG_BANCA = {
    "display_name": "TRADICIONAL (Duque)",
    "logo_url": "https://cdn-icons-png.flaticon.com/512/1063/1063233.png", 
    "cor_fundo": "#2E004F", 
    "cor_texto": "#ffffff",
    "card_bg": "rgba(255, 255, 255, 0.1)",
    "horarios": "11:20 🔹 12:20 🔹 13:20 🔹 14:20 🔹 18:20 🔹 19:20 🔹 20:20 🔹 21:20 🔹 22:20 🔹 23:20"
}

st.markdown(f"""
<style>
    [data-testid="stAppViewContainer"] {{ background-color: {CONFIG_BANCA['cor_fundo']}; }}
    h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {{ color: {CONFIG_BANCA['cor_texto']} !important; }}
    .stNumberInput input {{ color: white !important; }}
    [data-testid="stTable"] {{ color: white !important; }}
    .bola-duque {{ display: inline-block; width: 60px; height: 35px; line-height: 35px; border-radius: 15px; background-color: #ffd700; color: black !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; box-shadow: 0 0 10px rgba(255, 215, 0, 0.5); }}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO ---
# =============================================================================
def conectar_planilha():
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
                if len(row) >= 2 and row[0].isdigit() and row[1].isdigit():
                    g1, g2 = int(row[0]), int(row[1])
                    lista_duques.append(tuple(sorted((g1, g2))))
        except: pass
        return lista_duques
    return []

def salvar_duque(b1, b2, horario):
    worksheet = conectar_planilha()
    if worksheet:
        try:
            data_hoje = datetime.now().strftime("%Y-%m-%d")
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
# --- 3. LÓGICA ---
# =============================================================================
def gerar_universo_duques():
    todos = []
    for i in range(1, 26):
        for j in range(i, 26):
            todos.append((i, j)) 
    setor1, setor2, setor3 = [], [], []
    for d in todos:
        if d <= (5, 15): setor1.append(d)
        elif d <= (11, 16): setor2.append(d)
        else: setor3.append(d)
    return todos, {"SETOR 1": setor1, "SETOR 2": setor2, "SETOR 3": setor3}

def analisar_estrategias(historico):
    if len(historico) < 10: return None
    todos, mapa_setores = gerar_universo_duques()
    c_duques = Counter(historico)
    
    dados_tabela = []
    atrasos_atuais = {}
    freqs_recentes = {}
    recorte_bma = historico[-20:]
    
    # Helper Metrics
    def calc_metrics(lista_alvo):
        atraso = 0; max_atraso = 0; tmp_atraso = 0; max_seq = 0; tmp_seq = 0
        for x in reversed(historico):
            if x in lista_alvo: break
            atraso += 1
        for x in historico:
            if x in lista_alvo:
                tmp_seq += 1
                if tmp_atraso > max_atraso: max_atraso = tmp_atraso
                tmp_atraso = 0
            else:
                tmp_atraso += 1
                if tmp_seq > max_seq: max_seq = tmp_seq
                tmp_seq = 0
        if tmp_atraso > max_atraso: max_atraso = tmp_atraso
        if tmp_seq > max_seq: max_seq = tmp_seq
        return atraso, max_atraso, max_seq

    for nome, lista in mapa_setores.items():
        curr_l, max_l, max_w = calc_metrics(lista)
        dados_tabela.append({"SETOR": nome, "ATRASO ATUAL": curr_l, "REC. ATRASO": max_l, "REC. VITÓRIA": max_w})
        atrasos_atuais[nome] = curr_l
        count = 0
        for x in recorte_bma:
            if x in lista: count += 1
        freqs_recentes[nome] = count

    df_stress = pd.DataFrame(dados_tabela)
    
    def get_best(lista_candidatos, n):
        return sorted(lista_candidatos, key=lambda x: c_duques[x], reverse=True)[:n]

    s_crise = max(atrasos_atuais, key=atrasos_atuais.get)
    s_trend = max(freqs_recentes, key=freqs_recentes.get)
    
    palpite_bma = []
    if s_crise == s_trend: palpite_bma = get_best(mapa_setores[s_crise], 126)
    else:
        p1 = get_best(mapa_setores[s_crise], 63)
        p2 = get_best(mapa_setores[s_trend], 63)
        palpite_bma = list(set(p1 + p2))
        
    p_s1 = get_best(mapa_setores["SETOR 1"], 42)
    p_s2 = get_best(mapa_setores["SETOR 2"], 42)
    p_s3 = get_best(mapa_setores["SETOR 3"], 42)
    palpite_setor = list(set(p_s1 + p_s2 + p_s3))
    
    return df_stress, palpite_bma, palpite_setor, s_crise, s_trend

def backtest_duque(historico, palpite):
    if not palpite: return pd.DataFrame(), 0, 0, 0
    res = []; max_loss = 0; temp_loss = 0
    for x in historico:
        if x in palpite: temp_loss = 0
        else:
            temp_loss += 1
            if temp_loss > max_loss: max_loss = temp_loss
    for i in range(max(0, len(historico)-10), len(historico)):
        saiu = historico[i]
        status = "💚" if saiu in palpite else "❌"
        res.append({"JOGO": f"#{len(historico)-i}", "SAIU": f"{saiu[0]:02}-{saiu[1]:02}", "RESULTADO": status})
    curr_streak = 0
    for r in reversed(res):
        if r["RESULTADO"] == "❌": curr_streak += 1
        else: break
    return pd.DataFrame(res[::-1]), max_loss, curr_streak

# =============================================================================
# --- 4. INTERFACE ---
# =============================================================================
with st.sidebar:
    st.image(CONFIG_BANCA['logo_url'], width=100)
    st.title("MENU DUQUE")
    horarios = [h.strip() for h in CONFIG_BANCA['horarios'].split('🔹')]
    if 'idx_h' not in st.session_state: st.session_state['idx_h'] = 0
    if 'g1' not in st.session_state: st.session_state['g1'] = 1
    if 'g2' not in st.session_state: st.session_state['g2'] = 2
    h_sel = st.selectbox("Horário:", horarios, index=st.session_state['idx_h'])
    c1, c2 = st.columns(2)
    with c1: b1 = st.number_input("1º Bicho", 1, 25, st.session_state['g1'])
    with c2: b2 = st.number_input("2º Bicho", 1, 25, st.session_state['g2'])
    if st.button("💾 SALVAR DUQUE", type="primary"):
        if salvar_duque(b1, b2, h_sel):
            st.toast("Duque Salvo!", icon="✅"); time.sleep(0.5); st.rerun()
    if st.button("🗑️ APAGAR ÚLTIMO"):
        if deletar_ultimo():
            st.toast("Apagado!", icon="🗑️"); time.sleep(0.5); st.rerun()

historico = carregar_dados()
st.title(f"👑 {CONFIG_BANCA['display_name']}")

if len(historico) > 0:
    st.info(f"Base de Dados: {len(historico)} Sorteios Registrados")
    df_stress, palp_bma, palp_set, s_crise, s_trend = analisar_estrategias(historico)
    df_bt_bma, max_l_bma, cur_l_bma = backtest_duque(historico, palp_bma)
    df_bt_set, max_l_set, cur_l_set = backtest_duque(historico, palp_set)
    
    alertas = []
    if cur_l_bma >= (max_l_bma - 1): alertas.append(f"🔥 OPORTUNIDADE BMA: Derrotas ({cur_l_bma}) perto do Recorde ({max_l_bma})!")
    if cur_l_set >= (max_l_set - 1): alertas.append(f"⚖️ OPORTUNIDADE SETOR: Derrotas ({cur_l_set}) perto do Recorde ({max_l_set})!")
    if alertas:
        for al in alertas: st.error(al)
    
    tab1, tab2 = st.tabs(["📊 Setores & Estratégias", "📜 Histórico"])
    
    with tab1:
        st.subheader("📡 Radar de Setores")
        st.table(df_stress)
        c_strat1, c_strat2 = st.columns(2)
        
        # Função para formatar lista bonita
        def formatar_palpite(lista_tuplas):
            texto = ""
            for p in lista_tuplas:
                texto += f"[{p[0]:02},{p[1]:02}], "
            return texto.rstrip(", ")

        with c_strat1:
            st.markdown("### 🔥 BMA (Crise + Tendência)")
            st.caption(f"Mixando: {s_crise} + {s_trend}")
            st.table(df_bt_bma)
            st.warning(f"⚠️ Recorde Derrotas: {max_l_bma}")
            with st.expander("Ver Palpite (126 Duques)"):
                st.code(formatar_palpite(palp_bma), language="text")
                
        with c_strat2:
            st.markdown("### ⚖️ Setorizada (42x3)")
            st.caption("Equilíbrio entre os 3 setores")
            st.table(df_bt_set)
            st.warning(f"⚠️ Recorde Derrotas: {max_l_set}")
            with st.expander("Ver Palpite (126 Duques)"):
                st.code(formatar_palpite(palp_set), language="text")

    with tab2:
        st.write("Últimos resultados:")
        for p in reversed(historico[-10:]):
            st.markdown(f"<div class='bola-duque'>{p[0]:02} - {p[1]:02}</div>", unsafe_allow_html=True)
else:
    st.warning("⚠️ Adicione os primeiros resultados na barra lateral para começar a análise.")
