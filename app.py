import streamlit as st
import pandas as pd
from collections import Counter
import gspread
from google.oauth2.service_account import Credentials
import requests
from datetime import datetime
import pytz

# =============================================================================
# --- 1. CONFIGURAÇÕES AVANÇADAS ---
# =============================================================================
st.set_page_config(page_title="Titanium V13 - Monitor", page_icon="🦅")

# 🔗 SEUS LINKS DE MONITORAMENTO
# Aqui colocamos um link diferente para cada banca
URLS_BANCAS = {
    "LOTEP": "https://www.resultadofacil.com.br/resultados-lotep-paraiba-de-hoje",
    "CAMINHODASORTE": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-de-hoje",
    "MONTECAI": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-de-hoje" # Substitua pelo link certo se tiver
}

BANCA_OPCOES = ["LOTEP", "CAMINHODASORTE", "MONTECAI"]

# =============================================================================
# --- 2. FUNÇÕES DE CONEXÃO E BANCO DE DADOS ---
# =============================================================================
def conectar_planilha(nome_aba):
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        try:
            sh = gc.open("CentralBichos")
            worksheet = sh.worksheet(nome_aba)
            return worksheet
        except Exception as e:
            st.error(f"Erro na planilha: {e}")
            return None
    return None

def carregar_dados(worksheet):
    if worksheet:
        valores = worksheet.col_values(1)
        return [int(v) for v in valores if v.isdigit()]
    return []

def salvar_na_nuvem(worksheet, numero):
    if worksheet:
        try:
            worksheet.append_row([int(numero)])
            return True
        except:
            return False
    return False

def deletar_ultimo_registro(worksheet):
    if worksheet:
        try:
            valores = worksheet.col_values(1)
            total_linhas = len(valores)
            if total_linhas > 0:
                worksheet.delete_rows(total_linhas)
                return True
        except:
            return False
    return False

# =============================================================================
# --- 3. O NOVO MONITOR (DETETIVE DE DATA) ---
# =============================================================================
def verificar_atualizacao_site(url):
    """
    Acessa o site e verifica se a DATA DE HOJE está escrita lá.
    Isso indica forte chance de ter saído resultado novo.
    """
    if not url:
        return False, "Link não configurado", ""
    
    try:
        # Pega a data de hoje no Brasil (ex: 24/05/2024)
        fuso_br = pytz.timezone('America/Sao_Paulo')
        hoje = datetime.now(fuso_br)
        
        # Formatos comuns de data em sites
        data_curta = hoje.strftime("%d/%m/%Y")   # 24/05/2024
        data_traco = hoje.strftime("%d-%m-%Y")   # 24-05-2024
        data_extenso = hoje.strftime("%d de")    # 24 de (maio...)
        
        # O robô acessa o site
        headers = {'User-Agent': 'Mozilla/5.0'}
        resposta = requests.get(url, headers=headers, timeout=5)
        
        if resposta.status_code == 200:
            texto_site = resposta.text
            
            # Verifica se alguma das datas está no texto do site
            if data_curta in texto_site or data_traco in texto_site or data_extenso in texto_site:
                return True, "🟢 SITE ATUALIZADO HOJE!", f"O site menciona a data de hoje ({data_curta})."
            else:
                return False, "🟡 Data de hoje não encontrada", f"O site está online, mas não achei a data {data_curta}."
        else:
            return False, "🔴 Site Fora do Ar", f"Erro código: {resposta.status_code}"
            
    except Exception as e:
        return False, "🔴 Erro de Conexão", f"Detalhe: {e}"

# =============================================================================
# --- 4. MOTOR TITANIUM V11.1 (INTELIGÊNCIA) ---
# =============================================================================
def calcular_ranking_forca(historico):
    if not historico: return []
    hist_reverso = historico[::-1]
    scores = {g: 0 for g in range(1, 26)}
    
    # Pesos
    c_curto = Counter(hist_reverso[:10])
    for g, f in c_curto.items(): scores[g] += (f * 2.0)
    
    c_medio = Counter(hist_reverso[:50])
    for g, f in c_medio.items(): scores[g] += (f * 1.0)
    
    rank = sorted(scores.items(), key=lambda x: -x[1])
    return [g for g, s in rank[:14]]

def gerar_backtest(historico):
    resultados = []
    if len(historico) < 15: return pd.DataFrame()
    for i in range(5):
        idx = len(historico) - 1 - i
        saiu = historico[idx]
        prev = calcular_ranking_forca(historico[:idx])
        status = "💚 VITÓRIA" if saiu in prev else "❌"
        resultados.append({"JOGO": f"Recente #{i+1}", "SAIU": f"{saiu:02}", "STATUS": status})
    return pd.DataFrame(resultados)

# =============================================================================
# --- 5. INTERFACE DO APLICATIVO ---
# =============================================================================
st.title("🦅 Titanium V13 Monitor")
st.caption("Sistema de Monitoramento & Inteligência")

# Seleção de Banca
banca_selecionada = st.selectbox("Selecione a Banca:", BANCA_OPCOES)
aba_ativa = conectar_planilha(banca_selecionada)

if aba_ativa:
    # --- ÁREA DE MONITORAMENTO (NOVIDADE) ---
    st.markdown("---")
    st.subheader(f"📡 Monitor: {banca_selecionada}")
    
    link_atual = URLS_BANCAS.get(banca_selecionada)
    
    col_status, col_botao = st.columns([2, 1])
    
    with col_status:
        # Verifica o site em tempo real
        online, titulo, detalhe = verificar_atualizacao_site(link_atual)
        if online:
            st.success(f"**{titulo}**\n\n{detalhe}")
        else:
            st.warning(f"**{titulo}**\n\n{detalhe}")

    with col_botao:
        st.write("Verifique o resultado:")
        if link_atual:
            st.link_button("🔗 ABRIR SITE AGORA", link_atual)
        else:
            st.error("Link não configurado")
    
    st.markdown("---")

    # --- ÁREA DE DADOS E PALPITES ---
    historico = carregar_dados(aba_ativa)
    
    if len(historico) > 0:
        ultimo = historico[-1]
        st.markdown(f"### Último na Planilha: **{ultimo:02}**")
        
        # Backtest e Palpites
        palpite = calcular_ranking_forca(historico)
        
        # Colunas para organizar
        c1, c2 = st.columns(2)
        with c1:
            st.info(f"🔥 **Fogo (Top 10):**\n\n{', '.join([f'{n:02}' for n in palpite[:10]])}")
        with c2:
            st.warning(f"❄️ **Gelo (Cobertura):**\n\n{', '.join([f'{n:02}' for n in palpite[10:]])}")

        # Tabela Backtest
        with st.expander("📊 Ver Histórico de Acertos (Backtest)"):
            df_back = gerar_backtest(historico)
            if not df_back.empty: st.table(df_back)

        st.markdown("---")
        
        # --- ÁREA DE INSERÇÃO MANUAL ---
        st.write("### 📝 Inserir Novo Resultado")
        col_input, col_action = st.columns([1, 1])
        
        with col_input:
            novo_bicho = st.number_input("Digite o Grupo que saiu:", min_value=1, max_value=25, value=1)
        
        with col_action:
            st.write("") # Espaço
            st.write("") 
            if st.button("💾 Salvar na Planilha", type="primary"):
                with st.spinner("Salvando..."):
                    if salvar_na_nuvem(aba_ativa, novo_bicho):
                        st.success("Sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar.")

        # Botão de correção discreto
        with st.expander("Opções de Correção"):
            if st.button("🗑️ Apagar Último Registro"):
                if deletar_ultimo_registro(aba_ativa):
                    st.success("Apagado.")
                    st.rerun()
    else:
        st.warning("A planilha parece estar vazia.")
