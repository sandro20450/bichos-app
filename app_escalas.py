import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import time
import re

# =============================================================================
# --- CONFIGURAÇÕES DA PÁGINA E ESTILOS ---
# =============================================================================
st.set_page_config(page_title="ESCALAS DAS - Comando", page_icon="👮‍♂️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card-policial { background-color: #1e2530; padding: 15px; border-radius: 10px; border-left: 5px solid #28a745; margin-bottom: 10px; }
    .graduacao { color: #ffd700; font-weight: bold; font-size: 1.1em; }
    .btn-ligar { background-color: #28a745; color: white; padding: 5px 10px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 0.9em; float: right; margin-left: 5px;}
    .btn-ligar:hover { background-color: #218838; color: white; }
    .btn-wpp { background-color: #25D366; color: white; padding: 5px 10px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 0.9em; float: right; }
    .btn-wpp:hover { background-color: #128C7E; color: white; }
    .obs-text { color: #ffc107; font-size: 0.9em; margin-top: 5px; display: block;}
    .botoes-container { margin-top: 10px; display: block; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

TIPOS_SERVICO = [
    "Recepção DAS (24h)", 
    "Sobreaviso Oficiais/ST", 
    "Motorista SSTRAN (24h)", 
    "Operação Visibilidade (8h)", 
    "Vila Militar (8h)", 
    "Rendição Almoço (1h)",
    "Guarda do Quartel (24h)"
]

HORARIOS_PADRAO = [
    "07h às 07h (24h)",
    "07h às 19h (12h)",
    "19h às 07h (12h)",
    "08h às 15h (Expediente)",
    "15h às 21h (Visibilidade)",
    "Outro (Digitar manualmente)"
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
            chave_planilha = "1VyaWftpKA8V4m4SH2IX9xqkbgv4-uPIxZ27tq1FsFns" 
            return gc.open_by_key(chave_planilha)
        except Exception as e:
            st.error(f"Erro de conexão com o Google Sheets: {e}")
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
# --- SISTEMA DE LOGIN ---
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
# --- APLICATIVO PRINCIPAL ---
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

else:
    user = st.session_state.user_data
    is_admin = user.get("Nivel", "Comum").strip().upper() in ["ADMIN", "P1", "COMANDO"]
    
    st.sidebar.markdown(f"### 👮‍♂️ {user.get('Graduacao', '')} {user.get('Nome', '')}")
    st.sidebar.caption(f"Matrícula: {user.get('Matricula', '')}")
    st.sidebar.markdown("---")
    
    menu_opcoes = ["🏠 Quadro de Hoje", "📅 Minhas Escalas"]
    if is_admin:
        menu_opcoes.append("⚙️ Lançar Escalas (P1 Turbo)")
        menu_opcoes.append("📋 Relação do Efetivo")
        
    escolha = st.sidebar.radio("Navegação", menu_opcoes)
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Sair do Sistema"):
        logout()

    efetivo_db = carregar_dados("Efetivo")
    escalas_db = carregar_dados("Escalas_Lancadas")
    dict_efetivo = {str(p["Matricula"]): p for p in efetivo_db}

    # -------------------------------------------------------------------------
    # TELA 1: QUADRO DE HOJE
    # -------------------------------------------------------------------------
    if escolha == "🏠 Quadro de Hoje":
        st.title("🦅 QUADRO DE SERVIÇO DIÁRIO")
        
        data_filtro = st.date_input("Filtrar por Data:", date.today())
        data_str = data_filtro.strftime("%d/%m/%Y")
        
        st.subheader(f"Efetivo Empregado em: {data_str}")
        
        escalas_hoje = [e for e in escalas_db if str(e.get("Data", "")) == data_str]
        
        if not escalas_hoje:
            st.info("Nenhuma escala lançada para esta data.")
        else:
            servicos_do_dia = {}
            for e in escalas_hoje:
                srv = e["Servico"]
                if srv not in servicos_do_dia:
                    servicos_do_dia[srv] = []
                servicos_do_dia[srv].append(e)
            
            for srv, policiais in servicos_do_dia.items():
                st.markdown(f"### 🎯 {srv}")
                for pol_escala in policiais:
                    mat = str(pol_escala.get("Matricula", ""))
                    dados_pol = dict_efetivo.get(mat, {})
                    
                    nome = dados_pol.get("Nome", "Policial Não Encontrado")
                    grad = dados_pol.get("Graduacao", "")
                    telefone = str(dados_pol.get("Telefone", ""))
                    horario = pol_escala.get("Horario", "N/I")
                    obs = pol_escala.get("Observacao", "")
                    
                    tel_limpo = re.sub(r'\D', '', telefone)
                    if len(tel_limpo) == 10 or len(tel_limpo) == 11: tel_limpo = f"55{tel_limpo}" 
                        
                    html_obs = f"<span class='obs-text'>⚠️ <b>Obs:</b> {obs}</span>" if obs else ""
                    
                    # LINHA ÚNICA CEGA PARA MATAR O BUG DO MARKDOWN
                    card_html = f"<div class='card-policial'><span class='graduacao'>{grad} {nome}</span> (Mat: {mat})<br>⏰ <b>Horário:</b> {horario}{html_obs}<div class='botoes-container'><a href='https://api.whatsapp.com/send?phone={tel_limpo}' target='_blank' class='btn-wpp'>💬 WhatsApp</a><a href='tel:{telefone}' class='btn-ligar'>📞 Ligar</a></div></div>"
                    
                    st.markdown(card_html, unsafe_allow_html=True)
                st.markdown("---")

    # -------------------------------------------------------------------------
    # TELA 2: MINHAS ESCALAS E PERMUTAS (Visão do Policial)
    # -------------------------------------------------------------------------
    elif escolha == "📅 Minhas Escalas":
        st.title("📅 MINHAS MISSÕES E PERMUTAS")
        st.write("Acompanhe seus serviços e informe permutas ou alterações diretamente ao Oficial de Dia.")
        
        minha_mat = str(user.get("Matricula"))
        minhas_escalas = [e for e in escalas_db if str(e.get("Matricula", "")) == minha_mat]
        
        if not minhas_escalas:
            st.success("Você não possui serviços escalados lançados no sistema atualmente.")
        else:
            df_minhas = pd.DataFrame(minhas_escalas)
            if 'Observacao' in df_minhas.columns:
                df_minhas = df_minhas[["Data", "Servico", "Horario", "Observacao"]]
            else:
                df_minhas = df_minhas[["Data", "Servico", "Horario"]]
            st.dataframe(df_minhas, hide_index=True, use_container_width=True)
            
            st.markdown("---")
            st.subheader("🔄 Informar Permuta / Alteração")
            with st.form("form_permuta"):
                # Cria uma lista amigável para o policial escolher qual serviço ele quer alterar
                opcoes_servico = [f"{e['Data']} | {e['Servico']}" for e in minhas_escalas]
                serv_selecionado = st.selectbox("Escolha o Serviço:", opcoes_servico)
                nova_obs = st.text_input("Descreva a alteração (Ex: Permutado com o Sd Silva, Mat 1234-5):")
                
                if st.form_submit_button("Atualizar Serviço", use_container_width=True):
                    if nova_obs:
                        data_alvo = serv_selecionado.split(" | ")[0]
                        serv_alvo = serv_selecionado.split(" | ")[1]
                        
                        sh = conectar_planilha()
                        if sh:
                            try:
                                ws = sh.worksheet("Escalas_Lancadas")
                                # Baixa tudo para achar a linha exata
                                records = ws.get_all_records()
                                linha_encontrada = None
                                
                                # A primeira linha de dados é a linha 2 no Excel/Sheets
                                for idx, row in enumerate(records):
                                    if str(row.get("Data")) == data_alvo and str(row.get("Servico")) == serv_alvo and str(row.get("Matricula")) == minha_mat:
                                        linha_encontrada = idx + 2 
                                        break
                                
                                if linha_encontrada:
                                    # Atualiza a coluna 5 (Coluna E = Observacao)
                                    ws.update_cell(linha_encontrada, 5, nova_obs)
                                    st.success("✅ Permuta/Observação informada com sucesso ao Comando!")
                                    st.cache_resource.clear()
                                    time.sleep(1.5)
                                    st.rerun()
                                else:
                                    st.error("Erro: Serviço não encontrado no banco de dados para atualização.")
                            except Exception as e:
                                st.error(f"Erro de comunicação: {e}")
                    else:
                        st.warning("Escreva a observação antes de salvar.")

    # -------------------------------------------------------------------------
    # TELA 3: LANÇAR ESCALAS EM LOTE (Visão do P1)
    # -------------------------------------------------------------------------
    elif escolha == "⚙️ Lançar Escalas (P1 Turbo)" and is_admin:
        st.title("⚙️ P1 TURBO: Lançamento em Lote")
        st.write("Lance dezenas de serviços de uma única vez para escalas repetitivas (24x72, 12x36).")
        
        with st.form("form_lancar_escala"):
            col1, col2 = st.columns(2)
            with col1:
                mes_ref = st.date_input("Selecione qualquer data do Mês/Ano desejado:", date.today())
                servico = st.selectbox("Tipo de Serviço:", TIPOS_SERVICO)
                
                lista_policiais = [f"{p['Matricula']} - {p['Graduacao']} {p['Nome']}" for p in efetivo_db if str(p.get("Status")).upper() == "ATIVO"]
                policial_selecionado = st.selectbox("Selecione o Policial:", lista_policiais)
                
            with col2:
                # Sistema Inteligente de Horários
                opcao_horario = st.selectbox("Horário Padrão:", HORARIOS_PADRAO)
                if opcao_horario == "Outro (Digitar manualmente)":
                    horario_final = st.text_input("Digite o horário customizado:")
                else:
                    horario_final = opcao_horario
                
                # A MÁGICA DO LOTE ESTÁ AQUI
                st.markdown("🎯 **Dias do Mês:**")
                dias_str = st.text_input("Digite os dias separados por vírgula (Ex: 1, 5, 9, 13, 21):")
                observacao = st.text_input("Observação Geral (Opcional):")
            
            submit = st.form_submit_button("💾 Salvar Lote Inteiro", use_container_width=True)
            
            if submit:
                if not dias_str:
                    st.warning("⚠️ Você precisa informar pelo menos um dia do mês.")
                elif opcao_horario == "Outro (Digitar manualmente)" and not horario_final:
                    st.warning("⚠️ Você escolheu 'Outro', mas não digitou o horário.")
                elif policial_selecionado:
                    mat_selecionada = policial_selecionado.split(" - ")[0]
                    
                    # Extrai os números digitados e ignora espaços ou letras erradas
                    dias_limpos = [d.strip() for d in dias_str.split(',') if d.strip().isdigit()]
                    
                    if dias_limpos:
                        linhas_para_inserir = []
                        mes = mes_ref.month
                        ano = mes_ref.year
                        
                        for dia_str in dias_limpos:
                            dia = int(dia_str)
                            # Valida se o dia existe naquele mês
                            try:
                                data_formatada = date(ano, mes, dia).strftime("%d/%m/%Y")
                                linhas_para_inserir.append([data_formatada, servico, horario_final, mat_selecionada, observacao])
                            except ValueError:
                                st.error(f"❌ O dia {dia} não existe no mês {mes}/{ano}. Ignorado.")
                        
                        if linhas_para_inserir:
                            sh = conectar_planilha()
                            if sh:
                                try:
                                    ws = sh.worksheet("Escalas_Lancadas")
                                    # Usa append_rows para inserir todas as datas de uma vez só!
                                    ws.append_rows(linhas_para_inserir)
                                    st.success(f"✅ Lote de {len(linhas_para_inserir)} serviços gravado com sucesso para a Mat: {mat_selecionada}!")
                                    st.cache_resource.clear() # Limpa a memória para forçar atualização
                                    time.sleep(2)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar na planilha: {e}")
                    else:
                        st.warning("⚠️ Formato de dias inválido. Use apenas números separados por vírgula.")

    # -------------------------------------------------------------------------
    # TELA 4: RELAÇÃO DO EFETIVO
    # -------------------------------------------------------------------------
    elif escolha == "📋 Relação do Efetivo" and is_admin:
        st.title("📋 CONTROLE DE EFETIVO")
        st.write("Visualização da aba 'Efetivo' do banco de dados.")
        df_efetivo = pd.DataFrame(efetivo_db)
        if 'Senha' in df_efetivo.columns:
            df_efetivo = df_efetivo.drop(columns=['Senha'])
        st.dataframe(df_efetivo, use_container_width=True)
