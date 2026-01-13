import streamlit as st
import pandas as pd
from collections import Counter
import gspread
from google.oauth2.service_account import Credentials
import requests
from datetime import datetime
import pytz
import time
import base64

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS E SOM ---
# =============================================================================
st.set_page_config(page_title="BICHOS da LOTECA", page_icon="🦅", layout="wide")

if 'tocar_som_salvar' not in st.session_state:
    st.session_state['tocar_som_salvar'] = False
if 'tocar_som_apagar' not in st.session_state:
    st.session_state['tocar_som_apagar'] = False

def reproduzir_som(tipo):
    if tipo == 'sucesso':
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=success-1-6297.mp3"
    elif tipo == 'alerta': # Som de erro/alerta
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/09/audio_0083556434.mp3?filename=error-2-126514.mp3"
    else:
        sound_url = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3?filename=crumpling-paper-1-6240.mp3"
    st.markdown(f"""
        <audio autoplay style="display:none;">
            <source src="{sound_url}" type="audio/mpeg">
        </audio>
    """, unsafe_allow_html=True)

def aplicar_estilo_banca(banca, bloqueado=False):
    bg_color = "#0e1117" 
    text_color = "#ffffff"
    card_bg = "#262730"
    
    if bloqueado:
        # ESTILO DE BLOQUEIO (CINZA ESCURO / PRETO)
        bg_color = "#1a1a1a"
        text_color = "#a0a0a0"
        card_bg = "#000000"
    else:
        if banca == "LOTEP":
            bg_color = "#003366" 
            text_color = "#ffffff"
            card_bg = "rgba(255, 255, 255, 0.1)"
        elif banca == "CAMINHODASORTE":
            bg_color = "#054a29"  
            text_color = "#ffffff" 
            card_bg = "rgba(255, 255, 255, 0.1)"
        elif banca == "MONTECAI":
            bg_color = "#b71c1c"
            text_color = "#ffffff"
            card_bg = "rgba(255, 255, 255, 0.1)"

    st.markdown(f"""
    <style>
        [data-testid="stAppViewContainer"] {{ background-color: {bg_color}; transition: background-color 0.5s; }}
        h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {{ color: {text_color} !important; }}
        .stNumberInput input {{ color: white !important; caret-color: white !important; }}
        [data-testid="stTable"] {{ background-color: transparent !important; color: white !important; }}
        thead tr th {{ color: {text_color} !important; }}
        tbody tr td {{ color: {text_color} !important; }}
        .metric-card {{ background-color: {card_bg}; padding: 10px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.2); text-align: center; }}
        .stAudio {{ display: none; }}
        
        /* Bolas */
        .bola-verde {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #28a745; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-azul {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #17a2b8; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-vermelha {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #dc3545; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-cinza {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #555; color: #ccc !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #777; }}
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
# --- 3. LÓGICA V27 - ESPECÍFICA POR BANCA ---
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

def calcular_ranking_forca_completo(historico, banca="PADRAO"):
    """
    V27: Lógica Diferenciada.
    - PADRAO: Olha longo prazo (50 jogos).
    - CAMINHODASORTE: Olha CURTÍSSIMO prazo (8 jogos) para pegar tendências rápidas.
    """
    if not historico: return []
    hist_reverso = historico[::-1]
    scores = {g: 0 for g in range(1, 26)}
    
    if banca == "CAMINHODASORTE":
        # LÓGICA TURBO (Para banca difícil)
        # Foca drasticamente nos últimos 8 resultados
        c_ultra_curto = Counter(hist_reverso[:8])
        for g, f in c_ultra_curto.items(): scores[g] += (f * 4.0) # Peso enorme no recente
        
        # Ignora quase todo o resto para não poluir
        c_curto = Counter(hist_reverso[:15])
        for g, f in c_curto.items(): scores[g] += (f * 1.0)
        
    else:
        # LÓGICA CLÁSSICA (Para bancas estáveis - Lotep/Montecai)
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

def analisar_dna_banca(historico, banca):
    if len(historico) < 35: return 0, "Calibrando..."
    acertos = 0
    analise = 25
    for i in range(analise):
        idx = len(historico) - 1 - i
        saiu = historico[idx]
        passado = historico[:idx]
        ranking = calcular_ranking_forca_completo(passado, banca)[:12]
        if saiu in ranking: acertos += 1
    score = (acertos / analise) * 100
    if score >= 65: status = "DISCIPLINADA"
    elif score >= 45: status = "EQUILIBRADA"
    else: status = "CAÓTICA"
    return score, status

def gerar_palpite_estrategico(historico, banca, modo_crise=False):
    # Passamos a banca para o calculo de força saber qual lógica usar
    todos_forca = calcular_ranking_forca_completo(historico, banca)
    
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

def gerar_backtest_e_status(historico, banca):
    if len(historico) < 30: return pd.DataFrame(), False, 0
    derrotas = 0
    resultados = []
    inicio = max(0, len(historico) - 25)
    
    for i in range(inicio, len(historico)):
        saiu = historico[i]
        passado = historico[:i]
        crise = derrotas >= 2
        p_princ, p_cob = gerar_palpite_estrategico(passado, banca, crise)
        status = "❌"
        if saiu in (p_princ + p_cob):
            status = "💚"
            derrotas = 0
        else:
            derrotas += 1
        if i >= len(historico) - 5:
            resultados.append({"JOGO": f"#{len(historico)-i}", "SAIU": f"{saiu:02}", "RES": status})
            
    # Retorna também o numero exato de derrotas atuais
    return pd.DataFrame(resultados[::-1]), derrotas >= 2, derrotas

# =============================================================================
# --- 4. INTERFACE PRINCIPAL ---
# =============================================================================

if st.session_state['tocar_som_salvar']:
    reproduzir_som('sucesso')
    st.session_state['tocar_som_salvar'] = False

if st.session_state['tocar_som_apagar']:
    reproduzir_som('apagar')
    st.session_state['tocar_som_apagar'] = False

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
                st.session_state['tocar_som_salvar'] = True
                st.toast("Salvo! 🔔", icon="✅")
                time.sleep(0.5)
                st.rerun()
    with col_btn2:
        if st.button("🔄 REBOOT"):
            st.rerun()
            
    with st.expander("🗑️ Área de Perigo"):
        if st.button("APAGAR ÚLTIMO"):
            aba = conectar_planilha(banca_selecionada)
            if aba and deletar_ultimo_registro(aba):
                st.session_state['tocar_som_apagar'] = True
                st.toast("Apagado! 🗑️", icon="🗑️")
                time.sleep(0.5)
                st.rerun()

aba_ativa = conectar_planilha(banca_selecionada)

if aba_ativa:
    historico = carregar_dados(aba_ativa)
    if len(historico) > 0:
        
        # --- CÁLCULOS CENTRAIS ---
        df_back, EM_CRISE, qtd_derrotas = gerar_backtest_e_status(historico, banca_selecionada)
        palpite_p, palpite_cob = gerar_palpite_estrategico(historico, banca_selecionada, EM_CRISE)
        score, status_dna = analisar_dna_banca(historico, banca_selecionada)
        
        # --- LÓGICA DE TRAVA DE SEGURANÇA (NOVIDADE V27) ---
        # Se for Caminho da Sorte e tiver 3 ou mais derrotas, BLOQUEIA.
        MODO_BLOQUEIO = False
        if banca_selecionada == "CAMINHODASORTE" and qtd_derrotas >= 3:
            MODO_BLOQUEIO = True
        
        # Aplica o estilo (Se bloqueado, fica tudo cinza/preto)
        aplicar_estilo_banca(banca_selecionada, bloqueado=MODO_BLOQUEIO)
        
        st.title("🦅 BICHOS da LOTECA")

        # --- CABEÇALHO ---
        link = URLS_BANCAS.get(banca_selecionada)
        site_on, site_tit, _ = verificar_atualizacao_site(link)
        
        col_mon1, col_mon2 = st.columns([3, 1])
        with col_mon1: st.caption(f"Monitor: {site_tit}")
        with col_mon2: 
            if link: st.link_button("🔗 Site", link)

        # --- 1. DIAGNÓSTICO ---
        with st.expander("📊 Diagnóstico & Histórico da Banca", expanded=True):
            dados_dna = {
                "OBEDIÊNCIA": [f"{int(score)}%"],
                "DNA STATUS": [status_dna]
            }
            st.table(pd.DataFrame(dados_dna))
            st.table(df_back)

        st.markdown("---")

        # --- TELA DE BLOQUEIO OU PALPITES ---
        if MODO_BLOQUEIO:
            st.error(f"⛔ TRAVA DE SEGURANÇA ATIVADA: {qtd_derrotas} Derrotas Seguidas")
            st.markdown("""
            <div style="background-color: #330000; padding: 20px; border-radius: 10px; border: 2px solid red; text-align: center;">
                <h2>NÃO APOSTE AGORA!</h2>
                <p>A banca <b>Caminho da Sorte</b> está extremamente instável.</p>
                <p>O sistema entrou em modo de <b>Simulação de Recuperação</b>.</p>
                <hr>
                <p>Abaixo estão os números que o robô está testando para tentar vencer a banca.</p>
                <p><b>Aguarde sair uma VITÓRIA VIRTUAL (💚) no Histórico antes de voltar a jogar dinheiro.</b></p>
            </div>
            """, unsafe_allow_html=True)
            
            # Mostra palpites "apagados/cinzas"
            st.write("🤖 Palpites de Teste (Simulação):")
            st.markdown(html_bolas(palpite_p, "cinza"), unsafe_allow_html=True)
            
        else:
            # FLUXO NORMAL DE JOGO
            tab_palpites, tab_graficos = st.tabs(["🏠 Palpites do Robô", "📈 Gráficos & Atrasos"])

            with tab_palpites:
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
                        st.markdown(html_bolas(palpite_cob, "azul"), unsafe_allow_html=True)
                        st.code(", ".join([f"{n:02}" for n in palpite_cob]), language="text")

            with tab_graficos:
                st.write("### 🐢 Top Atrasados")
                todos_atrasos = calcular_ranking_atraso_completo(historico)
                atrasos_dict = {}
                total = len(historico)
                for b in todos_atrasos[:12]:
                    indices = [i for i, x in enumerate(historico) if x == b]
                    val = total - 1 - indices[-1] if indices else total
                    atrasos_dict[f"Gr {b:02}"] = val
                st.bar_chart(pd.DataFrame.from_dict(atrasos_dict, orient='index', columns=['Jogos sem sair']))
                
                st.write("### 📊 Frequência")
                recentes = historico[-50:] 
                contagem = Counter(recentes)
                df_freq = pd.DataFrame.from_dict(contagem, orient='index', columns=['Vezes'])
                st.bar_chart(df_freq)

    else:
        st.warning("⚠️ Planilha vazia.")
else:
    st.info("Conectando...")
