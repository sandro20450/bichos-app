import streamlit as st
import pandas as pd
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =============================================================================
# 🎯 ATENÇÃO COMANDANTE: COLE O LINK DA SUA PLANILHA AQUI DENTRO DAS ASPAS!
# =============================================================================
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1-Dhxg5G62KNcALWpbFtU_ZVLJ4sevYaZmovYJrKdQ3k/edit?gid=491860253#gid=491860253"

# =============================================================================
# --- 1. CONFIGURAÇÃO DA PÁGINA E CSS (DESIGN DE BARALHO) ---
# =============================================================================
st.set_page_config(page_title="Secret Game", page_icon="🔥", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #07090f; color: #ffffff; }
    .vez-texto { text-align: center; font-size: 28px; font-weight: bold; color: #ff4b4b; margin-bottom: 20px; text-transform: uppercase; text-shadow: 0 0 10px #ff4b4b; }
    .desc-texto { text-align: center; font-size: 22px; font-weight: bold; color: #ffcc00; margin-bottom: 20px; padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px; border: 1px solid rgba(255,204,0,0.3); }
    
    /* 🃏 ESTILIZAÇÃO DAS CARTAS DE BARALHO 🃏 */
    div[data-testid="stButton"] button {
        height: 280px !important;
        border-radius: 12px !important;
        /* Padrão clássico de verso de baralho com borda branca */
        background-color: #b30000 !important;
        background-image: repeating-linear-gradient(45deg, rgba(0,0,0,0.2) 25%, transparent 25%, transparent 75%, rgba(0,0,0,0.2) 75%, rgba(0,0,0,0.2)), repeating-linear-gradient(45deg, rgba(0,0,0,0.2) 25%, transparent 25%, transparent 75%, rgba(0,0,0,0.2) 75%, rgba(0,0,0,0.2)) !important;
        background-position: 0 0, 10px 10px !important;
        background-size: 20px 20px !important;
        border: 8px solid #ffffff !important;
        color: #ffffff !important;
        font-size: 28px !important;
        font-weight: 900 !important;
        text-shadow: 2px 2px 5px rgba(0,0,0,0.9) !important;
        box-shadow: 0 10px 20px rgba(0,0,0,0.6), inset 0 0 15px rgba(0,0,0,0.5) !important;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important; /* Efeito de mola */
    }
    
    /* 🃏 FÍSICA DE INTERAÇÃO (Levantar e Girar) 🃏 */
    div[data-testid="stButton"] button:hover { 
        transform: translateY(-20px) scale(1.05) rotate(-3deg) !important; 
        box-shadow: 0 20px 40px rgba(255, 75, 75, 0.8) !important; 
        border-color: #ffcc00 !important; 
        color: #ffcc00 !important;
    }
    
    /* Proteção para o botão de "Próxima Vez" não herdar o estilo de carta */
    .btn-proximo button { 
        height: 60px !important; 
        background-image: none !important;
        background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%) !important; 
        border: none !important;
        box-shadow: 0 8px 15px rgba(0,114,255,0.3) !important; 
        font-size: 18px !important;
        text-shadow: none !important;
    }
    .btn-proximo button:hover {
        transform: scale(1.02) !important;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONEXÃO BLINDADA COM O GOOGLE SHEETS ---
# =============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def carregar_planilha_jogo():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        
        sh = client.open_by_url(URL_PLANILHA)
        ws = sh.worksheet("Cartas Escolha")
        dados = ws.get_all_values()
        
        if len(dados) < 2: 
            st.error("⚠️ A planilha foi encontrada, mas parece estar vazia (só tem cabeçalho).")
            return pd.DataFrame()
            
        cabecalhos = [str(c).strip() for c in dados[0]]
        df = pd.DataFrame(dados[1:], columns=cabecalhos)
        return df
        
    except gspread.exceptions.APIError as e:
        st.error(f"⚠️ Erro no Google. A planilha foi compartilhada como Editor com o e-mail do Service Account? Detalhes: {e}")
        return pd.DataFrame()
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("⚠️ Planilha não encontrada! Verifique se o Link está correto e se você compartilhou com o robô.")
        return pd.DataFrame()
    except gspread.exceptions.WorksheetNotFound:
        st.error("⚠️ Aba 'Cartas Escolha' não encontrada. Verifique o nome na parte de baixo da planilha.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"⚠️ Erro crítico: {type(e).__name__} - {str(e)}")
        return pd.DataFrame()

df_cartas = carregar_planilha_jogo()

if df_cartas.empty:
    st.stop()

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
    if not link: return
        
    if "dropbox.com" in link: 
        link = link.replace("dl=0", "raw=1")
    
    if link.lower().endswith(('.mp4', '.mov', '.webm')):
        st.video(link)
    else:
        st.image(link, use_container_width=True)

# =============================================================================
# --- 5. LÓGICA DO TABULEIRO ---
# =============================================================================
jogador_atual = st.session_state.jogadores[st.session_state.turno_idx % len(st.session_state.jogadores)]

if st.session_state.fase == "escolha":
    st.markdown(f"<div class='vez-texto'>Vez de: {jogador_atual}</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #ccc;'>Escolha uma das 3 Cartas Surpresas!</h3>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    if not st.session_state.cartas_mesa:
        if 'Nível' not in df_cartas.columns:
            st.error("❌ Coluna 'Nível' não encontrada na planilha. Verifique o cabeçalho.")
            st.stop()
            
        df_nivel = df_cartas[df_cartas['Nível'].astype(str).str.strip().str.lower() == nivel_selecionado.lower()]
        df_nivel = df_nivel[df_nivel['Descrição'].astype(str).str.strip() != ""]
        cartas_validas = df_nivel[~df_nivel.index.isin(st.session_state.cartas_jogadas)]
        
        if len(cartas_validas) >= 3:
            amostra = cartas_validas.sample(3)
        elif len(cartas_validas) > 0:
            amostra = cartas_validas.sample(len(cartas_validas))
        else:
            st.warning(f"❌ Acabaram as cartas novas para o {nivel_selecionado}! Suba o nível no menu lateral.")
            st.stop()
            
        st.session_state.cartas_mesa = []
        for index, row in amostra.iterrows():
            carta_dict = row.to_dict()
            carta_dict['_index'] = index
            st.session_state.cartas_mesa.append(carta_dict)

    if st.session_state.cartas_mesa:
        colunas = st.columns(len(st.session_state.cartas_mesa))
        for i, carta in enumerate(st.session_state.cartas_mesa):
            with colunas[i]:
                # Mudei o texto do botão para ter um ícone de interrogação no centro
                if st.button(f"❓\nCARTA {i+1}", key=f"btn_carta_{i}", use_container_width=True):
                    st.session_state.carta_selecionada = carta
                    st.session_state.fase = "revelada"
                    st.session_state.cartas_jogadas.append(carta['_index'])
                    st.rerun()

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
