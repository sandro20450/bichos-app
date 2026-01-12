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
st.set_page_config(page_title="Titanium V15 - Top 12", page_icon="🦅", layout="centered")

# 🔗 SEUS LINKS DE MONITORAMENTO
URLS_BANCAS = {
    "LOTEP": "https://www.resultadofacil.com.br/resultados-lotep-de-hoje",
    "CAMINHODASORTE": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-de-hoje",
    "MONTECAI": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-de-hoje"
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
# --- 3. FUNÇÕES DE MONITORAMENTO E ESTATÍSTICA ---
# =============================================================================
def verificar_atualizacao_site(url):
    """Verifica se a data de hoje consta no site"""
    if not url: return False, "Link não configurado", ""
    try:
        fuso_br = pytz.timezone('America/Sao_Paulo')
        hoje = datetime.now(fuso_br)
        datas_possiveis = [
            hoje.strftime("%d/%m/%Y"),
            hoje.strftime("%d-%m-%Y"),
            hoje.strftime("%d de")
        ]
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        resposta = requests.get(url, headers=headers, timeout=5)
        
        if resposta.status_code == 200:
            texto = resposta.text
            for data in datas_possiveis:
                if data in texto:
                    return True, "🟢 SITE ATUALIZADO HOJE!", f"Data encontrada: {data}"
            return False, "🟡 Data de hoje não encontrada", "O site está online, mas sem a data de hoje."
        else:
            return False, "🔴 Site Fora do Ar", f"Erro: {resposta.status_code}"
    except Exception as e:
        return False, "🔴 Erro de Conexão", f"Detalhe: {e}"

def calcular_atrasos(historico):
    """Calcula há quantos jogos cada bicho não sai"""
    atrasos = {}
    total_jogos = len(historico)
    
    for bicho in range(1, 26):
        try:
            indices = [i for i, x in enumerate(historico) if x == bicho]
            if indices:
                ultimo_indice = indices[-1]
                atraso = total_jogos - 1 - ultimo_indice
                atrasos[bicho] = atraso
            else:
                atrasos[bicho] = total_jogos
        except:
            atrasos[bicho] = 0
            
    rank_atraso = sorted(atrasos.items(), key=lambda x: -x[1])
    return rank_atraso

# =============================================================================
# --- 4. MOTOR TITANIUM V11.1 ---
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
st.title("🦅 Titanium V15 Top 12")
st.caption("Estratégia: 12 Fortes + 2 Cobertura")

# Seleção de Banca
banca_selecionada = st.selectbox("Selecione a Banca:", BANCA_OPCOES)
aba_ativa = conectar_planilha(banca_selecionada)

if aba_ativa:
    historico = carregar_dados(aba_ativa)
    
    # --- ÁREA DE MONITORAMENTO ---
    st.markdown("---")
    link_atual = URLS_BANCAS.get(banca_selecionada)
    online, titulo, detalhe = verificar_atualizacao_site(link_atual)
    
    col_mon1, col_mon2 = st.columns([3, 1])
    with col_mon1:
        if online: st.success(f"**{titulo}**")
        else: st.warning(f"**{titulo}**")
    with col_mon2:
        if link_atual: st.link_button("🔗 VER SITE", link_atual)

    # --- ABAS DE NAVEGAÇÃO ---
    tab1, tab2 = st.tabs(["🏠 Principal", "📈 Análise Gráfica"])

    # === ABA 1: PRINCIPAL ===
    with tab1:
        if len(historico) > 0:
            ultimo = historico[-1]
            st.info(f"Último Resultado Salvo: **Grupo {ultimo:02}**")
            
            palpite = calcular_ranking_forca(historico)
            
            # --- MUDANÇA AQUI: DIVISÃO 12 / 2 ---
            c1, c2 = st.columns([2, 1]) # Coluna 1 maior para caber 12 números
            with c1:
                st.markdown("### 🔥 Top 12 (Fogo)")
                # Pega os primeiros 12
                st.write(", ".join([f"**{n:02}**" for n in palpite[:12]]))
            with c2:
                st.markdown("### ❄️ Cob (2)")
                # Pega do 12 em diante
                st.write(", ".join([f"{n:02}" for n in palpite[12:]]))

            with st.expander("📊 Ver Backtest (Últimos 5 jogos)"):
                df_back = gerar_backtest(historico)
                if not df_back.empty: st.table(df_back)

            st.markdown("---")
            st.write("### 📝 Inserir Novo Resultado")
            col_input, col_action = st.columns([1, 1])
            with col_input:
                novo_bicho = st.number_input("Digite o Grupo:", 1, 25, 1)
            with col_action:
                st.write("")
                st.write("")
                if st.button("💾 Salvar", type="primary"):
                    if salvar_na_nuvem(aba_ativa, novo_bicho):
                        st.success("Salvo!")
                        st.rerun()
                    else:
                        st.error("Erro.")

            with st.expander("Opções de Correção"):
                if st.button("🗑️ Apagar Último"):
                    deletar_ultimo_registro(aba_ativa)
                    st.rerun()
        else:
            st.warning("Planilha vazia.")

    # === ABA 2: ESTATÍSTICAS E GRÁFICOS ===
    with tab2:
        if len(historico) > 0:
            st.markdown("### 🐢 Top 4 Atrasados")
            st.caption("Há quantos jogos eles não saem?")
            
            rank_atraso = calcular_atrasos(historico)
            
            colA, colB, colC, colD = st.columns(4)
            top4 = rank_atraso[:4]
            
            colA.metric(f"Grupo {top4[0][0]:02}", f"{top4[0][1]} jogos")
            colB.metric(f"Grupo {top4[1][0]:02}", f"{top4[1][1]} jogos")
            colC.metric(f"Grupo {top4[2][0]:02}", f"{top4[2][1]} jogos")
            colD.metric(f"Grupo {top4[3][0]:02}", f"{top4[3][1]} jogos")
            
            st.markdown("---")
            st.markdown("### 📊 Frequência (Últimos 50 Jogos)")
            st.caption("Quais grupos estão saindo mais?")
            
            recentes = historico[-50:]
            contagem = Counter(recentes)
            
            df_grafico = pd.DataFrame.from_dict(contagem, orient='index', columns=['Vezes que saiu'])
            df_grafico.index.name = 'Grupo'
            
            st.bar_chart(df_grafico)
            
        else:
            st.info("Sem dados suficientes para gráficos.")

else:
    st.info("Conectando...")
