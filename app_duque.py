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
    [data-testid="stTable"] {{ color: white !important; background-color: transparent !important; }}
    
    .bola-s1 {{ display: inline-block; width: 40px; height: 40px; line-height: 40px; border-radius: 50%; background-color: #17a2b8; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); }}
    .bola-s2 {{ display: inline-block; width: 40px; height: 40px; line-height: 40px; border-radius: 50%; background-color: #fd7e14; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); }}
    .bola-s3 {{ display: inline-block; width: 40px; height: 40px; line-height: 40px; border-radius: 50%; background-color: #dc3545; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); }}
    
    .bola-duque {{ display: inline-block; width: 60px; height: 35px; line-height: 35px; border-radius: 15px; background-color: #ffd700; color: black !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; box-shadow: 0 0 10px rgba(255, 215, 0, 0.5); }}
    
    .metric-box-loss {{ background-color: #583b00; border: 1px solid #d4af37; color: #ffd700; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 5px; font-weight: bold; }}
    .metric-box-win {{ background-color: #003300; border: 1px solid #00ff00; color: #00ff00; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 5px; font-weight: bold; }}
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
    return todos, {"SETOR 1 (01-01 a 05-15)": setor1, "SETOR 2 (05-16 a 11-16)": setor2, "SETOR 3 (11-17 a 25-25)": setor3}

def formatar_palpite(lista_tuplas):
    lista_ordenada = sorted(lista_tuplas)
    texto = ""
    for p in lista_ordenada:
        texto += f"[{p[0]:02},{p[1]:02}], "
    return texto.rstrip(", ")

# --- RANKINGS (FUNÇÕES PURAS) ---
def get_rank_dinamico(dados_historicos):
    # Calcula ranking baseado apenas nos dados passados
    hist_rev = dados_historicos[::-1]
    scores = {d: 0 for d in gerar_universo_duques()[0]}
    
    c_curto = Counter(hist_rev[:20]) 
    c_medio = Counter(hist_rev[:50])
    
    for d, freq in c_curto.items(): scores[d] += (freq * 3.0)
    for d, freq in c_medio.items(): scores[d] += (freq * 1.0)
    
    rank = sorted(scores.items(), key=lambda x: -x[1])
    return [d for d, s in rank]

def get_rank_bunker(dados_historicos):
    c = Counter(dados_historicos)
    rank = c.most_common()
    return [d for d, qtd in rank]

# --- ANÁLISE DE SETORES (BMA / SETORIZADA) ---
def analisar_estrategias_setores(historico):
    if len(historico) < 10: return None
    todos, mapa_setores = gerar_universo_duques()
    c_duques = Counter(historico)
    
    dados_tabela = []
    atrasos_atuais = {}
    freqs_recentes = {}
    recorte_bma = historico[-20:]
    
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
        dados_tabela.append({"SETOR": nome, "ATRASO": curr_l, "REC. ATRASO": max_l, "REC. SEQ. (V)": max_w})
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
        
    p_s1 = get_best(mapa_setores["SETOR 1 (01-01 a 05-15)"], 42)
    p_s2 = get_best(mapa_setores["SETOR 2 (05-16 a 11-16)"], 42)
    p_s3 = get_best(mapa_setores["SETOR 3 (11-17 a 25-25)"], 42)
    palpite_setor = list(set(p_s1 + p_s2 + p_s3))
    
    return df_stress, palpite_bma, palpite_setor, s_crise, s_trend

# --- BACKTEST COM SIMULAÇÃO REAL (ROLLING WINDOW) ---
def backtest_simulado_real(historico, tipo_estrategia, n_simulacoes=50):
    # tipo_estrategia: 'dinamico' ou 'bunker'
    
    if len(historico) < n_simulacoes + 10: return pd.DataFrame(), 0, 0, 0
    
    res = []
    max_loss = 0; temp_loss = 0
    max_win = 0; temp_win = 0
    
    # Loop de Simulação "Viajando no Tempo"
    # Começa em (Hoje - 50 jogos) e vai até Hoje
    inicio_sim = len(historico) - n_simulacoes
    
    for i in range(inicio_sim, len(historico)):
        resultado_real = historico[i]
        
        # O PULO DO GATO:
        # Usa APENAS o histórico ANTERIOR ao jogo 'i' para calcular o palpite
        historico_passado = historico[:i] 
        
        palpite_da_epoca = []
        if tipo_estrategia == 'dinamico':
            palpite_da_epoca = get_rank_dinamico(historico_passado)[:126]
        elif tipo_estrategia == 'bunker':
            palpite_da_epoca = get_rank_bunker(historico_passado)[:126]
            
        # Confere se ganhou
        if resultado_real in palpite_da_epoca:
            status = "💚"
            temp_win += 1
            if temp_loss > max_loss: max_loss = temp_loss
            temp_loss = 0
        else:
            status = "❌"
            temp_loss += 1
            if temp_win > max_win: max_win = temp_win
            temp_win = 0
            
        # Adiciona na tabela (apenas os ultimos 20 para visualização)
        if i >= len(historico) - 20:
            res.append({
                "JOGO": f"#{len(historico)-i}", 
                "SAIU": f"{resultado_real[0]:02}-{resultado_real[1]:02}", 
                "RES": status
            })
            
    # Verifica recordes finais do loop
    if temp_loss > max_loss: max_loss = temp_loss
    if temp_win > max_win: max_win = temp_win
    
    # Streak Atual
    curr_streak = 0
    df_res = pd.DataFrame(res[::-1])
    
    if not df_res.empty:
        for r in df_res.to_dict('records'):
            if r["RES"] == "❌": curr_streak += 1
            else: break
            
    return df_res, max_loss, curr_streak, max_win

# Backtest Simples para BMA/Setor (Estatístico Fixo)
def backtest_fixo(historico, palpite, limit=50):
    if not palpite: return pd.DataFrame(), 0, 0, 0
    recorte_risk = historico[-limit:] if len(historico) > limit else historico
    max_loss = 0; temp_loss = 0; max_win = 0; temp_win = 0
    for x in recorte_risk:
        if x in palpite:
            temp_win += 1
            if temp_loss > max_loss: max_loss = temp_loss
            temp_loss = 0
        else:
            temp_loss += 1
            if temp_win > max_win: max_win = temp_win
            temp_win = 0
    if temp_loss > max_loss: max_loss = temp_loss
    if temp_win > max_win: max_win = temp_win
    res = []
    inicio = max(0, len(historico)-20)
    for i in range(inicio, len(historico)):
        saiu = historico[i]
        status = "💚" if saiu in palpite else "❌"
        res.append({"JOGO": f"#{len(historico)-i}", "SAIU": f"{saiu[0]:02}-{saiu[1]:02}", "RES": status})
    curr_streak = 0
    for r in reversed(res):
        if r["RES"] == "❌": curr_streak += 1
        else: break
    return pd.DataFrame(res[::-1]), max_loss, curr_streak, max_win

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
    
    # 1. Estratégias de Setor (Padrão)
    df_stress, palp_bma, palp_set, s_crise, s_trend = analisar_estrategias_setores(historico)
    
    # 2. Palpites ATUAIS para Dinâmico e Bunker (Para jogar HOJE)
    palp_din_hoje = get_rank_dinamico(historico)[:126]
    palp_bun_hoje = get_rank_bunker(historico)[:126]
    
    # 3. Backtests (Calculos)
    # BMA e Setor usam cálculo fixo estatístico
    bt_bma, ml_bma, cl_bma, mw_bma = backtest_fixo(historico, palp_bma)
    bt_set, ml_set, cl_set, mw_set = backtest_fixo(historico, palp_set)
    
    # Dinâmico e Bunker usam SIMULAÇÃO REAL (Rolling Window) para não mentir
    bt_din, ml_din, cl_din, mw_din = backtest_simulado_real(historico, 'dinamico')
    bt_bun, ml_bun, cl_bun, mw_bun = backtest_simulado_real(historico, 'bunker')
    
    # Alertas
    alertas = []
    if cl_bma >= (ml_bma - 1): alertas.append(f"🔥 OPORTUNIDADE BMA: Derrotas ({cl_bma}) perto do Recorde ({ml_bma})!")
    if cl_set >= (ml_set - 1): alertas.append(f"⚖️ OPORTUNIDADE SETOR: Derrotas ({cl_set}) perto do Recorde ({ml_set})!")
    if cl_din >= (ml_din - 1): alertas.append(f"🚀 OPORTUNIDADE DINÂMICA: Derrotas ({cl_din}) perto do Recorde ({ml_din})!")
    if cl_bun >= (ml_bun - 1): alertas.append(f"🧬 OPORTUNIDADE BUNKER: Derrotas ({cl_bun}) perto do Recorde ({ml_bun})!")
    
    if alertas:
        for al in alertas: st.error(al)
    
    tab1, tab2, tab3 = st.tabs(["📊 Setores & Estratégias", "🆚 Comparativo (2 Mesas)", "📜 Histórico"])
    
    with tab1:
        st.write("Histórico Recente por Setor (⬅️ Mais Novo):")
        _, mapa_setores_vis = gerar_universo_duques()
        html_bolas = "<div>"
        for duque in reversed(historico[-12:]):
            if duque in mapa_setores_vis["SETOR 1 (01-01 a 05-15)"]: classe, sigla = "bola-s1", "S1"
            elif duque in mapa_setores_vis["SETOR 2 (05-16 a 11-16)"]: classe, sigla = "bola-s2", "S2"
            else: classe, sigla = "bola-s3", "S3"
            html_bolas += f"<div class='{classe}'>{sigla}</div>"
        html_bolas += "</div>"
        st.markdown(html_bolas, unsafe_allow_html=True)
        st.markdown("---")

        st.subheader("📡 Radar de Setores")
        st.table(df_stress)
        c_strat1, c_strat2 = st.columns(2)
        
        with c_strat1:
            st.markdown("### 🔥 BMA (Crise + Tendência)")
            st.caption(f"Mixando: {s_crise} + {s_trend}")
            st.table(bt_bma)
            st.markdown(f'<div class="metric-box-loss">⚠️ Recorde Derrotas (50j): {ml_bma}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box-win">🏆 Recorde Vitórias (50j): {mw_bma}</div>', unsafe_allow_html=True)
            with st.expander("Ver Palpite (126 Duques)"):
                st.code(formatar_palpite(palp_bma), language="text")
                
        with c_strat2:
            st.markdown("### ⚖️ Setorizada (42x3)")
            st.caption("Equilíbrio entre os 3 setores")
            st.table(bt_set)
            st.markdown(f'<div class="metric-box-loss">⚠️ Recorde Derrotas (50j): {ml_set}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box-win">🏆 Recorde Vitórias (50j): {mw_set}</div>', unsafe_allow_html=True)
            with st.expander("Ver Palpite (126 Duques)"):
                st.code(formatar_palpite(palp_set), language="text")

    # --- ABA COMPARATIVO ---
    with tab2:
        col_comp1, col_comp2 = st.columns(2)
        
        with col_comp1:
            st.markdown("### 🚀 Top 126 Dinâmico")
            st.caption("Simulação Real (Sem vazamento de dados)")
            st.table(bt_din)
            st.markdown(f'<div class="metric-box-loss">⚠️ Recorde Derrotas (50j): {ml_din}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box-win">🏆 Recorde Vitórias (50j): {mw_din}</div>', unsafe_allow_html=True)
            with st.expander("Ver Palpite HOJE (126 Dinâmicos)"):
                st.code(formatar_palpite(palp_din_hoje), language="text")
        
        with col_comp2:
            st.markdown("### 🧬 Bunker 126 (Fixo)")
            st.caption("Simulação Real (Sem vazamento de dados)")
            st.table(bt_bun)
            st.markdown(f'<div class="metric-box-loss">⚠️ Recorde Derrotas (50j): {ml_bun}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box-win">🏆 Recorde Vitórias (50j): {mw_bun}</div>', unsafe_allow_html=True)
            with st.expander("Ver Palpite HOJE (126 Bunker)"):
                st.code(formatar_palpite(palp_bun_hoje), language="text")

    with tab3:
        st.write("Últimos resultados:")
        for p in reversed(historico[-10:]):
            st.markdown(f"<div class='bola-duque'>{p[0]:02} - {p[1]:02}</div>", unsafe_allow_html=True)
            
    st.markdown("---")
    with st.expander("🕒 Grade de Horários da Banca"):
        df_horarios = pd.DataFrame({
            "DIA DA SEMANA": ["Todos os Dias"],
            "HORÁRIOS": [CONFIG_BANCA['horarios']]
        })
        st.table(df_horarios)
else:
    st.warning("⚠️ Adicione os primeiros resultados na barra lateral para começar a análise.")
