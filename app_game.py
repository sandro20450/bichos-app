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
    .stApp { background-color: #121212; color: #ffffff; }
    .vez-texto { text-align: center; font-size: 28px; font-weight: bold; color: #ff4b4b; margin-bottom: 20px; text-transform: uppercase; }
    .desc-texto { text-align: center; font-size: 22px; font-weight: bold; color: #ffcc00; margin-bottom: 20px; padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px; }
    div[data-testid="stButton"] button {
        height: 150px; font-size: 24px !important; font-weight: bold; border-radius: 15px;
        background: linear-gradient(135deg, #ff4b4b 0%, #cc0000 100%); color: white; border: none;
        box-shadow: 0 8px 15px rgba(255,0,0,0.3); transition: all 0.3s ease;
    }
    div[data-testid="stButton"] button:hover { transform: scale(1.05); box-shadow: 0 12px 20px rgba(255,0,0,0.5); }
    .btn-proximo button { height: 60px !important; background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%) !important; box-shadow: 0 8px 15px rgba(0,114,255,0.3) !important; font-size: 18px !important;}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO COM O GOOGLE SHEETS ---
# =============================================================================
@st.cache_resource(ttl=60)
def carregar_planilha_jogo():
    try:
        # Usa o mesmo segredo do Pentágono
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" in st.secrets:
            if isinstance(st.secrets["gcp_service_account"], str): creds_dict = json.loads(st.secrets["gcp_service_account"])
            else: creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            # Nome EXATO da planilha e da aba
            ws = client.open("Game Sex").worksheet("Cartas Escolha")
            dados = ws.get_all_records()
            return pd.DataFrame(dados)
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        return pd.DataFrame()

df_cartas = carregar_planilha_jogo()

# =============================================================================
# --- 3. VARIÁVEIS DE ESTADO (MEMÓRIA DO JOGO) ---
# =============================================================================
# Lista de jogadores
if 'jogadores' not in st.session_state:
    st.session_state.jogadores = ["Homem", "Mulher 1", "Mulher 2"]
if 'turno_idx' not in st.session_state:
    st.session_state.turno_idx = 0
if 'fase' not in st.session_state:
    st.session_state.fase = "escolha"  # "escolha" ou "revelada"
if 'cartas_mesa' not in st.session_state:
    st.session_state.cartas_mesa = []
if 'carta_selecionada' not in st.session_state:
    st.session_state.carta_selecionada = None
if 'cartas_jogadas' not in st.session_state:
    st.session_state.cartas_jogadas = [] # Guarda os índices para não repetir

# Nível atual controlado na barra lateral
with st.sidebar:
    st.header("⚙️ Controle do Jogo")
    nivel_selecionado = st.selectbox("Selecione o Nível Atual:", ["Nível 1", "Nível 2", "Nível 3", "Nível 4"], index=0)
    
    if st.button("🔄 Reiniciar Jogo Totalmente"):
        st.session_state.turno_idx = 0
        st.session_state.fase = "escolha"
        st.session_state.cartas_mesa = []
        st.session_state.cartas_jogadas = []
        st.cache_resource.clear()
        st.rerun()

# =============================================================================
# --- 4. MECÂNICA DE RENDERIZAÇÃO DE MÍDIA ---
# =============================================================================
def renderizar_midia(link):
    link = str(link).strip()
    # Tratamento para links do Dropbox (forçar raw)
    if "dropbox.com" in link: link = link.replace("dl=0", "raw=1")
    
    # Renderização
    if link.lower().endswith(('.mp4', '.mov', '.webm')):
        st.video(link)
    else:
        # Se for imagem ou link genérico
        st.image(link, use_container_width=True)

# =============================================================================
# --- 5. LÓGICA DO TABULEIRO ---
# =============================================================================
if df_cartas.empty:
    st.warning("⚠️ Planilha vazia ou não encontrada. Verifique as credenciais e o nome da aba.")
    st.stop()

jogador_atual = st.session_state.jogadores[st.session_state.turno_idx % len(st.session_state.jogadores)]

# --- FASE 1: ESCOLHA DAS CARTAS ---
if st.session_state.fase == "escolha":
    st.markdown(f"<div class='vez-texto'>Vez de: {jogador_atual}</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #ccc;'>Escolha uma das 3 Cartas Surpresas!</h3>", unsafe_allow_html=True)
    
    # Sorteia 3 cartas que sejam do nível atual e ainda não foram jogadas
    if not st.session_state.cartas_mesa:
        cartas_validas = df_cartas[
            (df_cartas['Nível'].astype(str).str.strip().str.lower() == nivel_selecionado.lower()) & 
            (~df_cartas.index.isin(st.session_state.cartas_jogadas))
        ]
        
        if len(cartas_validas) >= 3:
            st.session_state.cartas_mesa = cartas_validas.sample(3).to_dict('records')
        elif len(cartas_validas) > 0:
            st.session_state.cartas_mesa = cartas_validas.sample(len(cartas_validas)).to_dict('records')
        else:
            st.error(f"❌ Acabaram as cartas do {nivel_selecionado}! Suba o nível no menu lateral.")
            st.stop()

    # Desenha as 3 Cartas na tela
    if st.session_state.cartas_mesa:
        colunas = st.columns(len(st.session_state.cartas_mesa))
        for i, carta in enumerate(st.session_state.cartas_mesa):
            with colunas[i]:
                if st.button(f"🃏 CARTA {i+1}", key=f"btn_carta_{i}", use_container_width=True):
                    st.session_state.carta_selecionada = carta
                    st.session_state.fase = "revelada"
                    # Opcional: Para evitar repetição absoluta, poderíamos salvar o index dela na lista 'cartas_jogadas'.
                    st.rerun()

# --- FASE 2: CARTA REVELADA ---
elif st.session_state.fase == "revelada":
    st.markdown(f"<div class='vez-texto'>Ação de: {jogador_atual}</div>", unsafe_allow_html=True)
    
    carta = st.session_state.carta_selecionada
    if carta:
        st.markdown(f"<div class='desc-texto'>{carta.get('Descrição', 'Ação Surpresa!')}</div>", unsafe_allow_html=True)
        
        # Renderiza Imagem ou Vídeo em tela cheia no container
        link_midia = carta.get('imagem QR', '')
        if link_midia: renderizar_midia(link_midia)
        else: st.info("Nenhuma mídia vinculada a esta carta.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Botão para avançar o turno
        st.markdown("<div class='btn-proximo'>", unsafe_allow_html=True)
        if st.button("Passar a Vez (Próximo Jogador) ⏭️", use_container_width=True):
            st.session_state.turno_idx += 1
            st.session_state.fase = "escolha"
            st.session_state.cartas_mesa = [] # Limpa a mesa para puxar 3 cartas novas
            st.session_state.carta_selecionada = None
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
