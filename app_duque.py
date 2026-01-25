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
# --- 3. LÓGICA DE SIMULAÇÃO ROBUSTA (TIME MACHINE) ---
# =============================================================================

# --- A. MAPAS E UTILITÁRIOS ---
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
    return todos, {"S1": setor1, "S2": setor2, "S3": setor3}

def formatar_palpite(lista_tuplas):
    lista_ordenada = sorted(lista_tuplas)
    texto = ""
    for p in lista_ordenada:
        texto += f"[{p[0]:02},{p[1]:02}], "
    return texto.rstrip(", ")

# --- B. GERADORES DE ESTRATÉGIA (REUTILIZÁVEIS) ---
# Estas funções recebem um "recorte do passado" e devolvem o palpite para aquele momento

def estrategia_bma(historico_slice):
    if len(historico_slice) < 10: return []
    _, mapa_setores = gerar_universo_duques()
    c_duques = Counter(historico_slice)
    
    # Identificar Crise (Atraso)
    atrasos = {"S1": 0, "S2": 0, "S3": 0}
    for nome, lista in mapa_setores.items():
        cnt = 0
        for sorteio in reversed(historico_slice):
            if sorteio in lista: break
            cnt += 1
        atrasos[nome] = cnt
        
    # Identificar Tendência (Freq Recente)
    recorte = historico_slice[-20:]
    freqs = {"S1": 0, "S2": 0, "S3": 0}
    for sorteio in recorte:
        for nome, lista in mapa_setores.items():
            if sorteio in lista:
                freqs[nome] += 1
                break
    
    s_crise = max(atrasos, key=atrasos.get)
    s_trend = max(freqs, key=freqs.get)
    
    def get_best(lista, n):
        return sorted(lista, key=lambda x: c_duques[x], reverse=True)[:n]
    
    if s_crise == s_trend:
        return get_best(mapa_setores[s_crise], 126)
    else:
        p1 = get_best(mapa_setores[s_crise], 63)
        p2 = get_best(mapa_setores[s_trend], 63)
        return list(set(p1 + p2))

def estrategia_setorizada(historico_slice):
    if len(historico_slice) < 10: return []
    _, mapa_setores = gerar_universo_duques()
    c_duques = Counter(historico_slice)
    
    def get_best(lista, n):
        return sorted(lista, key=lambda x: c_duques[x], reverse=True)[:n]
        
    p1 = get_best(mapa_setores["S1"], 42)
    p2 = get_best(mapa_setores["S2"], 42)
    p3 = get_best(mapa_setores["S3"], 42)
    return list(set(p1 + p2 + p3))

def estrategia_dinamica(historico_slice):
    hist_rev = historico_slice[::-1]
    scores = {d: 0 for d in gerar_universo_duques()[0]}
    
    c_curto = Counter(hist_rev[:20])
    c_medio = Counter(hist_rev[:50])
    
    for d, f in c_curto.items(): scores[d] += (f * 3.0)
    for d, f in c_medio.items(): scores[d] += (f * 1.0)
    
    rank = sorted(scores.items(), key=lambda x: -x[1])
    return [d for d, s in rank][:126]

def estrategia_bunker(historico_slice):
    c = Counter(historico_slice)
    rank = c.most_common()
    return [d for d, qtd in rank][:126]

# --- C. MOTOR DE SIMULAÇÃO (ROLLING WINDOW) ---
# Esta função roda qualquer uma das estratégias acima passo a passo no tempo
def rodar_simulacao_real(historico_completo, func_estrategia, n_jogos=50):
    if len(historico_completo) < n_jogos + 10: return pd.DataFrame(), 0, 0, 0
    
    resultados = []
    max_loss = 0; temp_loss = 0
    max_win = 0; temp_win = 0
    
    start_idx = len(historico_completo) - n_jogos
    
    # Loop "Viajando no Tempo"
    for i in range(start_idx, len(historico_completo)):
        # 1. Defina a realidade naquele momento (passado)
        hist_momento = historico_completo[:i]
        resultado_real = historico_completo[i]
        
        # 2. Peça o palpite para a estratégia usando SÓ o passado
        palpite_momento = func_estrategia(hist_momento)
        
        # 3. Confira
        if resultado_real in palpite_momento:
            status = "💚"
            temp_win += 1
            if temp_loss > max_loss: max_loss = temp_loss
            temp_loss = 0
        else:
            status = "❌"
            temp_loss += 1
            if temp_win > max_win: max_win = temp_win
            temp_win = 0
            
        # Salva para tabela (ultimos 20)
        if i >= len(historico_completo) - 20:
            resultados.append({
                "JOGO": f"#{len(historico_completo)-i}",
                "SAIU": f"{resultado_real[0]:02}-{resultado_real[1]:02}",
                "RES": status
            })
            
    # Fecha conta dos recordes
    if temp_loss > max_loss: max_loss = temp_loss
    if temp_win > max_win: max_win = temp_win
    
    # Calcula Streak Atual
    curr_streak = 0
    df_res = pd.DataFrame(resultados[::-1])
    if not df_res.empty:
        for r in df_res.to_dict('records'):
            if r["RES"] == "❌": curr_streak += 1
            else: break
            
    return df_res, max_loss, curr_streak, max_win

# --- D. METRICAS DE STRESS (VISUAL APENAS) ---
def calcular_tabela_stress(historico):
    _, mapa = gerar_universo_duques()
    recorte = historico[-20:]
    tabela = []
    
    # Crise/Trend Atuais (Para Info)
    atrasos = {}; freqs = {}
    
    for nome, lista in mapa.items():
        # Atraso Atual
        atraso = 0
        for x in reversed(historico):
            if x in lista: break
            atraso += 1
        atrasos[nome] = atraso
        
        # Freq Recente
        count = 0
        for x in recorte:
            if x in lista: count += 1
        freqs[nome] = count
        
        # Recordes (Varredura total)
        max_atraso = 0; tmp_atraso = 0
        max_win = 0; tmp_win = 0
        for x in historico:
            if x in lista:
                tmp_win += 1
                if tmp_atraso > max_atraso: max_atraso = tmp_atraso
                tmp_atraso = 0
            else:
                tmp_atraso += 1
                if tmp_win > max_win: max_win = tmp_win
                tmp_win = 0
        if tmp_atraso > max_atraso: max_atraso = tmp_atraso
        if tmp_win > max_win: max_win = tmp_win
        
        tabela.append({
            "SETOR": nome, 
            "ATRASO": atraso, 
            "REC. ATRASO": max_atraso, 
            "REC. SEQ. (V)": max_win
        })
        
    s_crise = max(atrasos, key=atrasos.get)
    s_trend = max(freqs, key=freqs.get)
    
    return pd.DataFrame(tabela), s_crise, s_trend

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
    
    # 1. Dados Estáticos Atuais (Para Tabela e Palpite de HOJE)
    df_stress, s_crise, s_trend = calcular_tabela_stress(historico)
    
    # Palpites para JOGAR HOJE (Baseado em todo histórico)
    palp_bma_hoje = estrategia_bma(historico)
    palp_set_hoje = estrategia_setorizada(historico)
    palp_din_hoje = estrategia_dinamica(historico)
    palp_bun_hoje = estrategia_bunker(historico)
    
    # 2. Simulação Real (Backtest Honesto)
    # Roda as estratégias passo a passo no passado para validar
    with st.spinner("Processando Simulação Real (Isso garante honestidade)..."):
        bt_bma, ml_bma, cl_bma, mw_bma = rodar_simulacao_real(historico, estrategia_bma)
        bt_set, ml_set, cl_set, mw_set = rodar_simulacao_real(historico, estrategia_setorizada)
        bt_din, ml_din, cl_din, mw_din = rodar_simulacao_real(historico, estrategia_dinamica)
        bt_bun, ml_bun, cl_bun, mw_bun = rodar_simulacao_real(historico, estrategia_bunker)
    
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
            if duque in mapa_setores_vis["S1"]: classe, sigla = "bola-s1", "S1"
            elif duque in mapa_setores_vis["S2"]: classe, sigla = "bola-s2", "S2"
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
            with st.expander("Ver Palpite HOJE (126 Duques)"):
                st.code(formatar_palpite(palp_bma_hoje), language="text")
                
        with c_strat2:
            st.markdown("### ⚖️ Setorizada (42x3)")
            st.caption("Equilíbrio entre os 3 setores")
            st.table(bt_set)
            st.markdown(f'<div class="metric-box-loss">⚠️ Recorde Derrotas (50j): {ml_set}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box-win">🏆 Recorde Vitórias (50j): {mw_set}</div>', unsafe_allow_html=True)
            with st.expander("Ver Palpite HOJE (126 Duques)"):
                st.code(formatar_palpite(palp_set_hoje), language="text")

    # --- ABA COMPARATIVO ---
    with tab2:
        col_comp1, col_comp2 = st.columns(2)
        
        with col_comp1:
            st.markdown("### 🚀 Top 126 Dinâmico")
            st.caption("Adapta-se ao momento (Frequência Ponderada)")
            st.table(bt_din)
            st.markdown(f'<div class="metric-box-loss">⚠️ Recorde Derrotas (50j): {ml_din}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box-win">🏆 Recorde Vitórias (50j): {mw_din}</div>', unsafe_allow_html=True)
            with st.expander("Ver Palpite HOJE (126 Dinâmicos)"):
                st.code(formatar_palpite(palp_din_hoje), language="text")
        
        with col_comp2:
            st.markdown("### 🧬 Bunker 126 (Fixo)")
            st.caption("Os 126 Reis da História (Não muda)")
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
