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
import itertools

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS ---
# =============================================================================
st.set_page_config(page_title="DUQUE DA LOTECA", page_icon="💰", layout="wide")

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

# Estados de Sessão
if 'tocar_som_salvar' not in st.session_state: st.session_state['tocar_som_salvar'] = False
if 'tocar_som_apagar' not in st.session_state: st.session_state['tocar_som_apagar'] = False
if 'auto_b1' not in st.session_state: st.session_state['auto_b1'] = 1
if 'auto_b2' not in st.session_state: st.session_state['auto_b2'] = 2
if 'auto_horario_idx' not in st.session_state: st.session_state['auto_horario_idx'] = 0

def reproduzir_som(tipo):
    if tipo == 'sucesso':
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=success-1-6297.mp3"
    else:
        sound_url = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3?filename=crumpling-paper-1-6240.mp3"
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
        .metric-card {{ background-color: {card_bg}; padding: 10px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.2); text-align: center; }}
        .bola-duque {{ display: inline-block; width: 40px; height: 40px; line-height: 40px; border-radius: 50%; background-color: #ffd700; color: black !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; box-shadow: 0 0 5px rgba(0,0,0,0.5); }}
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# --- 2. BANCO DE DADOS ---
# =============================================================================
def conectar_planilha(nome_aba):
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        try:
            sh = gc.open("CentralBichos") 
            # OBS: O App Duque geralmente usa uma aba separada ou a mesma. 
            # Vou assumir que usa abas com sufixo "_DUQUE" ou a mesma aba se você registra b1 e b2.
            # Para simplificar e manter a compatibilidade com o app anterior, vou tentar abrir a aba com o nome da banca + "_DUQUE"
            # Se não existir, tenta só o nome da banca.
            try: return sh.worksheet(f"{nome_aba}_DUQUE")
            except: return sh.worksheet(nome_aba)
        except: return None
    return None

def carregar_dados(worksheet):
    if worksheet:
        # Assume col1 = Bicho1, col2 = Bicho2, col3 = Horario
        try:
            todos = worksheet.get_all_values()
            dados = []
            for row in todos:
                if len(row) >= 2 and row[0].isdigit() and row[1].isdigit():
                    dados.append((int(row[0]), int(row[1])))
            
            ultimo_horario = ""
            if len(todos) > 0 and len(todos[-1]) >= 3:
                ultimo_horario = todos[-1][2]
                
            return dados, ultimo_horario
        except: return [], ""
    return [], ""

def salvar_na_nuvem(worksheet, b1, b2, horario):
    if worksheet:
        try:
            data_hoje = datetime.now().strftime("%Y-%m-%d")
            # Estrutura: Bicho1, Bicho2, Horario, Data
            worksheet.append_row([int(b1), int(b2), str(horario), data_hoje])
            return True
        except: return False
    return False

def deletar_ultimo_registro(worksheet):
    if worksheet:
        try:
            todos = worksheet.get_all_values()
            if len(todos) > 0:
                worksheet.delete_rows(len(todos))
                return True
        except: return False
    return False

# =============================================================================
# --- 3. ROBÔ DE IMPORTAÇÃO DUPLA (NOVO) ---
# =============================================================================
def raspar_dupla_por_horario(url, horario_alvo):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code != 200: return None, None, "Erro Site"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        tabelas = soup.find_all('table')
        
        for tabela in tabelas:
            if "1º" in tabela.get_text() or "Pri" in tabela.get_text():
                horario_encontrado = None
                prev = tabela.find_previous(string=re.compile(r'\d{2}:\d{2}'))
                if prev: 
                    m = re.search(r'(\d{2}:\d{2})', prev)
                    if m: horario_encontrado = m.group(1)
                
                # Se achou o horário alvo
                if horario_encontrado == horario_alvo:
                    bicho1 = None
                    bicho2 = None
                    
                    linhas = tabela.find_all('tr')
                    for linha in linhas:
                        colunas = linha.find_all('td')
                        if len(colunas) >= 3:
                            premio = colunas[0].get_text().strip()
                            
                            # Pega 1º Premio
                            if any(x in premio for x in ['1º', '1', 'Pri']) and "10" not in premio:
                                grp = colunas[2].get_text().strip()
                                if grp.isdigit(): bicho1 = int(grp)
                            
                            # Pega 2º Premio
                            if any(x in premio for x in ['2º', '2', 'Seg']):
                                grp = colunas[2].get_text().strip()
                                if grp.isdigit(): bicho2 = int(grp)
                                
                        if bicho1 is not None and bicho2 is not None:
                            return bicho1, bicho2, "Sucesso"
                    
                    return None, None, "Horário ok, mas sem 2 prêmios"
                    
        return None, None, "Horário não encontrado"
        
    except Exception as e: return None, None, f"Erro: {e}"

# =============================================================================
# --- 4. LÓGICA DE DUQUE ---
# =============================================================================
def gerar_top_duques(historico):
    if len(historico) < 10: return []
    # Cria pares ordenados (menor, maior) para ignorar a ordem (1-2 é igual a 2-1)
    pares = [tuple(sorted(par)) for par in historico]
    contagem = Counter(pares)
    # Retorna os 10 mais frequentes
    return contagem.most_common(10)

def sugerir_duque_atrasado(historico):
    # Gera todos os pares possíveis (1,2) a (24,25)
    todos_pares = list(itertools.combinations(range(1, 26), 2))
    # Vê quando foi a última vez que saiu
    atrasos = {}
    total_jogos = len(historico)
    
    historico_set = [tuple(sorted(h)) for h in historico]
    
    for par in todos_pares:
        if par in historico_set:
            # Acha o índice da última ocorrência
            indices = [i for i, x in enumerate(historico_set) if x == par]
            ultimo_idx = indices[-1]
            atraso = total_jogos - 1 - ultimo_idx
        else:
            atraso = total_jogos # Nunca saiu (no recorte)
        atrasos[par] = atraso
    
    # Ordena pelos mais atrasados
    rank = sorted(atrasos.items(), key=lambda x: -x[1])
    return rank[:10]

# =============================================================================
# --- 5. INTERFACE PRINCIPAL ---
# =============================================================================

if st.session_state['tocar_som_salvar']: reproduzir_som('sucesso'); st.session_state['tocar_som_salvar'] = False
if st.session_state['tocar_som_apagar']: reproduzir_som('apagar'); st.session_state['tocar_som_apagar'] = False

with st.sidebar:
    st.header("🎲 MENU DUQUE")
    banca_selecionada = st.selectbox("Selecione a Banca:", BANCA_OPCOES)
    config_banca = CONFIG_BANCAS[banca_selecionada]
    
    fuso_br = pytz.timezone('America/Sao_Paulo')
    dia_semana = datetime.now(fuso_br).weekday()
    lista_horarios_str = config_banca['horarios']['dom'] if dia_semana == 6 else config_banca['horarios']['segsab']
    lista_horarios = [h.strip() for h in lista_horarios_str.split('🔹')]
    
    if st.session_state.get('auto_horario_idx', 0) >= len(lista_horarios): st.session_state['auto_horario_idx'] = 0
    
    st.markdown("---")
    
    c_link, _ = st.columns([1, 0.1])
    with c_link:
        st.link_button("🔗 Ver Site Oficial", config_banca['url_site'])
    
    st.write("📝 **Registrar Dupla**")
    novo_horario = st.selectbox("Horário:", lista_horarios, index=st.session_state.get('auto_horario_idx', 0))
    
    # --- NOVO BOTÃO DE BUSCA INTELIGENTE DUPLA ---
    if st.button(f"🔍 Checar {novo_horario}"):
        with st.spinner("Buscando 1º e 2º prêmios..."):
            b1, b2, msg = raspar_dupla_por_horario(config_banca['url_site'], novo_horario)
            if b1 and b2:
                st.session_state['auto_b1'] = b1
                st.session_state['auto_b2'] = b2
                st.success(f"Achado: {b1:02} e {b2:02}")
            else:
                st.error(f"Não achado: {msg}")
    
    col_in1, col_in2 = st.columns(2)
    with col_in1: novo_b1 = st.number_input("Bicho 1:", 1, 25, st.session_state.get('auto_b1', 1))
    with col_in2: novo_b2 = st.number_input("Bicho 2:", 1, 25, st.session_state.get('auto_b2', 2))
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 SALVAR", type="primary"):
            aba = conectar_planilha(banca_selecionada)
            if aba and salvar_na_nuvem(aba, novo_b1, novo_b2, novo_horario):
                st.session_state['tocar_som_salvar'] = True
                st.toast("Duque Salvo! 💰", icon="✅"); time.sleep(0.5); st.rerun()
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
        
        # --- PROCESSAMENTO DUQUE ---
        top_duques = gerar_top_duques(historico)
        atrasados = sugerir_duque_atrasado(historico)
        
        # Cabeçalho
        col_head1, col_head2 = st.columns([1, 4])
        with col_head1: st.image(config_banca['logo_url'], width=80)
        with col_head2:
            st.markdown(f"## {config_banca['display_name']} (Modo Duque)")
            ult_res = historico[-1]
            st.caption(f"Último: {ult_res[0]:02} - {ult_res[1]:02} | Hora: {ultimo_horario_salvo}")

        # --- ABAS ---
        tab_top, tab_atr, tab_mat = st.tabs(["🔥 Top Duques", "🐢 Mais Atrasados", "🧩 Matriz"])
        
        with tab_top:
            st.subheader("🏆 Duques que mais saem")
            if top_duques:
                for i, (par, freq) in enumerate(top_duques):
                    st.markdown(f"**{i+1}º Lugar:** Dupla `{par[0]:02} - {par[1]:02}` (Saiu {freq} vezes)")
            else: st.info("Poucos dados.")
            
        with tab_atr:
            st.subheader("⏳ Duques 'Sumidos'")
            st.caption("Baseado nos duques que já saíram alguma vez, mas estão demorando a voltar.")
            # Filtra apenas os que já saíram (atraso < total_jogos) para não mostrar combinações virgens
            atrasados_reais = [x for x in atrasados if x[1] < len(historico)]
            if atrasados_reais:
                for i, (par, atr) in enumerate(atrasados_reais[:10]):
                    st.markdown(f"**{i+1}º:** `{par[0]:02} - {par[1]:02}` (Atraso: {atr} jogos)")
            else: st.info("Dados insuficientes.")
            
        with tab_mat:
            st.subheader("🧩 Matriz de Ocorrências")
            st.write("Cruzamento dos bichos que saíram juntos recentemente.")
            # Simples visualização dos últimos 10 pares
            for i, par in enumerate(historico[-10:][::-1]):
                st.markdown(f"Jogo {len(historico)-i}: <span class='bola-duque'>{par[0]:02}</span> + <span class='bola-duque'>{par[1]:02}</span>", unsafe_allow_html=True)

    else:
        st.warning("⚠️ Planilha vazia ou sem aba _DUQUE. Adicione o primeiro resultado.")
else:
    st.info("Conectando...")
