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

# --- CENTRAL DE CONFIGURAÇÃO ---
CONFIG_BANCAS = {
    "LOTEP": {
        "display_name": "LOTEP PARAÍBA",
        "logo_url": "https://cdn-icons-png.flaticon.com/512/731/731985.png", 
        "cor_fundo": "#003366", 
        "cor_texto": "#ffffff",
        "card_bg": "rgba(255, 255, 255, 0.1)",
        "url_site": "https://www.resultadofacil.com.br/resultados-lotep-de-hoje",
        "horarios": {
            "segsab": "10:45 🔹 12:45 🔹 15:45 🔹 18:00",
            "dom": "10:00 🔹 12:45"
        }
    },
    "CAMINHODASORTE": {
        "display_name": "CAMINHO DA SORTE",
        "logo_url": "https://cdn-icons-png.flaticon.com/512/732/732220.png", 
        "cor_fundo": "#054a29", 
        "cor_texto": "#ffffff",
        "card_bg": "rgba(255, 255, 255, 0.1)",
        "url_site": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-de-hoje",
        "horarios": {
            "segsab": "09:40 🔹 11:00 🔹 12:40 🔹 14:00 🔹 15:40 🔹 17:00 🔹 18:30 🔹 20:00 🔹 21:00",
            "dom": "09:40 🔹 11:00 🔹 12:40"
        }
    },
    "MONTECAI": {
        "display_name": "MONTE CARLOS",
        "logo_url": "https://cdn-icons-png.flaticon.com/512/732/732217.png", 
        "cor_fundo": "#b71c1c", 
        "cor_texto": "#ffffff",
        "card_bg": "rgba(255, 255, 255, 0.1)",
        "url_site": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-de-hoje",
        "horarios": {
            "segsab": "10:00 🔹 11:00 🔹 12:40 🔹 14:00 🔹 15:40 🔹 17:00 🔹 18:30 🔹 21:00",
            "dom": "10:00 🔹 11:00 🔹 12:40"
        }
    }
}

BANCA_OPCOES = list(CONFIG_BANCAS.keys())

# Estados de Som
if 'tocar_som_salvar' not in st.session_state:
    st.session_state['tocar_som_salvar'] = False
if 'tocar_som_apagar' not in st.session_state:
    st.session_state['tocar_som_apagar'] = False

def reproduzir_som(tipo):
    if tipo == 'sucesso':
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=success-1-6297.mp3"
    elif tipo == 'alerta':
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/09/audio_0083556434.mp3?filename=error-2-126514.mp3"
    else:
        sound_url = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3?filename=crumpling-paper-1-6240.mp3"
    st.markdown(f"""
        <audio autoplay style="display:none;">
            <source src="{sound_url}" type="audio/mpeg">
        </audio>
    """, unsafe_allow_html=True)

def aplicar_estilo_banca(banca_key, bloqueado=False):
    config = CONFIG_BANCAS.get(banca_key)
    
    if bloqueado:
        bg_color = "#1a1a1a"
        text_color = "#a0a0a0"
        card_bg = "#000000"
    else:
        bg_color = config["cor_fundo"]
        text_color = config["cor_texto"]
        card_bg = config["card_bg"]

    st.markdown(f"""
    <style>
        [data-testid="stAppViewContainer"] {{ background-color: {bg_color}; transition: background-color 0.5s; }}
        h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {{ color: {text_color} !important; }}
        .stNumberInput input {{ color: white !important; caret-color: white !important; }}
        .stSelectbox div[data-baseweb="select"] > div {{ color: black !important; }}
        
        [data-testid="stTable"] {{ background-color: transparent !important; color: white !important; }}
        thead tr th {{ color: {text_color} !important; text-align: center !important; border-bottom: 1px solid rgba(255,255,255,0.3) !important; }}
        tbody tr td {{ color: {text_color} !important; text-align: center !important; border-bottom: 1px solid rgba(255,255,255,0.1) !important; }}
        
        .metric-card {{ background-color: {card_bg}; padding: 10px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.2); text-align: center; }}
        .stAudio {{ display: none; }}
        
        /* Bolas */
        .bola-verde {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #28a745; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-azul {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #17a2b8; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-vermelha {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #dc3545; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-cinza {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #555; color: #ccc !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #777; }}
        
        .bola-25 {{ display: inline-block; width: 40px; height: 40px; line-height: 40px; border-radius: 50%; background-color: white; color: black !important; text-align: center; font-weight: bold; margin: 2px; border: 3px solid #d4af37; box-shadow: 0px 0px 10px #d4af37; }}
    </style>
    """, unsafe_allow_html=True)

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
        grupos = [int(v) for v in valores if v.isdigit()]
        try:
            horarios = worksheet.col_values(2)
            ultimo_horario = horarios[-1] if horarios else ""
        except:
            ultimo_horario = ""
        return grupos, ultimo_horario
    return [], ""

def salvar_na_nuvem(worksheet, numero, horario):
    if worksheet:
        try:
            worksheet.append_row([int(numero), str(horario)])
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
# --- 3. LÓGICA DO ROBÔ ---
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

def calcular_proximo_horario(banca, ultimo_horario):
    if not ultimo_horario: return "Próximo Sorteio"
    fuso_br = pytz.timezone('America/Sao_Paulo')
    dia_semana = datetime.now(fuso_br).weekday()
    config = CONFIG_BANCAS[banca]
    if dia_semana == 6: 
        lista_str = config['horarios']['dom']
    else:
        lista_str = config['horarios']['segsab']
    lista_horarios = [h.strip() for h in lista_str.split('🔹')]
    try:
        indice_atual = lista_horarios.index(ultimo_horario)
        if indice_atual + 1 < len(lista_horarios):
            proximo = lista_horarios[indice_atual + 1]
            return f"Palpite para: {proximo}"
        else:
            return "Palpite para: Amanhã/Próximo Dia"
    except:
        return "Palpite para: Próximo Sorteio"

def calcular_ranking_forca_completo(historico, banca="PADRAO"):
    if not historico: return []
    hist_reverso = historico[::-1]
    scores = {g: 0 for g in range(1, 26)}
    
    if banca == "CAMINHODASORTE" or banca == "MONTECAI":
        c_ultra_curto = Counter(hist_reverso[:8])
        for g, f in c_ultra_curto.items(): scores[g] += (f * 4.0)
        c_curto = Counter(hist_reverso[:15])
        for g, f in c_curto.items(): scores[g] += (f * 1.0)
    else:
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
            
    return pd.DataFrame(resultados[::-1]), derrotas >= 2, derrotas

def obter_comparativo_geral():
    dados_comp = {"JOGO": ["#1", "#2", "#3", "#4", "#5"]}
    for b_key in BANCA_OPCOES:
        nome_curto = CONFIG_BANCAS[b_key]['display_name'].split(" ")[0] 
        try:
            aba = conectar_planilha(b_key)
            if aba:
                hist, _ = carregar_dados(aba)
                if len(hist) > 0:
                    df, _, _ = gerar_backtest_e_status(hist, b_key)
                    status_list = df['RES'].tolist()
                    while len(status_list) < 5:
                        status_list.append("-")
                    dados_comp[nome_curto] = status_list
                else:
                    dados_comp[nome_curto] = ["-"] * 5
            else:
                dados_comp[nome_curto] = ["Erro"] * 5
        except:
            dados_comp[nome_curto] = ["Erro"] * 5
    return pd.DataFrame(dados_comp)

# --- ANÁLISE PAR/ÍMPAR V36 (COM FATOR 25 NEUTRO) ---
def analisar_par_impar_neutro(historico):
    if not historico: return None, 0, 0, 0, 0
    
    # Filtra: Remove 25 das contas de sequencia e balanço
    hist_validos = [x for x in historico if x != 25]
    
    if not hist_validos: return "NEUTRO", 0, 0, 0, 0
    
    # 1. Sequencia Atual (Ignorando os 25 que sairam)
    ultimo_valido = hist_validos[-1]
    eh_par = (ultimo_valido % 2 == 0)
    tipo_atual = "PAR" if eh_par else "ÍMPAR"
    seq = 0
    for x in reversed(hist_validos):
        if (x % 2 == 0) == eh_par: seq += 1
        else: break
        
    # 2. Balanço nos últimos 50 (Válidos)
    recorte = hist_validos[-50:]
    qtd_par = len([x for x in recorte if x % 2 == 0])
    qtd_impar = len([x for x in recorte if x % 2 != 0])
    
    # 3. Atraso do 25 (Vaca)
    atraso_25 = 0
    for x in reversed(historico):
        if x == 25: break
        atraso_25 += 1
        
    return tipo_atual, seq, qtd_par, qtd_impar, atraso_25

# --- ANÁLISE ALTO/BAIXO V36 (COM FATOR 25 NEUTRO) ---
def analisar_alto_baixo_neutro(historico):
    if not historico: return None, 0, 0, 0, 0
    
    # Filtra 25
    hist_validos = [x for x in historico if x != 25]
    if not hist_validos: return "NEUTRO", 0, 0, 0, 0
    
    # Baixo: 1 a 12 | Alto: 13 a 24 | (25 excluido)
    ultimo_valido = hist_validos[-1]
    eh_baixo = (1 <= ultimo_valido <= 12)
    tipo_atual = "BAIXO" if eh_baixo else "ALTO"
    seq = 0
    for x in reversed(hist_validos):
        x_baixo = (1 <= x <= 12)
        if x_baixo == eh_baixo: seq += 1
        else: break
        
    recorte = hist_validos[-50:]
    qtd_baixo = len([x for x in recorte if 1 <= x <= 12])
    qtd_alto = len([x for x in recorte if 13 <= x <= 24])
    
    # Atraso 25 (mesma logica)
    atraso_25 = 0
    for x in reversed(historico):
        if x == 25: break
        atraso_25 += 1
        
    return tipo_atual, seq, qtd_baixo, qtd_alto, atraso_25

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
    st.header("🦅 MENU DE JOGO")
    banca_selecionada = st.selectbox("Selecione a Banca:", BANCA_OPCOES)
    
    fuso_br = pytz.timezone('America/Sao_Paulo')
    dia_semana = datetime.now(fuso_br).weekday()
    config_banca = CONFIG_BANCAS[banca_selecionada]
    if dia_semana == 6: 
        lista_horarios_str = config_banca['horarios']['dom']
    else:
        lista_horarios_str = config_banca['horarios']['segsab']
    lista_horarios = [h.strip() for h in lista_horarios_str.split('🔹')]
    
    st.markdown("---")
    st.write("📝 **Registrar Sorteio**")
    
    novo_horario = st.selectbox("Horário do Resultado:", lista_horarios)
    novo_bicho = st.number_input("Grupo (Resultado):", 1, 25, 1)
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 SALVAR", type="primary"):
            aba = conectar_planilha(banca_selecionada)
            if aba and salvar_na_nuvem(aba, novo_bicho, novo_horario):
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
    historico, ultimo_horario_salvo = carregar_dados(aba_ativa)
    
    if len(historico) > 0:
        
        # CÁLCULOS
        df_back, EM_CRISE, qtd_derrotas = gerar_backtest_e_status(historico, banca_selecionada)
        palpite_p, palpite_cob = gerar_palpite_estrategico(historico, banca_selecionada, EM_CRISE)
        score, status_dna = analisar_dna_banca(historico, banca_selecionada)
        texto_horario_futuro = calcular_proximo_horario(banca_selecionada, ultimo_horario_salvo)
        
        # ANÁLISES EXTRAS (V36 - NEUTRO)
        tipo_pi, seq_pi, t_par, t_impar, atr_25 = analisar_par_impar_neutro(historico)
        tipo_ab, seq_ab, t_baixo, t_alto, _ = analisar_alto_baixo_neutro(historico)
        
        # BLOQUEIO
        MODO_BLOQUEIO = False
        if (banca_selecionada == "CAMINHODASORTE" or banca_selecionada == "MONTECAI") and qtd_derrotas >= 3:
            MODO_BLOQUEIO = True
        
        aplicar_estilo_banca(banca_selecionada, bloqueado=MODO_BLOQUEIO)
        config_atual = CONFIG_BANCAS[banca_selecionada]

        # CABEÇALHO
        col_head1, col_head2, col_head3 = st.columns([1, 2, 1])
        with col_head2:
            st.markdown(f"""
                <div style='text-align: center;'>
                    <img src='{config_atual['logo_url']}' width='100' style='margin-bottom: 10px;'>
                    <h1 style='margin:0; padding:0; font-size: 2.5rem;'>{config_atual['display_name']}</h1>
                </div>
            """, unsafe_allow_html=True)
        st.write("") 

        link = config_atual['url_site']
        site_on, site_tit, _ = verificar_atualizacao_site(link)
        col_mon1, col_mon2 = st.columns([3, 1])
        with col_mon1: 
            info_ultimo = f"Último: Grupo {historico[-1]:02}"
            if ultimo_horario_salvo:
                info_ultimo += f" ({ultimo_horario_salvo})"
            st.info(f"📡 {site_tit}  |  🏁 {info_ultimo}")
        with col_mon2: 
            if link: st.link_button("🔗 Abrir Site", link)

        # DIAGNÓSTICO
        with st.expander("📊 Diagnóstico & Histórico", expanded=True):
            tab_diag, tab_comp = st.tabs(["🔍 Diagnóstico Atual", "⚔️ Comparativo Geral"])
            with tab_diag:
                dados_dna = {"OBEDIÊNCIA": [f"{int(score)}%"], "DNA STATUS": [status_dna]}
                st.table(pd.DataFrame(dados_dna))
                st.table(df_back) 
            with tab_comp:
                st.caption("Comparação em Tempo Real")
                if st.button("🔄 Carregar Comparativo Geral"):
                    with st.spinner("Analisando todas as bancas..."):
                        df_comp = obter_comparativo_geral()
                        st.table(df_comp)
                else:
                    st.info("Clique no botão acima para carregar.")

        with st.expander("🕒 Grade de Horários da Banca"):
            df_horarios = pd.DataFrame({
                "DIA DA SEMANA": ["Segunda a Sábado", "Domingo"],
                "HORÁRIOS": [config_atual['horarios']['segsab'], config_atual['horarios']['dom']]
            })
            st.table(df_horarios)

        st.markdown("---")

        if MODO_BLOQUEIO:
            st.error(f"⛔ TRAVA DE SEGURANÇA: {qtd_derrotas} Derrotas Seguidas")
            st.markdown("""
            <div style="background-color: #330000; padding: 20px; border-radius: 10px; border: 2px solid red; text-align: center;">
                <h2>NÃO APOSTE AGORA!</h2>
                <p>A banca está muito instável. Aguarde uma vitória virtual.</p>
            </div>
            """, unsafe_allow_html=True)
            st.write("🤖 Palpites de Simulação:")
            st.markdown(html_bolas(palpite_p, "cinza"), unsafe_allow_html=True)
            st.markdown("---")

        tab_palpites, tab_parimpar, tab_altobaixo, tab_graficos = st.tabs(["🏠 Palpites", "⚖️ Par/Ímpar (50%)", "📏 Alto/Baixo (50%)", "📈 Gráficos"])

        with tab_palpites:
            if MODO_BLOQUEIO:
                st.info("👀 Modo Simulação Ativo. Veja os palpites cinzas acima.")
            else:
                if EM_CRISE:
                    st.error(f"🚨 MODO CRISE - {texto_horario_futuro}")
                    st.markdown(html_bolas(palpite_p, "vermelha"), unsafe_allow_html=True)
                    st.code(", ".join([f"{n:02}" for n in palpite_p]), language="text")
                else:
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.success(f"🔥 TOP 12 - {texto_horario_futuro}")
                        st.markdown(html_bolas(palpite_p, "verde"), unsafe_allow_html=True)
                        st.code(", ".join([f"{n:02}" for n in palpite_p]), language="text")
                    with c2:
                        st.info("❄️ COB (2)")
                        st.markdown(html_bolas(palpite_cob, "azul"), unsafe_allow_html=True)
                        st.code(", ".join([f"{n:02}" for n in palpite_cob]), language="text")
        
        with tab_parimpar:
            # MOSTRADOR DO 25 (VACA)
            st.write("### 🐮 Fator 25 (Neutro)")
            col_v1, col_v2 = st.columns([1, 3])
            with col_v1:
                st.markdown(f"<div class='bola-25'>25</div>", unsafe_allow_html=True)
            with col_v2:
                if atr_25 == 0:
                    st.warning("⚠️ O 25 ACABOU DE SAIR! As estatísticas podem resetar.")
                elif atr_25 >= 15:
                    st.success(f"🚨 **ATRASADO HÁ {atr_25} JOGOS!** Ideal para Cobertura.")
                else:
                    st.info(f"Atraso normal: {atr_25} jogos sem sair.")
            
            st.markdown("---")
            st.write("### ⚖️ Balança P/I (Sem o 25)")
            col_pi1, col_pi2 = st.columns(2)
            total_validos = t_par + t_impar
            if total_validos == 0: total_validos = 1 # Evitar div zero
            
            col_pi1.metric("Pares (2-24)", f"{t_par}", delta=f"{(t_par/total_validos)*100:.0f}%")
            col_pi2.metric("Ímpares (1-23)", f"{t_impar}", delta=f"{(t_impar/total_validos)*100:.0f}%")
            
            # Alerta P/I
            if seq_pi >= 4:
                cor_alerta = "red"
                texto_alerta = f"⚠️ ALERTA: {seq_pi} {tipo_pi}ES SEGUIDOS!"
                sugestao = f"👉 Dica: Aposte no **{'ÍMPAR' if tipo_pi == 'PAR' else 'PAR'}**"
            elif seq_pi == 3:
                cor_alerta = "orange"
                texto_alerta = f"Fique de Olho: {seq_pi} {tipo_pi}es Seguidos"
                sugestao = "Aguarde..."
            else:
                cor_alerta = "green"
                texto_alerta = f"Normal: {seq_pi} {tipo_pi} seguido(s)"
                sugestao = "Equilibrado."
            
            st.markdown(f"<h3 style='color:{cor_alerta}'>{texto_alerta}</h3>", unsafe_allow_html=True)
            st.info(sugestao)
            
            st.write("Histórico Visual (P=Azul, I=Amarelo, 25=Branco):")
            html_seq = "<div>"
            for x in historico[::-1][:12]:
                if x == 25:
                    txt, cor_b, cor_txt = "25", "white", "black"
                    borda = "3px solid #d4af37"
                else:
                    txt = "P" if x%2==0 else "I"
                    cor_b = "#007bff" if txt=="P" else "#ffc107"
                    cor_txt = "#000" if txt=="I" else "#fff"
                    borda = "none"
                html_seq += f"<span style='display:inline-block;width:30px;height:30px;line-height:30px;border-radius:50%;background-color:{cor_b};color:{cor_txt};text-align:center;margin:2px;font-weight:bold;border:{borda}'>{txt}</span>"
            html_seq += "</div>"
            st.markdown(html_seq, unsafe_allow_html=True)

        with tab_altobaixo:
            st.write("### 🐮 Fator 25 (Neutro)")
            if atr_25 >= 15: st.success(f"🚨 **USE O 25 COMO COBERTURA!** (Atraso: {atr_25})")
            else: st.info(f"Status do 25: Atraso {atr_25}")
            
            st.markdown("---")
            st.write("### 📏 Balança A/B (Sem o 25)")
            col_ab1, col_ab2 = st.columns(2)
            tot_v_ab = t_baixo + t_alto
            if tot_v_ab == 0: tot_v_ab = 1
            
            col_ab1.metric("Baixos (1-12)", f"{t_baixo}", delta=f"{(t_baixo/tot_v_ab)*100:.0f}%")
            col_ab2.metric("Altos (13-24)", f"{t_alto}", delta=f"{(t_alto/tot_v_ab)*100:.0f}%")
            
            if seq_ab >= 4:
                cor_alerta = "red"
                texto_alerta = f"⚠️ ALERTA: {seq_ab} {tipo_ab}OS SEGUIDOS!"
                oposto = 'ALTO' if tipo_ab == 'BAIXO' else 'BAIXO'
                sugestao = f"👉 Dica: Aposte no **{oposto}**"
            elif seq_ab == 3:
                cor_alerta = "orange"
                texto_alerta = f"Fique de Olho: {seq_ab} {tipo_ab}os Seguidos"
                sugestao = "Aguarde..."
            else:
                cor_alerta = "green"
                texto_alerta = f"Normal: {seq_ab} {tipo_ab}o(s) seguido(s)"
                sugestao = "Equilibrado."
            
            st.markdown(f"<h3 style='color:{cor_alerta}'>{texto_alerta}</h3>", unsafe_allow_html=True)
            st.info(sugestao)
            
            st.write("Histórico Visual (B=Ciano, A=Laranja, 25=Branco):")
            html_seq_ab = "<div>"
            for x in historico[::-1][:12]:
                if x == 25:
                    txt, cor_b, cor_txt = "25", "white", "black"
                    borda = "3px solid #d4af37"
                else:
                    is_low = (1 <= x <= 12)
                    txt = "B" if is_low else "A"
                    cor_b = "#17a2b8" if is_low else "#fd7e14"
                    cor_txt = "white"
                    borda = "none"
                html_seq_ab += f"<span style='display:inline-block;width:30px;height:30px;line-height:30px;border-radius:50%;background-color:{cor_b};color:{cor_txt};text-align:center;margin:2px;font-weight:bold;border:{borda}'>{txt}</span>"
            html_seq_ab += "</div>"
            st.markdown(html_seq_ab, unsafe_allow_html=True)

        with tab_graficos:
            st.write("### 🐢 Top Atrasados")
            todos_atrasos = calcular_ranking_atraso_completo(historico)
            atrasos_dict = {}
            total = len(historico)
            for b in todos_atrasos[:12]:
                indices = [i for i, x in enumerate(historico) if x == b]
                val = total - 1 - indices[-1] if indices else total
                atrasos_dict[f"Gr {b:02}"] = val
            st.bar_chart(pd.DataFrame.from_dict(atrasos_dict, orient='index', columns=['Jogos']))
            
            st.write("### 📊 Frequência")
            recentes = historico[-50:] 
            contagem = Counter(recentes)
            df_freq = pd.DataFrame.from_dict(contagem, orient='index', columns=['Vezes'])
            st.bar_chart(df_freq)

    else:
        st.warning("⚠️ Planilha vazia. Adicione o primeiro resultado.")
else:
    st.info("Conectando...")
