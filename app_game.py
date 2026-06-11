import streamlit as st
import pandas as pd
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =============================================================================
# 🎯 ID EXATO DA PLANILHA (TIRO DE SNIPER - INFALÍVEL)
# =============================================================================
ID_PLANILHA = "1-Dhxg5G62KNcALWpbFtU_ZVLJ4sevYaZmovYJrKdQ3k"

# =============================================================================
# --- 1. CONFIGURAÇÃO DA PÁGINA E CSS ---
# =============================================================================
st.set_page_config(page_title="Secret Game", page_icon="🔥", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #07090f; color: #ffffff; }
    .vez-texto { text-align: center; font-size: 28px; font-weight: bold; color: #ff4b4b; margin-bottom: 20px; text-transform: uppercase; text-shadow: 0 0 10px #ff4b4b; }
    .desc-texto { text-align: center; font-size: 22px; font-weight: bold; color: #ffcc00; margin-bottom: 20px; padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px; border: 1px solid rgba(255,204,0,0.3); }
    
    /* 🃏 ESTILIZAÇÃO DAS CARTAS DE BARALHO 🃏 */
    .carta-btn button {
        height: 280px !important;
        border-radius: 12px !important;
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
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
    }
    .carta-btn button:hover { 
        transform: translateY(-20px) scale(1.05) rotate(-3deg) !important; 
        box-shadow: 0 20px 40px rgba(255, 75, 75, 0.8) !important; 
        border-color: #ffcc00 !important; 
        color: #ffcc00 !important;
    }
    
    /* 🚪 ESTILIZAÇÃO DOS BOTÕES DE SALA (MENU) 🚪 */
    .btn-sala button {
        height: 80px !important;
        font-size: 20px !important;
        font-weight: bold !important;
        border-radius: 10px !important;
        background: linear-gradient(135deg, #2b5876 0%, #4e4376 100%) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        box-shadow: 0 8px 15px rgba(0,0,0,0.3) !important;
        margin-bottom: 10px !important;
        transition: all 0.3s ease !important;
    }
    .btn-sala button:hover {
        transform: scale(1.02) !important;
        background: linear-gradient(135deg, #ff4b4b 0%, #cc0000 100%) !important;
        box-shadow: 0 10px 20px rgba(255,75,75,0.4) !important;
    }

    .btn-proximo button { 
        height: 60px !important; 
        background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%) !important; 
        border: none !important;
        box-shadow: 0 8px 15px rgba(0,114,255,0.3) !important; 
        font-size: 18px !important;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# --- 2. CONFIGURAÇÃO DAS SALAS E ABA DA PLANILHA ---
# =============================================================================
CONFIG_SALAS = {
    "Casal": {"jogadores": ["Homem", "Mulher"], "aba": "Sala Casal", "icon": "👫"},
    "Lésbicas": {"jogadores": ["Mulher 1", "Mulher 2"], "aba": "Sala Lesbicas", "icon": "👩‍❤️‍👩"},
    "Trisal 1": {"jogadores": ["Homem", "Mulher 1", "Mulher 2"], "aba": "Cartas Escolha", "icon": "👨‍👧‍👧"},
    "Gay": {"jogadores": ["Homem 1", "Homem 2"], "aba": "Sala Gay", "icon": "👨‍❤️‍👨"},
    "Trisal 2": {"jogadores": ["Homem", "Mulher", "TGirl"], "aba": "Sala Trisal 2", "icon": "🔥"}
}

# =============================================================================
# --- 3. CONEXÃO BLINDADA COM O GOOGLE SHEETS ---
# =============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def carregar_planilha_jogo(nome_aba):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        
        sh = client.open_by_key(ID_PLANILHA)
        ws = sh.worksheet(nome_aba)
        dados = ws.get_all_values()
        
        if len(dados) < 2: 
            st.error(f"⚠️ A aba '{nome_aba}' foi encontrada, mas parece estar vazia.")
            return pd.DataFrame()
            
        cabecalhos = [str(c).strip() for c in dados[0]]
        df = pd.DataFrame(dados[1:], columns=cabecalhos)
        return df
        
    except gspread.exceptions.APIError as e:
        st.error(f"⚠️ Erro no Google. Detalhes: {e}")
        return pd.DataFrame()
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("⚠️ Planilha não encontrada! Verifique o ID.")
        return pd.DataFrame()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"⚠️ Aba '{nome_aba}' não existe na planilha! Crie esta aba no Google Sheets.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"⚠️ Erro crítico: {type(e).__name__} - {str(e)}")
        return pd.DataFrame()

# =============================================================================
# --- 4. VARIÁVEIS DE ESTADO (MEMÓRIA DO JOGO) ---
# =============================================================================
if 'sala_selecionada' not in st.session_state:
    st.session_state.sala_selecionada = None
if 'jogadores' not in st.session_state:
    st.session_state.jogadores = []
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

def resetar_jogo(voltar_menu=False):
    st.session_state.turno_idx = 0
    st.session_state.fase = "escolha"
    st.session_state.cartas_mesa = []
    st.session_state.cartas_jogadas = []
    if voltar_menu:
        st.session_state.sala_selecionada = None
        st.session_state.jogadores = []
    st.cache_data.clear()

with st.sidebar:
    st.header("⚙️ Controle do Jogo")
    nivel_selecionado = st.selectbox("Selecione o Nível Atual:", ["Nível 1", "Nível 2", "Nível 3", "Nível 4"], index=0)
    
    if st.session_state.sala_selecionada:
        st.success(f"Sala Atual: {st.session_state.sala_selecionada}")
        if st.button("🚪 Sair da Sala (Mudar de Jogo)"):
            resetar_jogo(voltar_menu=True)
            st.rerun()
            
    if st.button("🔄 Reiniciar Jogo Atual"):
        resetar_jogo(voltar_menu=False)
        st.rerun()

# =============================================================================
# --- 5. RENDERIZAÇÃO ---
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
# --- 6. TELAS DO APLICATIVO (LOBBY OU JOGO) ---
# =============================================================================

# TELA 1: LOBBY (ESCOLHA DA SALA)
if st.session_state.sala_selecionada is None:
    st.markdown("<h1 class='vez-texto' style='font-size: 40px;'>🔥 THE SECRET GAME 🔥</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #ccc; margin-bottom: 30px;'>Selecione o seu Modo de Jogo:</h3>", unsafe_allow_html=True)
    
    for nome_sala, conf in CONFIG_SALAS.items():
        st.markdown("<div class='btn-sala'>", unsafe_allow_html=True)
        texto_botao = f"{conf['icon']} {nome_sala}  ({', '.join(conf['jogadores'])})"
        if st.button(texto_botao, use_container_width=True, key=f"btn_{nome_sala}"):
            st.session_state.sala_selecionada = nome_sala
            st.session_state.jogadores = conf["jogadores"]
            st.session_state.aba_planilha = conf["aba"]
            resetar_jogo()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# TELA 2: TABULEIRO (O JOGO EM SI)
else:
    # Carrega a planilha ESPECÍFICA da sala escolhida
    df_cartas = carregar_planilha_jogo(st.session_state.aba_planilha)
    
    if df_cartas.empty:
        st.stop() # Interrompe se a aba não existir ou estiver vazia

    jogador_atual = st.session_state.jogadores[st.session_state.turno_idx % len(st.session_state.jogadores)]

    if st.session_state.fase == "escolha":
        st.markdown(f"<div class='vez-texto'>Vez de: {jogador_atual}</div>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #ccc;'>Escolha uma das 3 Cartas Surpresas!</h3>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not st.session_state.cartas_mesa:
            if 'Nível' not in df_cartas.columns:
                st.error("❌ Coluna 'Nível' não encontrada nesta aba da planilha. Verifique o cabeçalho.")
                st.stop()
                
            df_nivel = df_cartas[df_cartas['Nível'].astype(str).str.strip().str.lower() == nivel_selecionado.lower()]
            df_nivel = df_nivel[df_nivel['Descrição'].astype(str).str.strip() != ""]
            cartas_validas = df_nivel[~df_nivel.index.isin(st.session_state.cartas_jogadas)]
            
            if len(cartas_validas) >= 3:
                amostra = cartas_validas.sample(3)
            elif len(cartas_validas) > 0:
                amostra = cartas_validas.sample(len(cartas_validas))
            else:
                st.warning(f"❌ Acabaram as cartas novas para o {nivel_selecionado} nesta sala! Suba o nível no menu lateral ou reinicie o jogo.")
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
                    st.markdown("<div class='carta-btn'>", unsafe_allow_html=True)
                    if st.button(f"❓\nCARTA {i+1}", key=f"btn_carta_{i}", use_container_width=True):
                        st.session_state.carta_selecionada = carta
                        st.session_state.fase = "revelada"
                        st.session_state.cartas_jogadas.append(carta['_index'])
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

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
