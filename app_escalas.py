import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import time
import re
import calendar

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
    .funcao-text { color: #17a2b8; font-size: 0.95em; font-weight: bold; margin-top: 2px;}
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
    "Guarda do Quartel (24h)",
    "Núcleo de Psicologia",
    "Serviço Administrativo"
]

HORARIOS_PADRAO = [
    "07h às 07h (24h)",
    "07h às 19h (12h)",
    "19h às 07h (12h)",
    "08h às 15h (Expediente)",
    "15h às 21h (Visibilidade)",
    "Outro (Digitar manualmente)"
]

GRADUACOES = [
    "Cel PM", "Ten Cel PM", "Maj PM", "Cap PM", "1º Ten PM", "2º Ten PM", 
    "Subten PM", "1º Sgt PM", "2º Sgt PM", "3º Sgt PM", "Cb PM", "Sd PM", "Func. Civil"
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
        st.markdown("<h1 style='text-align: center; color: #ffd700;'>📑 SISTEMA ESCALAS DAS</h1>", unsafe_allow_html=True)
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
    
    menu_opcoes = ["🏠 Quadro de Hoje", "📅 Minhas Escalas", "🔑 Alterar Senha"]
    if is_admin:
        menu_opcoes.append("📊 Consultar Escalas Mensais") # <--- NOVO MENU DE VISÃO PANORÂMICA
        menu_opcoes.append("📢 Mural de Avisos (P1)")
        menu_opcoes.append("⚙️ Lançar Escalas (P1 Turbo)")
        menu_opcoes.append("📥 Importar Planilha (P1)")
        menu_opcoes.append("➕ Cadastrar Efetivo")
        menu_opcoes.append("📋 Relação do Efetivo")
        
    escolha = st.sidebar.radio("Navegação", menu_opcoes)
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Sair do Sistema"):
        logout()

    efetivo_db = carregar_dados("Efetivo")
    escalas_db = carregar_dados("Escalas_Lancadas")
    avisos_db = carregar_dados("Avisos_Gerais")
    dict_efetivo = {str(p["Matricula"]): p for p in efetivo_db}

    # -------------------------------------------------------------------------
    # TELA 1: QUADRO DE HOJE E MURAL DE AVISOS
    # -------------------------------------------------------------------------
    if escolha == "📑 Quadro de Hoje":
        st.title("🪪 QUADRO DE SERVIÇO DIÁRIO")
        
        if avisos_db:
            agora = datetime.now()
            avisos_ativos = []
            
            for aviso in avisos_db:
                try:
                    data_aviso = datetime.strptime(str(aviso.get('Data_Hora', '')), "%d/%m/%Y %H:%M")
                    if agora - data_aviso <= timedelta(hours=24):
                        avisos_ativos.append(aviso)
                except:
                    pass 
            
            if avisos_ativos:
                st.markdown("### 📢 MURAL DO COMANDO (Avisos Gerais)")
                for aviso in reversed(avisos_ativos):
                    st.warning(f"**Mensagem:** {aviso.get('Aviso', '')}\n\n*Assinado por: **{aviso.get('Autor', '')}** em {aviso.get('Data_Hora', '')}*")
                st.markdown("---")
        
        data_filtro = st.date_input("Filtrar por Data da Escala:", date.today())
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
                    funcao_posto = pol_escala.get("Funcao", "")
                    
                    tel_limpo = re.sub(r'\D', '', telefone)
                    if len(tel_limpo) == 10 or len(tel_limpo) == 11: tel_limpo = f"55{tel_limpo}" 
                        
                    html_obs = f"<span class='obs-text'>⚠️ <b>Obs:</b> {obs}</span>" if obs else ""
                    html_funcao = f"<div class='funcao-text'>📌 Função/Posto: {funcao_posto}</div>" if funcao_posto else ""
                    
                    card_html = f"<div class='card-policial'><span class='graduacao'>{grad} {nome}</span> (Mat: {mat}){html_funcao}<br>⏰ <b>Horário:</b> {horario}{html_obs}<div class='botoes-container'><a href='https://api.whatsapp.com/send?phone={tel_limpo}' target='_blank' class='btn-wpp'>💬 WhatsApp</a><a href='tel:{telefone}' class='btn-ligar'>📞 Ligar</a></div></div>"
                    
                    st.markdown(card_html, unsafe_allow_html=True)
                st.markdown("---")

    # -------------------------------------------------------------------------
    # TELA 2: VISÃO PANORÂMICA (CONSULTA MENSAIS) - MÓDULO P1 / ADMIN
    # -------------------------------------------------------------------------
    elif escolha == "📊 Consultar Escalas Mensais" and is_admin:
        st.title("📊 CONSULTA DE ESCALAS MENSAIS")
        st.write("Visão global das escalas lançadas. Filtre, visualize, copie os dados ou baixe para o Excel.")
        
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            
            meses_dict = {1:"Janeiro", 2:"Fevereiro", 3:"Março", 4:"Abril", 5:"Maio", 6:"Junho", 7:"Julho", 8:"Agosto", 9:"Setembro", 10:"Outubro", 11:"Novembro", 12:"Dezembro"}
            
            with col1:
                mes_selecionado = st.selectbox("Selecione o Mês:", options=list(meses_dict.keys()), format_func=lambda x: meses_dict[x], index=datetime.now().month - 1)
            with col2:
                ano_selecionado = st.number_input("Ano:", min_value=2024, max_value=2050, value=datetime.now().year)
            with col3:
                servico_filtro = st.selectbox("Selecione o Setor/Serviço:", ["Todos os Serviços"] + TIPOS_SERVICO)
            
            buscar = st.button("🔍 Buscar Escalas do Mês", use_container_width=True)
            
        if buscar:
            escala_filtrada = []
            
            for e in escalas_db:
                try:
                    data_obj = datetime.strptime(str(e.get("Data", "")), "%d/%m/%Y")
                    # Filtra por Mês e Ano
                    if data_obj.month == mes_selecionado and data_obj.year == ano_selecionado:
                        # Filtra por Serviço (Se não for "Todos")
                        if servico_filtro == "Todos os Serviços" or str(e.get("Servico", "")) == servico_filtro:
                            
                            mat = str(e.get("Matricula", ""))
                            pol_info = dict_efetivo.get(mat, {})
                            nome_completo = f"{pol_info.get('Graduacao', '')} {pol_info.get('Nome', 'Não Encontrado')}".strip()
                            
                            escala_filtrada.append({
                                "Data": e.get("Data", ""),
                                "Policial": nome_completo,
                                "Matricula": mat,
                                "Funcao/Posto": e.get("Funcao", ""),
                                "Horario": e.get("Horario", ""),
                                "Setor/Servico": e.get("Servico", ""),
                                "Observacao": e.get("Observacao", "")
                            })
                except Exception as ex:
                    pass # Ignora linhas com datas inválidas ou vazias
                    
            if escala_filtrada:
                df_escala = pd.DataFrame(escala_filtrada)
                # Ordenar cronologicamente pela data
                df_escala['Data_Formatada'] = pd.to_datetime(df_escala['Data'], format='%d/%m/%Y')
                df_escala = df_escala.sort_values(by='Data_Formatada').drop(columns=['Data_Formatada'])
                
                st.success(f"🎯 Foram encontrados **{len(df_escala)}** serviços lançados para os filtros selecionados.")
                
                # Exibe a tabela interativa (Permite copiar arrastando o mouse)
                st.dataframe(df_escala, hide_index=True, use_container_width=True)
                
                # Botão Nativo de Download
                csv_dados = df_escala.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    label="📥 BAIXAR TABELA EM EXCEL (.CSV)",
                    data=csv_dados,
                    file_name=f"escala_{meses_dict[mes_selecionado]}_{ano_selecionado}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning("⚠️ Nenhuma escala foi encontrada no banco de dados para este Mês/Ano e Setor.")

    # -------------------------------------------------------------------------
    # TELA 3: IMPORTAR PLANILHA (P1) - MÓDULO VISÃO DE ÁGUIA
    # -------------------------------------------------------------------------
    elif escolha == "📥 Importar Planilha (P1)" and is_admin:
        st.title("📥 IMPORTAÇÃO TÁTICA (Excel / CSV)")
        st.write("Lançamento em massa através de arquivo. Extraia sua escala do Excel e faça o upload.")
        
        st.info("""
        ⚠️ **Regras de Engajamento para a Planilha:**
        A sua planilha (.xlsx ou .csv) deve ter uma linha de cabeçalho com os **nomes exatos** destas 6 colunas:
        `Data` | `Servico` | `Horario` | `Matricula` | `Observacao` | `Funcao`
        """)
        
        arquivo_up = st.file_uploader("Suba a Escala Oficial (Formato .xlsx ou .csv)", type=["xlsx", "csv"])
        
        if arquivo_up:
            try:
                if arquivo_up.name.endswith('.csv'):
                    df_import = pd.read_csv(arquivo_up)
                else:
                    df_import = pd.read_excel(arquivo_up)
                
                colunas_esperadas = ['Data', 'Servico', 'Horario', 'Matricula']
                colunas_arquivo = df_import.columns.tolist()
                
                if not all(col in colunas_arquivo for col in colunas_esperadas):
                    st.error(f"❌ Erro de Formato: A planilha não possui as colunas obrigatórias. Esperado: {colunas_esperadas}")
                else:
                    if 'Observacao' not in df_import.columns: df_import['Observacao'] = ""
                    if 'Funcao' not in df_import.columns: df_import['Funcao'] = ""
                    
                    df_import = df_import.fillna("")
                    st.markdown("### 🔍 Raio-X da Planilha (Pré-visualização)")
                    st.dataframe(df_import.head(10), use_container_width=True)
                    st.caption(f"Total de registros detectados: **{len(df_import)}** serviços.")
                    
                    if st.button("🚀 Confirmar e Lançar no Banco de Dados", use_container_width=True):
                        with st.spinner("Processando dados pesados..."):
                            linhas_para_inserir = []
                            
                            for index, row in df_import.iterrows():
                                try:
                                    data_bruta = row['Data']
                                    if isinstance(data_bruta, datetime):
                                        data_formatada = data_bruta.strftime("%d/%m/%Y")
                                    else:
                                        data_obj = pd.to_datetime(data_bruta, dayfirst=True)
                                        data_formatada = data_obj.strftime("%d/%m/%Y")
                                    
                                    serv = str(row['Servico']).strip()
                                    hor = str(row['Horario']).strip()
                                    mat = str(row['Matricula']).split('.')[0].strip()
                                    obs = str(row['Observacao']).strip()
                                    func = str(row['Funcao']).strip()
                                    
                                    linhas_para_inserir.append([data_formatada, serv, hor, mat, obs, func])
                                except Exception as e:
                                    pass
                            
                            if linhas_para_inserir:
                                sh = conectar_planilha()
                                if sh:
                                    try:
                                        ws = sh.worksheet("Escalas_Lancadas")
                                        ws.append_rows(linhas_para_inserir)
                                        st.success(f"✅ Bombardeio Concluído! {len(linhas_para_inserir)} serviços lançados com sucesso na Nuvem.")
                                        st.cache_resource.clear()
                                        time.sleep(3)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao salvar na planilha: {e}")
                            else:
                                st.warning("Nenhum dado válido encontrado para importar.")

            except Exception as e:
                st.error(f"Erro ao processar o arquivo. Verifique se não está corrompido. Detalhe: {e}")

    # -------------------------------------------------------------------------
    # TELA 4: MURAL DE AVISOS (PUBLICAR E APAGAR)
    # -------------------------------------------------------------------------
    elif escolha == "📢 Mural de Avisos (P1)" and is_admin:
        st.title("📢 GESTÃO DO MURAL DE AVISOS")
        
        st.subheader("1. Publicar Novo Aviso")
        st.write("Atenção: Os avisos somem automaticamente da tela da tropa após 24 horas.")
        with st.form("form_aviso"):
            texto_aviso = st.text_area("Digite a mensagem da Ordem/Aviso:")
            submit_aviso = st.form_submit_button("📤 Publicar no Mural", use_container_width=True)
            
            if submit_aviso:
                if texto_aviso:
                    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
                    autor_assinatura = f"{user.get('Graduacao', '')} {user.get('Nome', '')}"
                    
                    sh = conectar_planilha()
                    if sh:
                        try:
                            ws = sh.worksheet("Avisos_Gerais")
                            ws.append_row([data_hora, texto_aviso, autor_assinatura])
                            st.success(f"✅ Aviso publicado com sucesso como '{autor_assinatura}'!")
                            st.cache_resource.clear()
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao publicar: {e}")
                else:
                    st.warning("⚠️ Digite uma mensagem antes de publicar.")
                    
        st.markdown("---")
        st.subheader("2. Histórico e Remoção de Avisos")
        if not avisos_db:
            st.info("Nenhum aviso no banco de dados.")
        else:
            for idx, aviso in enumerate(avisos_db):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.write(f"📅 **{aviso.get('Data_Hora', '')}** | {aviso.get('Aviso', '')} | ✍️ *{aviso.get('Autor', '')}*")
                with col2:
                    if st.button("🗑️ Apagar", key=f"del_aviso_{idx}"):
                        sh = conectar_planilha()
                        if sh:
                            try:
                                ws = sh.worksheet("Avisos_Gerais")
                                ws.delete_rows(idx + 2) 
                                st.success("Aviso desintegrado do banco de dados!")
                                st.cache_resource.clear()
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao apagar: {e}")
                st.markdown("---")

    # -------------------------------------------------------------------------
    # TELA 5: MINHAS ESCALAS E PERMUTAS
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
            colunas_exibir = ["Data", "Servico", "Horario"]
            if 'Funcao' in df_minhas.columns: colunas_exibir.append("Funcao")
            if 'Observacao' in df_minhas.columns: colunas_exibir.append("Observacao")
            
            st.dataframe(df_minhas[colunas_exibir], hide_index=True, use_container_width=True)
            
            st.markdown("---")
            st.subheader("🔄 Informar Permuta / Alteração")
            with st.form("form_permuta"):
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
                                records = ws.get_all_records()
                                linha_encontrada = None
                                
                                for idx, row in enumerate(records):
                                    if str(row.get("Data")) == data_alvo and str(row.get("Servico")) == serv_alvo and str(row.get("Matricula")) == minha_mat:
                                        linha_encontrada = idx + 2 
                                        break
                                
                                if linha_encontrada:
                                    ws.update_cell(linha_encontrada, 5, nova_obs)
                                    st.success("✅ Permuta/Observação informada com sucesso ao Comando!")
                                    st.cache_resource.clear()
                                    time.sleep(1.5)
                                    st.rerun()
                                else:
                                    st.error("Erro: Serviço não encontrado no banco de dados.")
                            except Exception as e:
                                st.error(f"Erro de comunicação: {e}")
                    else:
                        st.warning("Escreva a observação antes de salvar.")

    # -------------------------------------------------------------------------
    # TELA 6: ALTERAR SENHA
    # -------------------------------------------------------------------------
    elif escolha == "🔑 Alterar Senha":
        st.title("🔑 ALTERAR MINHA SENHA")
        
        with st.form("form_senha"):
            senha_atual = st.text_input("Senha Atual:", type="password")
            senha_nova = st.text_input("Nova Senha:", type="password")
            senha_conf = st.text_input("Confirme a Nova Senha:", type="password")
            
            submit_senha = st.form_submit_button("🔄 Atualizar Senha", use_container_width=True)
            
            if submit_senha:
                if senha_atual != str(user.get("Senha")):
                    st.error("❌ A senha atual está incorreta.")
                elif senha_nova != senha_conf:
                    st.error("❌ As novas senhas não coincidem.")
                elif len(senha_nova) < 4:
                    st.error("⚠️ A nova senha deve ter pelo menos 4 caracteres.")
                else:
                    sh = conectar_planilha()
                    if sh:
                        try:
                            ws = sh.worksheet("Efetivo")
                            records = ws.get_all_records()
                            linha_encontrada = None
                            minha_mat = str(user.get("Matricula"))
                            
                            for idx, row in enumerate(records):
                                if str(row.get("Matricula")) == minha_mat:
                                    linha_encontrada = idx + 2
                                    break
                            
                            if linha_encontrada:
                                ws.update_cell(linha_encontrada, 2, senha_nova)
                                st.success("✅ Senha alterada com sucesso! Você será deslogado para acessar novamente.")
                                st.cache_resource.clear()
                                time.sleep(3)
                                logout()
                        except Exception as e:
                            st.error(f"Erro de comunicação: {e}")

    # -------------------------------------------------------------------------
    # TELA 7: CADASTRAR EFETIVO
    # -------------------------------------------------------------------------
    elif escolha == "➕ Cadastrar Efetivo" and is_admin:
        st.title("➕ CADASTRAR NOVO POLICIAL")
        
        with st.form("form_cad_pol"):
            col1, col2 = st.columns(2)
            with col1:
                mat_nova = st.text_input("Matrícula (Apenas Números):")
                grad_nova = st.selectbox("Graduação:", GRADUACOES)
                nome_novo = st.text_input("Nome de Guerra:")
            with col2:
                tel_novo = st.text_input("Telefone (WhatsApp) com DDD:")
                nivel_novo = st.selectbox("Nível de Acesso:", ["Comum", "P1", "Admin", "Comando"])
                status_novo = st.selectbox("Status Operacional:", ["Ativo", "LTS", "Férias", "Inativo"])
                
            submit_cad = st.form_submit_button("💾 Cadastrar Policial", use_container_width=True)
            
            if submit_cad:
                if mat_nova and nome_novo:
                    mat_str = str(mat_nova).strip()
                    if mat_str in dict_efetivo:
                        st.error("⚠️ Esta matrícula já está cadastrada no sistema!")
                    else:
                        sh = conectar_planilha()
                        if sh:
                            try:
                                ws = sh.worksheet("Efetivo")
                                nova_linha = [mat_str, mat_str, grad_nova, nome_novo, tel_novo, nivel_novo, status_novo]
                                ws.append_row(nova_linha)
                                st.success(f"✅ Policial {grad_nova} {nome_novo} cadastrado com sucesso! A senha inicial é: {mat_str}")
                                st.cache_resource.clear()
                                time.sleep(2)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")
                else:
                    st.warning("Preencha Matrícula e Nome obrigatoriamente.")

    # -------------------------------------------------------------------------
    # TELA 8: LANÇAR ESCALAS EM LOTE (P1 Turbo)
    # -------------------------------------------------------------------------
    elif escolha == "⚙️ Lançar Escalas (P1 Turbo)" and is_admin:
        st.title("⚙️ P1 TURBO: Lançamento em Lote Inteligente")
        
        with st.form("form_lancar_escala"):
            col1, col2 = st.columns(2)
            with col1:
                mes_ref = st.date_input("Selecione qualquer data do Mês/Ano da Escala:", date.today())
                servico = st.selectbox("Tipo de Serviço:", TIPOS_SERVICO)
                
                lista_policiais = [f"{p['Matricula']} - {p['Graduacao']} {p['Nome']}" for p in efetivo_db if str(p.get("Status")).upper() == "ATIVO"]
                policial_selecionado = st.selectbox("Selecione o Policial:", lista_policiais)
                funcao_escala = st.text_input("Função / Posto (Ex: Rota 01/VT 38, Motorista, Cb de Dia):")
                
            with col2:
                opcao_horario = st.selectbox("Horário Padrão:", HORARIOS_PADRAO)
                if opcao_horario == "Outro (Digitar manualmente)":
                    horario_final = st.text_input("Digite o horário customizado:")
                else:
                    horario_final = opcao_horario
                
                st.markdown("🎯 **Modo de Seleção de Dias:**")
                modo_dias = st.radio("Selecione o Padrão do Mês:", ["Digitar Manualmente", "Todos os Dias Pares", "Todos os Dias Ímpares"])
                
                dias_str = ""
                if modo_dias == "Digitar Manualmente":
                    dias_str = st.text_input("Digite os dias separados por vírgula (Ex: 1, 5, 9, 13, 21):")
                
                observacao = st.text_input("Observação Geral (Opcional):")
            
            submit = st.form_submit_button("💾 Gerar e Salvar Escala", use_container_width=True)
            
            if submit:
                if modo_dias == "Digitar Manualmente" and not dias_str:
                    st.warning("⚠️ Você precisa informar os dias na opção manual.")
                elif opcao_horario == "Outro (Digitar manualmente)" and not horario_final:
                    st.warning("⚠️ Você escolheu 'Outro', mas não digitou o horário.")
                elif policial_selecionado:
                    mat_selecionada = policial_selecionado.split(" - ")[0]
                    
                    mes = mes_ref.month
                    ano = mes_ref.year
                    _, ult_dia = calendar.monthrange(ano, mes)
                    
                    dias_limpos = []
                    if modo_dias == "Todos os Dias Pares":
                        dias_limpos = [d for d in range(1, ult_dia + 1) if d % 2 == 0]
                    elif modo_dias == "Todos os Dias Ímpares":
                        dias_limpos = [d for d in range(1, ult_dia + 1) if d % 2 != 0]
                    else:
                        dias_limpos = [int(d.strip()) for d in dias_str.split(',') if d.strip().isdigit()]
                    
                    if dias_limpos:
                        linhas_para_inserir = []
                        for dia in dias_limpos:
                            try:
                                data_formatada = date(ano, mes, dia).strftime("%d/%m/%Y")
                                linhas_para_inserir.append([data_formatada, servico, horario_final, mat_selecionada, observacao, funcao_escala])
                            except ValueError:
                                pass
                        
                        if linhas_para_inserir:
                            sh = conectar_planilha()
                            if sh:
                                try:
                                    ws = sh.worksheet("Escalas_Lancadas")
                                    ws.append_rows(linhas_para_inserir)
                                    st.success(f"✅ Escala Operacional de {len(linhas_para_inserir)} serviços gerada com sucesso para a Mat: {mat_selecionada}!")
                                    st.cache_resource.clear()
                                    time.sleep(2.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar na planilha: {e}")
                    else:
                        st.warning("⚠️ Nenhum dia válido encontrado para gerar a escala.")

    # -------------------------------------------------------------------------
    # TELA 9: RELAÇÃO DO EFETIVO
    # -------------------------------------------------------------------------
    elif escolha == "📋 Relação do Efetivo" and is_admin:
        st.title("📋 CONTROLE DE EFETIVO")
        st.write("Visualização da aba 'Efetivo' do banco de dados.")
        df_efetivo = pd.DataFrame(efetivo_db)
        if 'Senha' in df_efetivo.columns:
            df_efetivo = df_efetivo.drop(columns=['Senha'])
        st.dataframe(df_efetivo, use_container_width=True)
