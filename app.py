import streamlit as st
import pandas as pd
from collections import Counter
import gspread
from google.oauth2.service_account import Credentials
import requests
from datetime import datetime
import pytz
import time

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS E SOM ---
# =============================================================================
st.set_page_config(page_title="BICHOS da LOTECA", page_icon="🦅", layout="wide")

# Inicializa estado para som
if 'tocar_som' not in st.session_state:
    st.session_state['tocar_som'] = False

# HTML do Som de Sucesso (Um "Plim" agradável)
SOM_SUCESSO_HTML = """
    <audio autoplay>
    <source src="https://www.soundjay.com/buttons/sounds/button-3.mp3" type="audio/mpeg">
    </audio>
    """

def aplicar_estilo_banca(banca):
    """Define as cores baseadas na banca selecionada"""
    
    # Cores Padrão (Dark Mode do Streamlit ou Branco)
    bg_color = "#0e1117" 
    text_color = "#ffffff"
    card_bg = "#262730"
    
    if banca == "LOTEP": # Azul e Branco
        bg_color = "#003366" 
        text_color = "#ffffff"
        card_bg = "rgba(255, 255, 255, 0.1)"
        
    elif banca == "CAMINHODASORTE": # Amarelo e Verde
        bg_color = "#ffeb3b" 
        text_color = "#1b5e20" # Verde escuro para contraste
        card_bg = "rgba(0, 0, 0, 0.05)"
        
    elif banca == "MONTECAI": # Vermelho e Branco
        bg_color = "#b71c1c"
        text_color = "#ffffff"
        card_bg = "rgba(255, 255, 255, 0.1)"

    # CSS Injetado
    st.markdown(f"""
    <style>
        /* Fundo Geral */
        [data-testid="stAppViewContainer"] {{
            background-color: {bg_color};
        }}
        
        /* Textos Gerais */
        h1, h2, h3, h4, h5, h6, p, span, div, label {{
            color: {text_color} !important;
        }}
        
        /* Ajuste para inputs ficarem legíveis */
        .stNumberInput input {{
            color: black !important;
        }}
        
        /* Cards Personalizados */
        .metric-card {{
            background-color: {card_bg};
            padding: 10px;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.2);
            text-align: center;
        }}

        /* Estilo das Bolas */
        .bola-verde {{
            display: inline-block; width: 38px; height: 38px; line-height: 38px;
            border-radius: 50%; background-color: #28a745; color: white !important;
            text-align: center; font-weight: bold; margin: 2px;
            box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white;
        }}
        .bola-azul {{
            display: inline-block; width: 38px; height: 38px; line-height: 38px;
            border-radius: 50%; background-color: #17a2b8; color: white !important;
            text-align: center; font-weight: bold; margin: 2px;
            box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white;
        }}
        .bola-vermelha {{
            display: inline-block; width: 38px; height: 38px; line-height: 38px;
            border-radius: 50%; background-color: #dc3545; color: white !important;
            text-align: center; font-weight: bold; margin: 2px;
            box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white;
        }}
    </style>
    """, unsafe_allow_html=True)

URLS_BANCAS = {
    "LOTEP": "https://www.resultadofacil.com.br/resultados-lotep-de-hoje",
    "CAMINHODASORTE": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-de-hoje",
    "MONTECAI": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-de-hoje"
}

BANCA_OPCOES = ["LOTEP", "CAMINHODASORTE", "MONTECAI"]

# =============================================================================
# --- 2. FUNÇÕES DE BANCO DE DADOS ---
# =============================================================================
def conectar_planilha(nome_aba):
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        try:
            sh = gc.open("CentralBichos")
            worksheet = sh.worksheet(nome_aba)
            return worksheet
        except Exception as e:
            st.sidebar.error(f"Erro planilha: {e}")
            return None
    return None

def carregar_dados(worksheet):
    if worksheet:
        valores = worksheet.col_values(1)
        return [int(v) for v in valores if v.isdigit()]
    return []

def salvar_na_nuvem(worksheet, numero):
    if worksheet:
        try:
            worksheet.append_row([int(numero)])
            return True
        except: return False
    return False

def deletar_ultimo_registro(worksheet):
    if worksheet:
        try:
            valores = worksheet.col_values(1)
            total_linhas = len(valores)
            if total_linhas > 0:
                worksheet.delete_rows(total_linhas)
                return True
        except: return False
    return False

# =============================================================================
# --- 3. LÓGICA E VISUAL ---
# =============================================================================
def html_bolas(lista, cor="verde"):
    html = "<div>"
    classe = f"bola-{cor}"
    for n in lista:
        html += f"<div class='{classe}'>{n:02}</div>"
    html += "</div>"
    return html

def verificar_atualizacao_site(url):
    if not url: return False, "Sem Link", ""
    try:
        fuso_br = pytz.timezone('America/Sao_Paulo')
        hoje = datetime.now(fuso_br)
        datas = [hoje.strftime("%d/%m/%Y"), hoje.strftime("%d-%m-%Y"), hoje.strftime("%d de")]
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            for d in datas:
                if d in r.text: return True, "🟢 SITE ATUALIZADO", f"Data: {d}"
            return False, "🟡 DATA AUSENTE", "Site online, sem data de hoje."
        return False, "🔴 OFF", "Erro site."
    except: return False, "🔴 ERRO", "Falha conexão."

def calcular_ranking_forca_completo(historico):
    if not historico: return []
    hist_reverso = historico[::-1]
    scores = {g: 0 for g in range(1, 26)}
    c_curto = Counter(hist_reverso[:10])
    for g, f in c_curto.items(): scores[g] += (f * 2.0)
    c_medio = Counter(hist_reverso[:50])
    for g, f in c_medio.items(): scores[g] += (f * 1.0)
    rank = sorted(scores.items(), key=lambda x: -x[1])
    return [g for g, s in rank]

def calcular_ranking_atraso_completo(historico):
    if not historico: return []
    atrasos = {}
    total = len(historico)
    for b in range(1, 26):
        indices = [i for i, x in enumerate(historico) if x == b]
        val = total - 1 - indices[-1] if indices else total
        atrasos[b] = val
    rank = sorted(atrasos.items(), key=lambda x: -x[1])
    return [g for g, s in rank]

def analisar_dna_banca(historico):
    if len(historico) < 35: return 0, "Calibrando..."
    acertos = 0
    analise = 25
    for i in range(analise):
        idx = len(historico) - 1 - i
        saiu = historico[idx]
        passado = historico[:idx]
        ranking = calcular_ranking_forca_completo(passado)[:12]
        if saiu in ranking: acertos += 1
    score = (acertos / analise) * 100
    if score >= 65: status = "🎯 DISCIPLINADA"
    elif score >= 45: status = "⚖️ EQUILIBRADA"
    else: status = "🎲 CAÓTICA"
    return score, status

def gerar_palpite_estrategico(historico, modo_crise=False):
    todos_forca = calcular_ranking_forca_completo(historico)
    if modo_crise:
        top8 = todos_forca[:8]
        todos_atrasos = calcular_ranking_atraso_completo(historico)
        top4_atraso = []
        for b in todos_atrasos:
            if b not in top8:
                top4_atraso.append(b)
            if len(top4_atraso) == 4: break
        return top8 + top4_atraso, []
    else:
        return todos_forca[:12], todos_forca[12:14]

def gerar_backtest_e_status(historico):
    if len(historico) < 30: return pd.DataFrame(), False
    derrotas = 0
    resultados = []
    inicio = max(0, len(historico) - 25)
    for i in range(inicio, len(historico)):
        saiu = historico[i]
        passado = historico[:i]
        crise = derrotas >= 2
        p_princ, p_cob = gerar_palpite_estrategico(passado, crise)
        status = "❌"
        if saiu in (p_princ + p_cob):
            status = "💚"
            derrotas = 0
        else:
            derrotas += 1
        if i >= len(historico) - 5:
            resultados.append({"JOGO": f"#{len(historico)-i}", "SAIU": f"{saiu:02}", "RES": status})
    return pd.DataFrame(resultados[::-1]), derrotas >= 2

# =============================================================================
# --- 4. INTERFACE PRINCIPAL ---
# =============================================================================

# Toca som se o estado estiver ativado
if st.session_state['tocar_som']:
    st.markdown(SOM_SUCESSO_HTML, unsafe_allow_html=True)
    st.session_state['tocar_som'] = False # Desliga para não tocar no refresh

with st.sidebar:
    st.header("🦅 MENU")
    banca_selecionada = st.selectbox("Banca:", BANCA_OPCOES)
    
    st.markdown("---")
    st.write("📝 **Novo Resultado**")
    novo_bicho = st.number_input("Grupo:", 1, 25, 1)
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 SALVAR", type="primary"):
            aba = conectar_planilha(banca_selecionada)
            if aba and salvar_na_nuvem(aba, novo_bicho):
                st.session_state['tocar_som'] = True # Ativa o som
                st.toast("Salvo! 🔔", icon="✅")
                time.sleep(0.5) # Pequena pausa para garantir
                st.rerun()
    with col_btn2:
        if st.button("🔄 REBOOT"):
            st.rerun()

    with st.expander("🗑️ Área de Perigo"):
        if st.button("APAGAR ÚLTIMO"):
            aba = conectar_planilha(banca_selecionada)
            if aba and deletar_ultimo_registro(aba):
                st.toast("Apagado!", icon="🗑️")
                st.rerun()

# Aplica as cores antes de carregar o resto
aplicar_estilo_banca(banca_selecionada)

st.title("🦅 BICHOS da LOTECA")
aba_ativa = conectar_planilha(banca_selecionada)

if aba_ativa:
    historico = carregar_dados(aba_ativa)
    
    if len(historico) > 0:
        # --- TOPO SIMPLIFICADO ---
        link = URLS_BANCAS.get(banca_selecionada)
        site_on, site_tit, _ = verificar_atualizacao_site(link)
        
        col_mon1, col_mon2 = st.columns([3, 1])
        with col_mon1:
            st.caption(f"Monitor: {site_tit}")
        with col_mon2:
            if link: st.link_button("🔗 Site", link)

        st.markdown("---")
        
        # --- CÁLCULOS ---
        df_back, EM_CRISE = gerar_backtest_e_status(historico)
        palpite_p, palpite_c = gerar_palpite_estrategico(historico, EM_CRISE)
        
        # --- PALPITES ---
        if EM_CRISE:
            st.error("🚨 MODO CRISE: Lista de Recuperação")
            st.markdown(html_bolas(palpite_p, "vermelha"), unsafe_allow_html=True)
            st.code(", ".join([f"{n:02}" for n in palpite_p]), language="text")
            
        else:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.success("🔥 TOP 12 (Principal)")
                st.markdown(html_bolas(palpite_p, "verde"), unsafe_allow_html=True)
                st.code(", ".join([f"{n:02}" for n in palpite_p]), language="text")
            with c2:
                st.info("❄️ COB (2)")
                st.markdown(html_bolas(palpite_c, "azul"), unsafe_allow_html=True)
                st.code(", ".join([f"{n:02}" for n in palpite_c]), language="text")

        # --- ABA DE HISTÓRICO E DNA (Nova Localização) ---
        with st.expander("📊 Histórico & DNA da Banca", expanded=True):
            
            # Diagnóstico movido para CÁ
            score, status_dna = analisar_dna_banca(historico)
            
            cd1, cd2 = st.columns(2)
            with cd1:
                st.metric("Obediência (25 jogos)", f"{int(score)}%")
            with cd2:
                st.metric("Status DNA", status_dna)
                
            st.table(df_back)

    else:
        st.warning("Adicione dados pela barra lateral.")

else:
    st.info("Conectando...")
