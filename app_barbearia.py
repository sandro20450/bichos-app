import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =============================================================================
# 🎯 ATENÇÃO COMANDANTE: COLE O LINK DA SUA PLANILHA DA BARBEARIA AQUI!
# =============================================================================
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1N1bcNC0-qyGTqFKexromMiUMKtMZTaqfBTCmRZjFGZc/edit?gid=0#gid=0"

# =============================================================================
# --- 1. CONFIGURAÇÃO DA PÁGINA ---
# =============================================================================
st.set_page_config(page_title="Barbearia D'Ramos", page_icon="💈", layout="centered")

# =============================================================================
# --- 2. CONEXÃO BLINDADA COM O GOOGLE SHEETS ---
# =============================================================================
def conectar_sheets():
    """Estabelece a conexão com a API do Google usando os Secrets do Streamlit."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client.open_by_url(URL_PLANILHA).worksheet("Registros")
    except Exception as e:
        st.error(f"⚠️ Erro de conexão com a planilha. Detalhes: {e}")
        return None

def carregar_dados():
    """Busca todos os dados da aba 'Registros' e converte para um DataFrame Pandas."""
    ws = conectar_sheets()
    if ws:
        dados = ws.get_all_values()
        if len(dados) > 1:
            cabecalhos = [str(c).strip() for c in dados[0]]
            df = pd.DataFrame(dados[1:], columns=cabecalhos)
            df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0.0)
            return df
    return pd.DataFrame()

# =============================================================================
# --- 3. MENU DE NAVEGAÇÃO LATERAL ---
# =============================================================================
with st.sidebar:
    st.title("💈 Barbearia D'Ramos")
    menu = st.radio("Selecione a Operação:", ["📝 Registrar Serviço", "📊 Relatório Financeiro"])
    st.markdown("---")
    st.info("Sistema de Gestão Financeira Integrado.")

# =============================================================================
# --- 4. TELA 1: REGISTRO DE SERVIÇOS ---
# =============================================================================
if menu == "📝 Registrar Serviço":
    st.header("Novo Serviço Realizado")
    
    with st.form("form_registro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            profissional = st.selectbox("Quem fez o serviço?", ["Proprietário", "Sócio"])
            servico = st.selectbox("Qual serviço?", ["Corte", "Barba", "Sobrancelha", "Corte + Barba", "Outros"])
            
        with col2:
            valor = st.number_input("Valor Cobrado (R$)", min_value=0.0, format="%.2f", step=5.0)
            pagamento = st.selectbox("Forma de Pagamento", ["PIX", "Dinheiro", "Cartão", "Fiado"])
            
        btn_salvar = st.form_submit_button("💾 Salvar Registro", use_container_width=True)
        
        if btn_salvar:
            if valor <= 0:
                st.warning("⚠️ O valor do serviço deve ser maior que zero.")
            else:
                ws = conectar_sheets()
                if ws:
                    data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    nova_linha = [data_atual, profissional, servico, f"{valor:.2f}", pagamento]
                    ws.append_row(nova_linha)
                    st.success(f"✅ Serviço de {servico} registrado com sucesso para o {profissional}!")

# =============================================================================
# --- 5. TELA 2: RELATÓRIO FINANCEIRO (ATUALIZADO COM FILTROS) ---
# =============================================================================
elif menu == "📊 Relatório Financeiro":
    st.header("Fechamento de Caixa")
    
    df = carregar_dados()
    
    if df.empty:
        st.info("Nenhum serviço registrado ainda na planilha.")
    else:
        # Extrair apenas a data (YYYY-MM-DD) para facilitar a busca
        df['Data_Curta'] = df['Data'].str[:10]
        
        # 1. NOVO FILTRO DE PERÍODO (Data Inicial e Final)
        st.markdown("### 📅 Escolha o Período")
        # O Streamlit permite que o date_input receba uma tupla (lista) com duas datas
        data_selecionada = st.date_input(
            "Selecione a Data Inicial e a Data Final:", 
            value=(datetime.today(), datetime.today())
        )
        
        # Lógica para garantir que o sistema não quebre se o usuário clicar apenas em uma data e não fechar o período
        if len(data_selecionada) == 2:
            data_inicio = data_selecionada[0].strftime("%Y-%m-%d")
            data_fim = data_selecionada[1].strftime("%Y-%m-%d")
        else:
            data_inicio = data_selecionada[0].strftime("%Y-%m-%d")
            data_fim = data_selecionada[0].strftime("%Y-%m-%d")
        
        # Varrer a planilha cruzando as informações para encontrar as datas dentro do período
        df_filtrado = df[(df['Data_Curta'] >= data_inicio) & (df['Data_Curta'] <= data_fim)]
        
        if df_filtrado.empty:
            st.warning("Nenhum serviço encontrado para este período.")
        else:
            # Cálculos Matemáticos (Refletem o período escolhido)
            total_bruto = df_filtrado['Valor'].sum()
            producao_proprietario = df_filtrado[df_filtrado['Profissional'] == 'Proprietário']['Valor'].sum()
            producao_socio = df_filtrado[df_filtrado['Profissional'] == 'Sócio']['Valor'].sum()
            
            parte_socio = producao_socio * 0.50
            lucro_proprietario = producao_proprietario + (producao_socio * 0.50)
            
            st.markdown("### 💰 Resumo do Período")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Faturamento Total", value=f"R$ {total_bruto:.2f}")
            with col2:
                st.metric(label="Proprietário Recebe", value=f"R$ {lucro_proprietario:.2f}")
            with col3:
                st.metric(label="Sócio Recebe", value=f"R$ {parte_socio:.2f}")
                
            st.markdown("---")
            
            # Resumo por forma de pagamento
            st.markdown("### 💳 Entrada por Pagamento")
            resumo_pagamento = df_filtrado.groupby('Pagamento')['Valor'].sum().reset_index()
            st.dataframe(resumo_pagamento, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # 2. NOVO FILTRO DE PROFISSIONAL PARA A TABELA DETALHADA
            st.markdown("### 📋 Histórico Detalhado")
            
            # Criamos um seletor que ficará logo acima da tabela
            filtro_profissional = st.selectbox(
                "Filtrar lista abaixo por Profissional:", 
                ["Todos", "Proprietário", "Sócio"]
            )
            
            # Lógica do filtro: Se não for "Todos", isolar apenas quem foi escolhido
            if filtro_profissional != "Todos":
                df_historico = df_filtrado[df_filtrado['Profissional'] == filtro_profissional]
            else:
                df_historico = df_filtrado
            
            # Mostrar a tabela com o novo filtro aplicado
            st.dataframe(df_historico[['Data', 'Profissional', 'Servico', 'Valor', 'Pagamento']], use_container_width=True, hide_index=True)
