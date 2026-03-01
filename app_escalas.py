import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import time

# =============================================================================
# --- CONFIGURAÇÕES DA PÁGINA E ESTILOS ---
# =============================================================================
st.set_page_config(page_title="ESCALAS DAS - Comando", page_icon="👮‍♂️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card-policial { background-color: #1e2530; padding: 15px; border-radius: 10px; border-left: 5px solid #28a745; margin-bottom: 10px; }
    .graduacao { color: #ffd700; font-weight: bold; font-size: 1.1em; }
    .btn-ligar { background-color: #28a745; color: white; padding: 5px 10px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 0.9em; float: right;}
    .btn-ligar:hover { background-color: #218838; color: white; }
</style>
""", unsafe_allow_html=True)

# Tipos de Serviços Padrões do Quartel
TIPOS_SERVICO = [
    "Recepção DAS (24h)", 
    "Sobreaviso Oficiais/ST", 
    "Motorista SSTRAN (24h)", 
    "Operação Visibilidade (8h)", 
    "Vila Militar (8h)", 
    "Rendição Almoço (1h)",
    "Guarda do Quartel (24h)"
]

# =============================================================================
# --- CONEXÃO COM GOOGLE SHEETS ---
# =============================================================================
@st.cache_resource(ttl=600)
def conectar_planilha():
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        gc = gspread.authorize(creds)
        try:
            # Usando a CHAVE EXATA da planilha para evitar o erro do Google Drive
            chave_planilha = "1VyaWftpKA8V4m4SH2IX9xqkbgv4-uPIxZ27tq1FsFns"
            return gc.open_by_key(chave_planilha)
        except Exception as e:
            st.error(f"Erro ao abrir planilha pela chave: {e}")
            return None
    return None

def carregar_dados(aba):
    sh = conectar_planilha()
    if sh:
        try:
            worksheet = sh.worksheet(aba)
            return worksheet.get_all_records()
        except:
            return []
    return []
# =============================================================================
# --- SISTEMA DE LOGIN (SESSÃO) ---
# =============================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_data = {}

def efetuar_login(matricula, senha):
    efetivo = carregar_dados("Efetivo")
    for pol in efetivo:
        if str(pol["Matricula"]) == str(matricula) and str(pol["Senha"]) == str(senha):
            if pol.get("Status", "Ativo").strip().upper() != "ATIVO":
                st.error("⚠️ Acesso Negado. Status do Policial: Inativo/Indisponível.")
                return False
            st.session_state.logged_in = True
            st.session_state.user_data = pol
            return True
    st.error("❌ Matrícula ou Senha incorretos.")
    return False

def logout():
    st.session_state.logged_in = False
    st.session_state.user_data = {}
    st.rerun()

# =============================================================================
# --- TELA DE LOGIN ---
# =============================================================================
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #ffd700;'>🦅 SISTEMA ESCALAS DAS</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Acesso Restrito ao Efetivo</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            mat_input = st.text_input("Matrícula:")
            senha_input = st.text_input("Senha:", type="password")
            if st.button("🚔 ENTRAR NO SISTEMA", use_container_width=True):
                if mat_input and senha_input:
                    with st.spinner("Autenticando..."):
                        if efetuar_login(mat_input, senha_input):
                            st.success("Acesso Permitido!")
                            time.sleep(1)
                            st.rerun()

# =============================================================================
# --- APLICATIVO PRINCIPAL (PÓS-LOGIN) ---
# =============================================================================
else:
    user = st.session_state.user_data
    is_admin = user.get("Nivel", "Comum").strip().upper() in ["ADMIN", "P1", "COMANDO"]
    
    # BARRA LATERAL (MENU)
    st.sidebar.markdown(f"### 👮‍♂️ {user.get('Graduacao', '')} {user.get('Nome', '')}")
    st.sidebar.caption(f"Matrícula: {user.get('Matricula', '')}")
    st.sidebar.markdown("---")
    
    menu_opcoes = ["🏠 Quadro de Hoje", "📅 Minhas Escalas"]
    if is_admin:
        menu_opcoes.append("⚙️ Lançar Escalas (P1)")
        menu_opcoes.append("📋 Relação do Efetivo")
        
    escolha = st.sidebar.radio("Navegação", menu_opcoes)
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Sair do Sistema"):
        logout()

    # --- CARREGAMENTO DE DADOS BASE ---
    efetivo_db = carregar_dados("Efetivo")
    escalas_db = carregar_dados("Escalas_Lancadas")
    
    # Dicionário rápido para buscar dados do policial pela matrícula
    dict_efetivo = {str(p["Matricula"]): p for p in efetivo_db}

    # -------------------------------------------------------------------------
    # TELA 1: QUADRO DE HOJE (Visão do Oficial de Dia)
    # -------------------------------------------------------------------------
    if escolha == "🏠 Quadro de Hoje":
        st.title("🦅 QUADRO DE SERVIÇO DIÁRIO")
        
        # Filtro de data (Padrão: Hoje, mas permite olhar amanhã)
        data_filtro = st.date_input("Filtrar por Data:", date.today())
        data_str = data_filtro.strftime("%d/%m/%Y")
        
        st.subheader(f"Efetivo Empregado em: {data_str}")
        
        # Filtrar escalas do dia
        escalas_hoje = [e for e in escalas_db if str(e.get("Data", "")) == data_str]
        
        if not escalas_hoje:
            st.info("Nenhuma escala lançada para esta data.")
        else:
            # Agrupar por serviço
            servicos_do_dia = {}
            for e in escalas_hoje:
                srv = e["Servico"]
                if srv not in servicos_do_dia:
                    servicos_do_dia[srv] = []
                servicos_do_dia[srv].append(e)
            
            # Exibir cards separados por serviço
            for srv, policiais in servicos_do_dia.items():
                st.markdown(f"### 🎯 {srv}")
                for pol_escala in policiais:
                    mat = str(pol_escala.get("Matricula", ""))
                    dados_pol = dict_efetivo.get(mat, {})
                    
                    nome = dados_pol.get("Nome", "Policial Não Encontrado")
                    grad = dados_pol.get("Graduacao", "")
                    telefone = str(dados_pol.get("Telefone", ""))
                    horario = pol_escala.get("Horario", "N/I")
                    
                    # HTML Customizado para o Card e o botão de ligação
                    card_html = f"""
                    <div class='card-policial'>
                        <span class='graduacao'>{grad} {nome}</span> (Mat: {mat})
                        <br>⏰ <b>Horário:</b> {horario}
                        <a href='tel:{telefone}' class='btn-ligar'>📞 Ligar Rápido</a>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                st.markdown("---")

    # -------------------------------------------------------------------------
    # TELA 2: MINHAS ESCALAS (Visão do Policial)
    # -------------------------------------------------------------------------
    elif escolha == "📅 Minhas Escalas":
        st.title("📅 MINHAS MISSÕES")
        st.write("Acompanhe os seus serviços lançados no sistema.")
        
        minha_mat = str(user.get("Matricula"))
        # Filtra e ordena (simplificado para exibição)
        minhas_escalas = [e for e in escalas_db if str(e.get("Matricula", "")) == minha_mat]
        
        if not minhas_escalas:
            st.success("Você não possui serviços escalados lançados no sistema atualmente.")
        else:
            df_minhas = pd.DataFrame(minhas_escalas)
            # Reordenar colunas
            df_minhas = df_minhas[["Data", "Servico", "Horario"]]
            st.dataframe(df_minhas, hide_index=True, use_container_width=True)

    # -------------------------------------------------------------------------
    # TELA 3: LANÇAR ESCALAS (Visão do P1 / ADMIN)
    # -------------------------------------------------------------------------
    elif escolha == "⚙️ Lançar Escalas (P1)" and is_admin:
        st.title("⚙️ ADMINISTRAÇÃO DE ESCALAS (P1)")
        st.write("Lançamento oficial no banco de dados. A atualização é instantânea para a tropa.")
        
        with st.form("form_lancar_escala"):
            col1, col2 = st.columns(2)
            with col1:
                data_escala = st.date_input("Data do Serviço:", date.today())
                servico = st.selectbox("Tipo de Serviço:", TIPOS_SERVICO)
            with col2:
                horario = st.text_input("Horário (Ex: 08h as 08h, 12h as 13h):")
                # Dropdown com os policiais ativos para evitar erro de digitação de matrícula
                lista_policiais = [f"{p['Matricula']} - {p['Graduacao']} {p['Nome']}" for p in efetivo_db if str(p.get("Status")).upper() == "ATIVO"]
                policial_selecionado = st.selectbox("Selecione o Policial:", lista_policiais)
            
            submit = st.form_submit_button("💾 Salvar Escala", use_container_width=True)
            
            if submit:
                if horario and policial_selecionado:
                    mat_selecionada = policial_selecionado.split(" - ")[0]
                    data_formatada = data_escala.strftime("%d/%m/%Y")
                    
                    nova_linha = [data_formatada, servico, horario, mat_selecionada]
                    
                    sh = conectar_planilha()
                    if sh:
                        try:
                            ws = sh.worksheet("Escalas_Lancadas")
                            ws.append_row(nova_linha)
                            st.success(f"✅ Escala de {servico} para o dia {data_formatada} gravada com sucesso!")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")
                else:
                    st.warning("Preencha todos os campos corretamente.")

    # -------------------------------------------------------------------------
    # TELA 4: RELAÇÃO DO EFETIVO (ADMIN)
    # -------------------------------------------------------------------------
    elif escolha == "📋 Relação do Efetivo" and is_admin:
        st.title("📋 CONTROLE DE EFETIVO")
        st.write("Visualização da aba 'Efetivo' do banco de dados.")
        df_efetivo = pd.DataFrame(efetivo_db)
        # Ocultar a senha por segurança na tela
        if 'Senha' in df_efetivo.columns:
            df_efetivo = df_efetivo.drop(columns=['Senha'])
        st.dataframe(df_efetivo, use_container_width=True)
