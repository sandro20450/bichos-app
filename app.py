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
if 'tocar_som_salvar' not in st.session_state: st.session_state['tocar_som_salvar'] = False
if 'tocar_som_apagar' not in st.session_state: st.session_state['tocar_som_apagar'] = False
if 'auto_grupo' not in st.session_state: st.session_state['auto_grupo'] = 1
if 'auto_horario_idx' not in st.session_state: st.session_state['auto_horario_idx'] = 0

def reproduzir_som(tipo):
    if tipo == 'sucesso':
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=success-1-6297.mp3"
    elif tipo == 'apagar':
        sound_url = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3?filename=crumpling-paper-1-6240.mp3"
    else: return
    st.markdown(f"""<audio autoplay style="display:none;"><source src="{sound_url}" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

def aplicar_estilo_banca(banca_key):
    config = CONFIG_BANCAS.get(banca_key)
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
        
        /* Bolas de Bicho */
        .bola-verde {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #28a745; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-azul {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #17a2b8; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-ice {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #00bcd4; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; text-shadow: 1px 1px 2px black; }}
        .bola-cinza {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #555; color: #ccc !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #777; }}
        
        .bola-b {{ display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #17a2b8; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #fff; }}
        .bola-m {{ display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #fd7e14; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #fff; }}
        .bola-a {{ display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #dc3545; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #fff; }}
        .bola-25 {{ display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #ffd700; color: black !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #fff; }}
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
        except: return None
    return None

def carregar_dados(worksheet):
    if worksheet:
        valores = worksheet.col_values(1)
        grupos = [int(v) for v in valores if v.isdigit()]
        try:
            horarios = worksheet.col_values(2)
            ultimo_horario = horarios[-1] if horarios else ""
        except: ultimo_horario = ""
        return grupos, ultimo_horario
    return [], ""

def salvar_na_nuvem(worksheet, dados_jogo, horario):
    if worksheet:
        try:
            data_hoje = datetime.now().strftime("%Y-%m-%d")
            linha = [int(dados_jogo), str(horario), data_hoje]
            worksheet.append_row(linha)
            return True
        except: return False
    return False

def deletar_ultimo_registro(worksheet):
    if worksheet:
        try:
            todos = worksheet.get_all_values()
            total_linhas = len(todos)
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
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            datas = [hoje.strftime("%d/%m/%Y"), hoje.strftime("%d-%m-%Y"), hoje.strftime("%d de")]
            for d in datas:
                if d in r.text: return True, "🟢 SITE ATUALIZADO", f"Data: {d}"
            return False, "🟡 DATA AUSENTE", "Site online, sem data de hoje."
        return False, "🔴 OFF", "Erro site."
    except: return False, "🔴 ERRO", "Falha conexão."

def raspar_ultimo_resultado_real(url, banca_key):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code != 200: return None, None, "Erro Site"
        soup = BeautifulSoup(r.text, 'html.parser')
        
        candidatos = []
        tabelas = soup.find_all('table')
        for tabela in tabelas:
            if "1º" in tabela.get_text() or "Pri" in tabela.get_text():
                horario_str = "00:00"
                prev = tabela.find_previous(string=re.compile(r'\d{2}:\d{2}'))
                if prev: 
                    m = re.search(r'(\d{2}:\d{2})', prev)
                    if m: horario_str = m.group(1)
                
                linhas = tabela.find_all('tr')
                for linha in linhas:
                    colunas = linha.find_all('td')
                    if len(colunas) >= 3:
                        premio = colunas[0].get_text().strip()
                        if any(x in premio for x in ['1º', '1', 'Pri']):
                            grp = colunas[2].get_text().strip()
                            if grp.isdigit():
                                candidatos.append((horario_str, int(grp)))
                                break
        if not candidatos: return None, None, "Não achou"
        return candidatos[0][1], candidatos[0][0], "Sucesso"
    except Exception as e: return None, None, f"Erro: {e}"

# --- ESTRATÉGIAS ---

# 1. Top 12 (Frequência)
def gerar_palpite_top12(historico):
    if not historico: return []
    c = Counter(historico[-50:])
    rank = c.most_common(12)
    return [x[0] for x in rank]

# 2. Bunker 12 (Frequência Global Fixa)
def gerar_palpite_bunker(historico):
    if not historico: return []
    c = Counter(historico)
    rank = c.most_common(12)
    return [x[0] for x in rank]

# 3. Iceberg 10 (Atrasados)
def gerar_palpite_iceberg(historico):
    if not historico: return []
    atrasos = {}
    total = len(historico)
    for b in range(1, 26):
        indices = [i for i, x in enumerate(historico) if x == b]
        if indices:
            atraso = total - 1 - indices[-1]
        else:
            atraso = total
        atrasos[b] = atraso
    
    # Ordena pelos mais atrasados (maior atraso)
    rank = sorted(atrasos.items(), key=lambda x: -x[1])
    return [x[0] for x in rank[:10]]

# --- BACKTEST (SIMULAÇÃO REAL) ---
def rodar_simulacao_real(historico, estrategia_func, n_jogos=50):
    if len(historico) < n_jogos + 10: return pd.DataFrame(), 0, 0, 0, 0
    
    resultados = []
    max_loss = 0; temp_loss = 0
    max_win = 0; temp_win = 0
    start_idx = len(historico) - n_jogos
    
    for i in range(start_idx, len(historico)):
        hist_momento = historico[:i]
        res_real = historico[i]
        palpite = estrategia_func(hist_momento)
        
        if res_real in palpite:
            status = "💚"; temp_win += 1
            if temp_loss > max_loss: max_loss = temp_loss; temp_loss = 0
        else:
            status = "❌"; temp_loss += 1
            if temp_win > max_win: max_win = temp_win; temp_win = 0
            
        if i >= len(historico) - 20:
            resultados.append({"JOGO": f"#{len(historico)-i}", "SAIU": f"{res_real:02}", "RES": status})
            
    if temp_loss > max_loss: max_loss = temp_loss
    if temp_win > max_win: max_win = temp_win
    
    curr_streak_loss = 0; curr_streak_win = 0
    df_res = pd.DataFrame(resultados[::-1])
    
    if not df_res.empty:
        for r in df_res.to_dict('records'):
            if r["RES"] == "❌": curr_streak_loss += 1
            else: break
        for r in df_res.to_dict('records'):
            if r["RES"] == "💚": curr_streak_win += 1
            else: break
            
    return df_res, max_loss, curr_streak_loss, max_win, curr_streak_win

# --- VISUAL SETORES ---
def analisar_setores_bma(historico):
    if not historico: return []
    seq_visual = []
    for x in historico[::-1][:12]:
        if x == 25: sigla, classe = "25", "bola-25"
        elif x <= 8: sigla, classe = "B", "bola-b"
        elif x <= 16: sigla, classe = "M", "bola-m"
        else: sigla, classe = "A", "bola-a"
        seq_visual.append((sigla, classe))
    return seq_visual

# --- INVERSO ---
def calcular_inverso_grupo(palpite):
    todos = set(range(1, 26))
    p_set = set(palpite)
    inv = list(todos - p_set)
    inv.sort()
    return inv

# =============================================================================
# --- 4. INTERFACE PRINCIPAL ---
# =============================================================================

if st.session_state['tocar_som_salvar']: reproduzir_som('sucesso'); st.session_state['tocar_som_salvar'] = False
if st.session_state['tocar_som_apagar']: reproduzir_som('apagar'); st.session_state['tocar_som_apagar'] = False

with st.sidebar:
    st.header("🦅 MENU DE JOGO")
    banca_selecionada = st.selectbox("Selecione a Banca:", BANCA_OPCOES)
    config_banca = CONFIG_BANCAS[banca_selecionada]
    
    # Horários
    fuso_br = pytz.timezone('America/Sao_Paulo')
    dia_semana = datetime.now(fuso_br).weekday()
    lista_horarios_str = config_banca['horarios']['dom'] if dia_semana == 6 else config_banca['horarios']['segsab']
    lista_horarios = [h.strip() for h in lista_horarios_str.split('🔹')]
    
    if st.session_state.get('auto_horario_idx', 0) >= len(lista_horarios):
        st.session_state['auto_horario_idx'] = 0
    
    st.markdown("---")
    
    col_import, _ = st.columns([1, 0.1])
    with col_import:
        if st.button("📡 Importar Resultado do Site"):
            with st.spinner("Buscando dados na central..."):
                grp, hor, msg = raspar_ultimo_resultado_real(config_banca['url_site'], banca_selecionada)
                if grp:
                    st.success(f"Encontrado! G{grp:02} às {hor}")
                    st.session_state['auto_grupo'] = grp
                    if hor in lista_horarios:
                        st.session_state['auto_horario_idx'] = lista_horarios.index(hor)
                else:
                    st.error(f"Não encontrado ({msg})")
    
    st.write("📝 **Registrar Sorteio**")
    novo_horario = st.selectbox("Horário:", lista_horarios, index=st.session_state.get('auto_horario_idx', 0))
    novo_bicho = st.number_input("Grupo:", 1, 25, st.session_state.get('auto_grupo', 1))
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 SALVAR", type="primary"):
            aba = conectar_planilha(banca_selecionada)
            if aba and salvar_na_nuvem(aba, novo_bicho, novo_horario):
                st.session_state['tocar_som_salvar'] = True
                st.toast("Salvo! 🔔", icon="✅"); time.sleep(0.5); st.rerun()
    with col_btn2:
        if st.button("🔄 REBOOT"): st.rerun()
            
    with st.expander("🗑️ Área de Perigo"):
        if st.button("APAGAR ÚLTIMO"):
            aba = conectar_planilha(banca_selecionada)
            if aba and deletar_ultimo_registro(aba):
                st.session_state['tocar_som_apagar'] = True
                st.toast("Apagado! 🗑️", icon="🗑️"); time.sleep(0.5); st.rerun()

aba_ativa = conectar_planilha(banca_selecionada)

if aba_ativa:
    historico, ultimo_horario_salvo = carregar_dados(aba_ativa)
    
    if len(historico) > 0:
        aplicar_estilo_banca(banca_selecionada)
        config_atual = CONFIG_BANCAS[banca_selecionada]

        # Cabeçalho
        col_head1, col_head2 = st.columns([1, 4])
        with col_head1: st.image(config_atual['logo_url'], width=80)
        with col_head2:
            st.markdown(f"## {config_atual['display_name']}")
            st.caption(f"Último: Grupo {historico[-1]:02} | Hora: {ultimo_horario_salvo}")

        site_on, site_tit, _ = verificar_atualizacao_site(config_atual['url_site'])
        if not site_on: st.warning(f"Status do Site: {site_tit}")

        # --- PROCESSAMENTO ESTRATÉGIAS ---
        palp_top12 = gerar_palpite_top12(historico)
        palp_bunker = gerar_palpite_bunker(historico)
        palp_ice = gerar_palpite_iceberg(historico)
        
        with st.spinner("Simulando estratégias..."):
            bt_top, ml_top, cl_top, mw_top, cw_top = rodar_simulacao_real(historico, gerar_palpite_top12)
            bt_bun, ml_bun, cl_bun, mw_bun, cw_bun = rodar_simulacao_real(historico, gerar_palpite_bunker)
            bt_ice, ml_ice, cl_ice, mw_ice, cw_ice = rodar_simulacao_real(historico, gerar_palpite_iceberg)
            
        # --- ALERTAS ---
        alertas = []
        def criar_alerta_inv(nome, curr, max_w, palp):
            st.warning(f"🛑 CUIDADO {nome}: {curr} Vitórias. Perto do Recorde ({max_w}). Inverso Recomendado!")
            inv = calcular_inverso_grupo(palp)
            with st.expander(f"👻 Ver {nome} INVERSO ({len(inv)} Grupos)"):
                st.markdown(html_bolas(inv, "cinza"), unsafe_allow_html=True)

        if cl_top >= (ml_top - 1): alertas.append(f"🔥 TOP 12: Derrotas ({cl_top}) perto do Recorde ({ml_top})!")
        if cl_bun >= (ml_bun - 1): alertas.append(f"🧬 BUNKER: Derrotas ({cl_bun}) perto do Recorde ({ml_bun})!")
        if cl_ice >= (ml_ice - 1): alertas.append(f"🥶 ICEBERG: Derrotas ({cl_ice}) perto do Recorde ({ml_ice})!")
        
        if alertas:
            for al in alertas: st.error(al)
            
        if cw_top >= (mw_top - 1) and cw_top > 0: criar_alerta_inv("TOP 12", cw_top, mw_top, palp_top12)
        if cw_bun >= (mw_bun - 1) and cw_bun > 0: criar_alerta_inv("BUNKER", cw_bun, mw_bun, palp_bunker)
        if cw_ice >= (mw_ice - 1) and cw_ice > 0: criar_alerta_inv("ICEBERG", cw_ice, mw_ice, palp_ice)

        # --- ABAS ---
        tab_set, tab_comp, tab_graf = st.tabs(["🎯 Setores (BMA)", "🆚 Comparativo (3 Mesas)", "📈 Gráficos"])
        
        with tab_set:
            st.write("Visual Recente (⬅️ Mais Novo):")
            # --- CORREÇÃO AQUI ---
            seq_visual = analisar_setores_bma(historico) # Variável correta agora
            html_seq = "<div>"
            for sigla, classe in seq_visual: 
                html_seq += f"<div class='{classe}'>{sigla}</div>"
            html_seq += "</div>"
            st.markdown(html_seq, unsafe_allow_html=True)
            st.info("Estratégia BMA (Baixo/Médio/Alto) é visual. Observe a sequência acima.")

        with tab_comp:
            c1, c2, c3 = st.columns(3)
            
            with c1:
                st.markdown("### 🔥 Top 12 (Dinâmico)")
                st.caption("Frequência Recente")
                st.table(bt_top)
                st.info(f"Derrotas Rec: {ml_top} | Vitórias Rec: {mw_top}")
                with st.expander("Ver Palpite"): st.markdown(html_bolas(palp_top12, "verde"), unsafe_allow_html=True)
                
            with c2:
                st.markdown("### 🧬 Bunker 12 (Fixo)")
                st.caption("Frequência Global")
                st.table(bt_bun)
                st.info(f"Derrotas Rec: {ml_bun} | Vitórias Rec: {mw_bun}")
                with st.expander("Ver Palpite"): st.markdown(html_bolas(palp_bunker, "azul"), unsafe_allow_html=True)
                
            with c3:
                st.markdown("### 🥶 Iceberg 10 (Atrasados)")
                st.caption("Os 10 Mais Frios")
                st.table(bt_ice)
                st.info(f"Derrotas Rec: {ml_ice} | Vitórias Rec: {mw_ice}")
                with st.expander("Ver Palpite"): st.markdown(html_bolas(palp_ice, "ice"), unsafe_allow_html=True)

        with tab_graf:
            st.write("### 📊 Frequência dos Bichos")
            c = Counter(historico[-50:])
            df_freq = pd.DataFrame.from_dict(c, orient='index', columns=['Vezes'])
            st.bar_chart(df_freq)

        st.markdown("---")
        with st.expander("🕒 Grade de Horários"):
            st.write(config_atual['horarios'])

    else:
        st.warning("⚠️ Planilha vazia. Adicione o primeiro resultado.")
else:
    st.info("Conectando...")
