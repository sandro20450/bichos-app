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
st.set_page_config(page_title="LOTECA V17 - Crise", page_icon="💲", layout="centered")

URLS_BANCAS = {
    "LOTEP": "https://www.resultadofacil.com.br/resultados-lotep-de-hoje",
    "CAMINHODASORTE": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-de-hoje",
    "MONTECAI": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-de-hoje"
}

BANCA_OPCOES = ["LOTEP", "CAMINHODASORTE", "MONTECAI"]

# =============================================================================
# --- 2. CONEXÃO E BANCO DE DADOS ---
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
# --- 3. MONITORAMENTO ---
# =============================================================================
def verificar_atualizacao_site(url):
    if not url: return False, "Link não configurado", ""
    try:
        fuso_br = pytz.timezone('America/Sao_Paulo')
        hoje = datetime.now(fuso_br)
        datas_possiveis = [hoje.strftime("%d/%m/%Y"), hoje.strftime("%d-%m-%Y"), hoje.strftime("%d de")]
        
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

# =============================================================================
# --- 4. MOTOR MATEMÁTICO (CRÍTICO E NORMAL) ---
# =============================================================================

def calcular_ranking_forca_completo(historico):
    """Retorna TODOS os 25 bichos ordenados por força (frequência ponderada)"""
    if not historico: return []
    hist_reverso = historico[::-1]
    scores = {g: 0 for g in range(1, 26)}
    
    # Pesos
    c_curto = Counter(hist_reverso[:10])
    for g, f in c_curto.items(): scores[g] += (f * 2.0)
    c_medio = Counter(hist_reverso[:50])
    for g, f in c_medio.items(): scores[g] += (f * 1.0)
    
    rank = sorted(scores.items(), key=lambda x: -x[1])
    return [g for g, s in rank] # Retorna lista completa ordenada

def calcular_ranking_atraso_completo(historico):
    """Retorna TODOS os 25 bichos ordenados por atraso (do maior para o menor)"""
    if not historico: return []
    atrasos = {}
    total = len(historico)
    for b in range(1, 26):
        indices = [i for i, x in enumerate(historico) if x == b]
        val = total - 1 - indices[-1] if indices else total
        atrasos[b] = val
    
    rank = sorted(atrasos.items(), key=lambda x: -x[1])
    return [g for g, s in rank] # Retorna lista completa ordenada

def gerar_palpite_estrategico(historico, modo_crise=False):
    """
    Define a estratégia baseada no estado atual:
    - NORMAL: Top 12 Força + 2 Cobertura (Força).
    - CRISE: 8 Top Força + 4 Top Atraso (que não estejam na força).
    """
    todos_forca = calcular_ranking_forca_completo(historico)
    
    if modo_crise:
        # ESTRATÉGIA DE CRISE (8 Quentes + 4 Atrasados)
        top8_quentes = todos_forca[:8]
        
        todos_atrasos = calcular_ranking_atraso_completo(historico)
        top4_atrasados_unicos = []
        
        for bicho in todos_atrasos:
            if bicho not in top8_quentes:
                top4_atrasados_unicos.append(bicho)
            if len(top4_atrasados_unicos) == 4:
                break
        
        # Junta tudo numa lista única de 12
        lista_final = top8_quentes + top4_atrasados_unicos
        return lista_final, [] # Retorna lista vazia na cobertura pois não tem
        
    else:
        # ESTRATÉGIA NORMAL (12 Força + 2 Cobertura)
        top12 = todos_forca[:12]
        cob2 = todos_forca[12:14]
        return top12, cob2

def verificar_status_crise(df_backtest):
    """Detecta se há 2 derrotas seguidas nas últimas jogadas"""
    derrotas = 0
    if not df_backtest.empty:
        for status in df_backtest['STATUS']:
            if "❌" in status:
                derrotas += 1
            else:
                break # Interrompe se achou vitória
    return derrotas >= 2

def gerar_backtest(historico):
    resultados = []
    if len(historico) < 15: return pd.DataFrame()
    
    # Analisa 5 jogos passados
    for i in range(5):
        idx = len(historico) - 1 - i
        saiu = historico[idx]
        hist_passado = historico[:idx]
        
        # Para o backtest ser honesto, precisamos saber se NAQUELA ÉPOCA
        # estaríamos em crise ou não.
        # Isso cria uma recursividade complexa. 
        # Para simplificar e deixar rápido: O Backtest usa a regra NORMAL (V15)
        # apenas para dizer se ganhou ou perdeu na tendência padrão.
        
        ranking_na_epoca = calcular_ranking_forca_completo(hist_passado)
        palpite_padrao = ranking_na_epoca[:14] # Top 14 padrão
        
        status = "❌"
        if saiu in palpite_padrao:
            status = "💚 VITÓRIA"
            
        resultados.append({"JOGO": f"Recente #{i+1}", "SAIU": f"{saiu:02}", "STATUS": status})
        
    return pd.DataFrame(resultados)

# =============================================================================
# --- 5. INTERFACE DO APLICATIVO ---
# =============================================================================
st.title("🦅 Titanium V17 - Auto Crise")
st.caption("Sistema Inteligente de Gestão de Risco")

banca_selecionada = st.selectbox("Selecione a Banca:", BANCA_OPCOES)
aba_ativa = conectar_planilha(banca_selecionada)

if aba_ativa:
    historico = carregar_dados(aba_ativa)
    
    # Monitor
    st.markdown("---")
    link = URLS_BANCAS.get(banca_selecionada)
    online, tit, det = verificar_atualizacao_site(link)
    c_m1, c_m2 = st.columns([3,1])
    with c_m1:
        if online: st.success(tit)
        else: st.warning(tit)
    with c_m2:
        if link: st.link_button("🔗 SITE", link)

    tab1, tab2 = st.tabs(["🏠 Palpites", "📈 Gráficos"])

    with tab1:
        if len(historico) > 0:
            ultimo = historico[-1]
            st.info(f"Último Resultado: **Grupo {ultimo:02}**")
            
            # 1. Gera Backtest e Verifica Crise
            df_back = gerar_backtest(historico)
            EM_CRISE = verificar_status_crise(df_back)
            
            # 2. Gera Palpite baseado no Status
            palpite_princ, palpite_cob = gerar_palpite_estrategico(historico, modo_crise=EM_CRISE)
            
            # 3. Exibição Condicional
            if EM_CRISE:
                st.error("🚨 MODO CRISE ATIVADO: 2 Derrotas Detectadas!")
                st.markdown("⚠️ **Estratégia Alterada:** Jogando com 8 Quentes + 4 Atrasados.")
                st.markdown("### 🛡️ Lista de Recuperação (12 Grupos)")
                # Mostra lista única de 12
                st.code(", ".join([f"{n:02}" for n in palpite_princ]))
                
            else:
                st.success("✅ MODO NORMAL: Tendência Estável")
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown("### 🔥 Top 12 (Normal)")
                    st.write(", ".join([f"**{n:02}**" for n in palpite_princ]))
                with c2:
                    st.markdown("### ❄️ Cob (2)")
                    st.write(", ".join([f"{n:02}" for n in palpite_cob]))

            # Backtest
            with st.expander("📊 Ver Histórico"):
                if not df_back.empty: st.table(df_back)

            st.markdown("---")
            st.write("### 📝 Inserir Novo Resultado")
            ci, ca = st.columns([1,1])
            with ci: novo = st.number_input("Grupo:", 1, 25, 1)
            with ca:
                st.write("")
                st.write("")
                if st.button("💾 Salvar", type="primary"):
                    if salvar_na_nuvem(aba_ativa, novo):
                        st.success("Salvo!")
                        st.rerun()
                    else: st.error("Erro")
            
            with st.expander("Correção"):
                if st.button("🗑️ Apagar Último"):
                    deletar_ultimo_registro(aba_ativa)
                    st.rerun()
        else:
            st.warning("Sem dados.")

    with tab2:
        if len(historico) > 0:
            st.write("### 🐢 Atrasômetro")
            # Recalcula para exibir gráfico
            todos_atrasos = calcular_ranking_atraso_completo(historico)
            atrasos_dict = {}
            total = len(historico)
            for b in todos_atrasos[:10]:
                indices = [i for i, x in enumerate(historico) if x == b]
                val = total - 1 - indices[-1] if indices else total
                atrasos_dict[f"Gr {b:02}"] = val
            st.bar_chart(pd.DataFrame.from_dict(atrasos_dict, orient='index', columns=['Jogos']))
        else:
            st.info("Sem dados.")

