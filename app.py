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
st.set_page_config(page_title="BICHOS da LOTECA", page_icon="🦅", layout="centered")

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
# --- 4. MOTOR MATEMÁTICO & DNA DA BANCA (NOVIDADE) ---
# =============================================================================

def calcular_ranking_forca_completo(historico):
    if not historico: return []
    hist_reverso = historico[::-1]
    scores = {g: 0 for g in range(1, 26)}
    
    c_curto = Counter(hist_reverso[:10])
    for g, f in c_curto.items(): scores[g] += (f * 2.0)
    c_medio = Counter(hist_reverso[:50])
    for g, f in c_medio.items(): scores[g] += (f * 1.0)
    
    rank = sorted(scores.items(), key=lambda x: -x[1])
    return [g for g, s in rank]

def calcular_ranking_atraso_completo(historico):
    if not historico: return []
    atrasos = {}
    total = len(historico)
    for b in range(1, 26):
        indices = [i for i, x in enumerate(historico) if x == b]
        val = total - 1 - indices[-1] if indices else total
        atrasos[b] = val
    rank = sorted(atrasos.items(), key=lambda x: -x[1])
    return [g for g, s in rank]

def analisar_dna_banca(historico):
    """
    Analisa os últimos 20 jogos para determinar a 'Personalidade' da banca.
    Retorna:
    - Score de Obediência (0-100%): Quanto ela respeita os Top 12.
    - Tipo de Comportamento: 'Normal', 'Viciada (Repete)' ou 'Caótica (Zebra)'.
    """
    if len(historico) < 30: return 0, "Dados Insuficientes"
    
    acertos_top12 = 0
    analise_qtd = 20
    
    for i in range(analise_qtd):
        idx = len(historico) - 1 - i
        saiu = historico[idx]
        passado = historico[:idx]
        
        # Gera o Top 12 daquela época
        ranking = calcular_ranking_forca_completo(passado)
        top12 = ranking[:12]
        
        if saiu in top12:
            acertos_top12 += 1
            
    score = (acertos_top12 / analise_qtd) * 100
    
    # Define personalidade
    if score >= 65:
        personalidade = "🎯 Disciplinada (Respeita Lógica)"
    elif score >= 45:
        personalidade = "⚖️ Equilibrada"
    else:
        personalidade = "🎲 Caótica (Muitas Zebras)"
        
    return score, personalidade

def gerar_palpite_estrategico(historico, modo_crise=False):
    todos_forca = calcular_ranking_forca_completo(historico)
    
    if modo_crise:
        top8_quentes = todos_forca[:8]
        todos_atrasos = calcular_ranking_atraso_completo(historico)
        top4_atrasados_unicos = []
        for bicho in todos_atrasos:
            if bicho not in top8_quentes:
                top4_atrasados_unicos.append(bicho)
            if len(top4_atrasados_unicos) == 4:
                break
        return top8_quentes + top4_atrasados_unicos, [] 
    else:
        return todos_forca[:12], todos_forca[12:14]

def gerar_backtest_e_status(historico):
    if len(historico) < 25: return pd.DataFrame(), False
    
    derrotas_consecutivas = 0
    resultados_simulados = []
    inicio_simulacao = len(historico) - 20
    if inicio_simulacao < 0: inicio_simulacao = 0
    
    for i in range(inicio_simulacao, len(historico)):
        saiu_real = historico[i]
        hist_passado = historico[:i]
        
        modo_crise_ativo = derrotas_consecutivas >= 2
        palpite_p, palpite_c = gerar_palpite_estrategico(hist_passado, modo_crise=modo_crise_ativo)
        
        status = "❌"
        if saiu_real in (palpite_p + palpite_c):
            status = "💚 VITÓRIA"
            derrotas_consecutivas = 0
        else:
            derrotas_consecutivas += 1
            
        if i >= len(historico) - 5:
            resultados_simulados.append({
                "JOGO": f"Recente #{len(historico) - i}",
                "SAIU": f"{saiu_real:02}",
                "STATUS": status
            })
    
    return pd.DataFrame(resultados_simulados[::-1]), derrotas_consecutivas >= 2

# =============================================================================
# --- 5. INTERFACE DO APLICATIVO ---
# =============================================================================
st.title("🦅 BICHOS da LOTECA")
st.caption("Sistema V19 - Diagnóstico de DNA")

banca_selecionada = st.selectbox("Selecione a Banca:", BANCA_OPCOES)
aba_ativa = conectar_planilha(banca_selecionada)

if aba_ativa:
    historico = carregar_dados(aba_ativa)
    
    # --- MONITOR DE SITE ---
    st.markdown("---")
    link = URLS_BANCAS.get(banca_selecionada)
    online, tit, det = verificar_atualizacao_site(link)
    c_m1, c_m2 = st.columns([3,1])
    with c_m1:
        if online: st.success(tit)
        else: st.warning(tit)
    with c_m2:
        if link: st.link_button("🔗 SITE", link)

    tab1, tab2 = st.tabs(["🏠 Diagnóstico & Jogo", "📈 Gráficos"])

    with tab1:
        if len(historico) > 0:
            ultimo = historico[-1]
            
            # --- 🔍 DIAGNÓSTICO DE DNA (NOVIDADE) ---
            score_dna, personalidade = analisar_dna_banca(historico)
            
            st.markdown("### 🧬 DNA da Banca (Últimos 20 Jogos)")
            col_dna1, col_dna2, col_dna3 = st.columns([1, 2, 1])
            
            # Cor do Score
            cor_score = "off"
            if score_dna >= 60: cor_score = "normal" # verde
            elif score_dna >= 40: cor_score = "off" # cinza/amarelo
            else: cor_score = "inverse" # vermelho (usando delta_color logic mental)

            col_dna1.metric("Obediência", f"{int(score_dna)}%")
            col_dna2.info(f"**Status:** {personalidade}")
            col_dna3.metric("Último", f"{ultimo:02}")
            
            if score_dna < 40:
                st.error("⚠️ CUIDADO: Esta banca está muito instável hoje!")
            elif score_dna > 75:
                st.balloons() # Um mimo visual se a banca estiver ótima
                st.success("💎 MOMENTO DE OURO: A banca está respeitando muito a lógica!")
            
            st.markdown("---")
            # ----------------------------------------

            # Lógica Normal V18
            df_back, EM_CRISE = gerar_backtest_e_status(historico)
            palpite_princ, palpite_cob = gerar_palpite_estrategico(historico, modo_crise=EM_CRISE)
            
            if EM_CRISE:
                st.error("🚨 MODO CRISE ATIVADO (Derrotas Recentes)")
                st.markdown("### 🛡️ Lista de Recuperação (12 Grupos)")
                st.code(", ".join([f"{n:02}" for n in palpite_princ]))
            else:
                st.success("✅ MODO NORMAL (Estratégia Padrão)")
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown("### 🔥 Top 12")
                    st.write(", ".join([f"**{n:02}**" for n in palpite_princ]))
                with c2:
                    st.markdown("### ❄️ Cob (2)")
                    st.write(", ".join([f"{n:02}" for n in palpite_cob]))

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
