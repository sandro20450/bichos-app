import streamlit as st
import pandas as pd
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# =============================================================================
# --- 1. CONFIGURAÇÃO DA PÁGINA E CSS ---
# =============================================================================
st.set_page_config(page_title="Secret Game", page_icon="🔥", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #07090f; color: #ffffff; }
    .vez-texto { text-align: center; font-size: 28px; font-weight: bold; color: #ff4b4b; margin-bottom: 20px; text-transform: uppercase; text-shadow: 0 0 10px #ff4b4b; }
    .desc-texto { text-align: center; font-size: 22px; font-weight: bold; color: #ffcc00; margin-bottom: 20px; padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px; border: 1px solid rgba(255,204,0,0.3); }
    div[data-testid="stButton"] button {
        height: 150px; font-size: 24px !important; font-weight: bold; border-radius: 15px;
        background: linear-gradient(135deg, #ff4b4b 0%, #cc0000 100%); color: white; border: none;
        box-shadow: 0 8px 15px rgba(255,0,0,0.3); transition: all 0.3s ease;
    }
    div[data-testid="stButton"] button:hover { transform: scale(1.05); box-shadow: 0 12px 20px rgba(255,0,0,0.5); border: 1px solid #ffcc00; }
    .btn-proximo button { height: 60px !important; background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%) !important; box-shadow: 0 8px 15px rgba(0,114,255,0.3) !important; font-size: 18px !important;}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO COM O GOOGLE SHEETS (MOTOR DO PENTÁGONO) ---
# =============================================================================
def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Usando a exata mecânica do app_pentagono.py
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds).open("Game Sex")
    except Exception as e: 
        return None

@st.cache_data(ttl=60, show_spinner=False)
def carregar_planilha_jogo():
    sh = conectar_sheets()
    if not sh: 
        return pd.DataFrame()
    try:
        ws = sh.worksheet("Cartas Escolha")
        # Puxa os dados em formato de matriz bruta para não quebrar com colunas vazias
        dados = ws.get_all_values()
        
        if len(dados) < 2: 
            return pd.DataFrame()
            
        # Pega a linha 1 como cabeçalho e remove espaços inúteis do texto
        cabecalhos = [str(c).strip() for c in dados[0]]
        
        # Cria a tabela de dados
        df = pd.DataFrame(dados[1:], columns=cabecalhos)
        return df
    except Exception as e:
        return pd.DataFrame()

df_cartas = carregar_planilha_jogo()

# =============================================================================
# --- 3. VARIÁVEIS DE ESTADO (MEMÓRIA DO JOGO) ---
# =============================================================================
if 'jogadores' not in st.session_state:
    st.session_state.jogadores = ["Homem", "Mulher 1", "Mulher 2"]
if 'turno_idx' not in st.session_state:
    st.session_state.turno_idx = 0
if 'fase' not in st.session_state:
    st.session_state.fase = "escolha"  
if 'cartas_mesa' not in st.session_state:
    st.session_state.cartas_mesa = []
if 'carta_selecionada' not in st.session_state:
    st.session_state.carta_selecionada = None
if 'cartas_jogadas' not in st.session_state:
    st.session_state.cartas_jogadas = [] 

with st.sidebar:
    st.header("⚙️ Controle do Jogo")
    nivel_selecionado = st.selectbox("Selecione o Nível Atual:", ["Nível 1", "Nível 2", "Nível 3", "Nível 4"], index=0)
    
    if st.button("🔄 Reiniciar Jogo Totalmente"):
        st.session_state.turno_idx = 0
        st.session_state.fase = "escolha"
        st.session_state.cartas_mesa = []
        st.session_state.cartas_jogadas = []
        st.cache_data.clear()
        st.rerun()

# =============================================================================
# --- 4. MECÂNICA DE RENDERIZAÇÃO DE MÍDIA ---
# =============================================================================
def renderizar_midia(link):
    link = str(link).strip()
    if not link:
        return
        
    # Tratamento para links do Dropbox (forçar raw para exibir direto na tela)
    if "dropbox.com" in link: 
        link = link.replace("dl=0", "raw=1")
    
    # Identifica se é vídeo ou imagem
    if link.lower().endswith(('.mp4', '.mov', '.webm')):
        st.video(link)
    else:
        st.image(link, use_container_width=True)

# =============================================================================
# --- 5. LÓGICA DO TABULEIRO ---
# =============================================================================
if df_cartas.empty:
    st.error("⚠️ Erro Crítico: Planilha vazia ou sem acesso. Verifique as credenciais no menu Secrets.")
    st.stop()

jogador_atual = st.session_state.jogadores[st.session_state.turno_idx % len(st.session_state.jogadores)]

# --- FASE 1: ESCOLHA DAS CARTAS ---
if st.session_state.fase == "escolha":
    st.markdown(f"<div class='vez-texto'>Vez de: {jogador_atual}</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #ccc;'>Escolha uma das 3 Cartas Surpresas!</h3>", unsafe_allow_html=True)
    
    if not st.session_state.cartas_mesa:
        # Verifica se existe a coluna 'Nível'
        if 'Nível' not in df_cartas.columns:
            st.error("❌ Coluna 'Nível' não encontrada na planilha. Verifique o cabeçalho.")
            st.stop()
            
        # Filtra cartas do nível atual que não estão vazias
        df_nivel = df_cartas[df_cartas['Nível'].astype(str).str.strip().str.lower() == nivel_selecionado.lower()]
        df_nivel = df_nivel[df_nivel['Descrição'].astype(str).str.strip() != ""]
        
        # Filtra cartas já jogadas
        cartas_validas = df_nivel[~df_nivel.index.isin(st.session_state.cartas_jogadas)]
        
        if len(cartas_validas) >= 3:
            amostra = cartas_validas.sample(3)
        elif len(cartas_validas) > 0:
            amostra = cartas_validas.sample(len(cartas_validas))
        else:
            st.warning(f"❌ Acabaram as cartas novas para o {nivel_selecionado}! Suba o nível no menu lateral.")
            st.stop()
            
        # Salva as cartas da mesa mantendo o index da planilha original
        st.session_state.cartas_mesa = []
        for index, row in amostra.iterrows():
            carta_dict = row.to_dict()
            carta_dict['_index'] = index
            st.session_state.cartas_mesa.append(carta_dict)

    if st.session_state.cartas_mesa:
        colunas = st.columns(len(st.session_state.cartas_mesa))
        for i, carta in enumerate(st.session_state.cartas_mesa):
            with colunas[i]:
                if st.button(f"🃏 CARTA {i+1}", key=f"btn_carta_{i}", use_container_width=True):
                    st.session_state.carta_selecionada = carta
                    st.session_state.fase = "revelada"
                    # Adiciona a carta na lista de jogadas para não repetir
                    st.session_state.cartas_jogadas.append(carta['_index'])
                    st.rerun()

# --- FASE 2: CARTA REVELADA ---
elif st.session_state.fase == "revelada":
    st.markdown(f"<div class='vez-texto'>Ação de: {jogador_atual}</div>", unsafe_allow_html=True)
    
    carta = st.session_state.carta_selecionada
    if carta:
        desc = carta.get('Descrição', 'Ação Surpresa!')
        st.markdown(f"<div class='desc-texto'>{desc}</div>", unsafe_allow_html=True)
        
        link_midia = carta.get('imagem QR', '')
        renderizar_midia(link_midia)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='btn-proximo'>", unsafe_allow_html=True)
        if st.button("Passar a Vez (Próximo Jogador) ⏭️", use_container_width=True):
            st.session_state.turno_idx += 1
            st.session_state.fase = "escolha"
            st.session_state.cartas_mesa = [] 
            st.session_state.carta_selecionada = None
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
