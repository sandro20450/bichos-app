import streamlit as st
import pandas as pd
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =============================================================================
# 🎯 ATENÇÃO COMANDANTE: COLE O LINK DA SUA PLANILHA AQUI DENTRO DAS ASPAS!
# =============================================================================
URL_PLANILHA = "COLE_AQUI_O_LINK_DA_SUA_PLANILHA"

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
# --- 2. CONEXÃO BLINDADA COM O GOOGLE SHEETS ---
# =============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def carregar_planilha_jogo():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        
        # Conecta direto pela URL absoluta (Tiro de Sniper)
        sh = client.open_by_url(URL_PLANILHA)
        ws = sh.worksheet("Cartas Escolha")
        dados = ws.get_all_values()
        
        if len(dados) < 2: 
            st.error("⚠️ A planilha foi encontrada, mas parece estar vazia (só tem cabeçalho).")
            return pd.DataFrame()
            
        # Pega a linha 1 como cabeçalho e remove espaços
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
    st.stop() # Interrompe a tela se houver erro (a msg de erro já foi mostrada acima)

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
                if st.button(f"🃏 CARTA {i+1}", key=f"btn_carta_{i}", use_container_width=True):
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
