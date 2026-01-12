import streamlit as st
import pandas as pd
from collections import Counter
import gspread
from google.oauth2.service_account import Credentials

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS E CONEXÃO ---
# =============================================================================
st.set_page_config(page_title="Titanium V11 - Loterias", page_icon="🦅")

# Nomes exatos das abas que estão na planilha
BANCA_OPCOES = ["LOTEP", "CAMINHODASORTE", "MONTECAI"]

def conectar_planilha(nome_aba):
    """Conecta na planilha e seleciona a aba escolhida"""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
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
    else:
        st.warning("⚠️ Configure as Secrets do Streamlit.")
        return None

def carregar_dados(worksheet):
    if worksheet:
        valores = worksheet.col_values(1)
        dados_limpos = []
        for v in valores:
            if v.isdigit():
                dados_limpos.append(int(v))
        return dados_limpos
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
    """Apaga a última linha preenchida da planilha"""
    if worksheet:
        try:
            # Pega todos os valores da coluna A para saber quantas linhas tem
            valores = worksheet.col_values(1)
            total_linhas = len(valores)
            if total_linhas > 0:
                worksheet.delete_rows(total_linhas)
                return True
        except Exception as e:
            st.error(f"Erro ao deletar: {e}")
            return False
    return False

# =============================================================================
# --- 2. MOTOR MATEMÁTICO: TITANIUM V11.1 (RANKING DE FORÇA) ---
# =============================================================================
def calcular_ranking_forca(historico):
    """
    Retorna os 14 grupos ordenados do MAIS FORTE para o MAIS FRACO.
    Lógica: Inverte o histórico para análise (Recentes têm peso maior).
    """
    if not historico:
        return []

    # Inverte para que o índice 0 seja o jogo mais recente para o algoritmo
    hist_reverso = historico[::-1] 
    
    curto_prazo = hist_reverso[:10]
    medio_prazo = hist_reverso[:50]

    scores = {g: 0 for g in range(1, 26)}

    # Pesos
    c_curto = Counter(curto_prazo)
    for g, freq in c_curto.items():
        scores[g] += (freq * 2.0) # Peso Ouro

    c_medio = Counter(medio_prazo)
    for g, freq in c_medio.items():
        scores[g] += (freq * 1.0) # Peso Prata

    # ORDENAÇÃO: Do maior score para o menor (Ranking de Força)
    rank = sorted(scores.items(), key=lambda x: -x[1])
    
    # Pega apenas os números (Grupos) dos Top 14
    top_14_ordenados = [g for g, s in rank[:14]]
    
    return top_14_ordenados

# =============================================================================
# --- 3. LÓGICA DO BACKTEST (TESTE DE PASSADO) ---
# =============================================================================
def gerar_backtest(historico):
    """Analisa os últimos 5 jogos e verifica se teríamos ganho"""
    resultados = []
    
    # Analisa os últimos 5 jogos
    # (Loop de 1 a 5, andando para trás no histórico)
    qtd_analise = 5
    if len(historico) < 15: # Precisa de um mínimo de histórico
        return pd.DataFrame()

    for i in range(qtd_analise):
        # O índice real na lista (do fim para o começo)
        indice_real = len(historico) - 1 - i
        
        grupo_que_saiu = historico[indice_real]
        
        # O passado é tudo que veio ANTES desse jogo
        hist_passado = historico[:indice_real]
        
        # Gera a previsão que teríamos feito naquele dia
        previsao_na_epoca = calcular_ranking_forca(hist_passado)
        
        status = "❌"
        if grupo_que_saiu in previsao_na_epoca:
            status = "💚 VITÓRIA"
        
        resultados.append({
            "JOGO": f"Recente #{i+1}",
            "SAIU": f"{grupo_que_saiu:02}",
            "STATUS": status
        })
    
    return pd.DataFrame(resultados)

# =============================================================================
# --- 4. INTERFACE DO APLICATIVO (FRONT-END) ---
# =============================================================================
st.title("🦅 Titanium V11.1")
st.caption("Ranking de Força & Inteligência Estatística")

# --- SELEÇÃO DE BANCA ---
banca_selecionada = st.selectbox("Selecione a Banca:", BANCA_OPCOES)
aba_ativa = conectar_planilha(banca_selecionada)

if aba_ativa:
    historico = carregar_dados(aba_ativa)
    
    if len(historico) > 0:
        ultimo = historico[-1]
        st.markdown(f"**Último Resultado na Planilha:** `{ultimo:02}`")
        st.markdown("---")

        # --- ÁREA 1: BACKTEST (VALIDAÇÃO) ---
        st.subheader("📊 Backtest (Últimos 5 Jogos)")
        df_backtest = gerar_backtest(historico)
        if not df_backtest.empty:
            st.table(df_backtest) # Tabela estática limpa
        else:
            st.info("Histórico insuficiente para backtest.")

        # --- ÁREA 2: PREVISÃO PODEROSA ---
        st.markdown("---")
        st.subheader(f"🎯 Palpite para {banca_selecionada}")
        
        palpite_ordenado = calcular_ranking_forca(historico)
        
        # Separação: Top 10 (Fogo) e Cobertura (Gelo)
        top_10 = palpite_ordenado[:10]
        cobertura = palpite_ordenado[10:]
        
        # Exibição Visual
        st.markdown("### 🔥 Top 10 Mais Fortes (Prioridade)")
        st.info(", ".join([f"{n:02}" for n in top_10]))
        
        st.markdown("### ❄️ 4 de Cobertura (Segurança)")
        st.warning(", ".join([f"{n:02}" for n in cobertura]))
        
        st.markdown("---")

        # --- ÁREA 3: CONTROLES (SALVAR / CORRIGIR) ---
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### 💾 Novo Resultado")
            novo_bicho = st.number_input("Digitar Grupo:", min_value=1, max_value=25, value=1)
            if st.button("Salvar na Nuvem", type="primary"):
                with st.spinner("Salvando..."):
                    if salvar_na_nuvem(aba_ativa, novo_bicho):
                        st.success("Salvo!")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar.")

        with col2:
            st.write("### ⚠️ Correção")
            with st.expander("Abra para corrigir"):
                st.write("Se digitou errado, clique abaixo para apagar o último registro da planilha.")
                if st.button("🗑️ Apagar Último"):
                    with st.spinner("Apagando..."):
                        if deletar_ultimo_registro(aba_ativa):
                            st.success("Último registro apagado!")
                            st.rerun()
                        else:
                            st.error("Erro ao apagar.")

    else:
        st.warning("A planilha parece estar vazia.")
else:
    st.info("Conectando ao banco de dados...")

