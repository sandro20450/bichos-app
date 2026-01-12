import streamlit as st
import pandas as pd
from collections import Counter
import gspread
from google.oauth2.service_account import Credentials
import requests
from datetime import datetime
import pytz

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS (CSS PRO) ---
# =============================================================================
st.set_page_config(page_title="BICHOS da LOTECA", page_icon="🦅", layout="wide")

# CSS para deixar o visual com cara de aplicativo nativo
st.markdown("""
<style>
    /* Estilo das Bolas de Loteria */
    .bola-verde {
        display: inline-block;
        width: 40px;
        height: 40px;
        line-height: 40px;
        border-radius: 50%;
        background-color: #28a745;
        color: white;
        text-align: center;
        font-weight: bold;
        margin: 3px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
    }
    .bola-azul {
        display: inline-block;
        width: 40px;
        height: 40px;
        line-height: 40px;
        border-radius: 50%;
        background-color: #17a2b8;
        color: white;
        text-align: center;
        font-weight: bold;
        margin: 3px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
    }
    .bola-vermelha {
        display: inline-block;
        width: 40px;
        height: 40px;
        line-height: 40px;
        border-radius: 50%;
        background-color: #dc3545;
        color: white;
        text-align: center;
        font-weight: bold;
        margin: 3px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
    }
    /* Cards do Topo */
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #d0d0d0;
    }
</style>
""", unsafe_allow_html=True)

URLS_BANCAS = {
    "LOTEP": "https://www.resultadofacil.com.br/resultados-lotep-de-hoje",
    "CAMINHODASORTE": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-de-hoje",
    "MONTECAI": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-de-hoje"
}

BANCA_OPCOES = ["LOTEP", "CAMINHODASORTE", "MONTECAI"]

# =============================================================================
# --- 2. FUNÇÕES DE BANCO DE DADOS ---
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
            st.sidebar.error(f"Erro planilha: {e}")
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
        except: return False
    return False

def deletar_ultimo_registro(worksheet):
    if worksheet:
        try:
            valores = worksheet.col_values(1)
            total_linhas = len(valores)
            if total_linhas > 0:
                worksheet.delete_rows(total_linhas)
                return True
        except: return False
    return False

# =============================================================================
# --- 3. FUNÇÕES MATEMÁTICAS & VISUAIS ---
# =============================================================================
def html_bolas(lista, cor="verde"):
    """Gera o HTML das bolas coloridas"""
    html = "<div>"
    classe = f"bola-{cor}"
    for n in lista:
        html += f"<div class='{classe}'>{n:02}</div>"
    html += "</div>"
    return html

def verificar_atualizacao_site(url):
    if not url: return False, "Sem Link", ""
    try:
        fuso_br = pytz.timezone('America/Sao_Paulo')
        hoje = datetime.now(fuso_br)
        datas = [hoje.strftime("%d/%m/%Y"), hoje.strftime("%d-%m-%Y"), hoje.strftime("%d de")]
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            for d in datas:
                if d in r.text: return True, "🟢 ATUALIZADO", f"Data: {d}"
            return False, "🟡 SEM DATA", "Site online, sem data de hoje."
        return False, "🔴 OFF", "Erro site."
    except: return False, "🔴 ERRO", "Falha conexão."

# --- LÓGICA V20 (CICLO 25) ---
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
    if len(historico) < 35: return 0, "Calibrando..."
    acertos = 0
    analise = 25
    for i in range(analise):
        idx = len(historico) - 1 - i
        saiu = historico[idx]
        passado = historico[:idx]
        ranking = calcular_ranking_forca_completo(passado)[:12]
        if saiu in ranking: acertos += 1
    score = (acertos / analise) * 100
    if score >= 65: status = "🎯 DISCIPLINADA"
    elif score >= 45: status = "⚖️ EQUILIBRADA"
    else: status = "🎲 CAÓTICA"
    return score, status

def gerar_palpite_estrategico(historico, modo_crise=False):
    todos_forca = calcular_ranking_forca_completo(historico)
    if modo_crise:
        top8 = todos_forca[:8]
        todos_atrasos = calcular_ranking_atraso_completo(historico)
        top4_atraso = []
        for b in todos_atrasos:
            if b not in top8:
                top4_atraso.append(b)
            if len(top4_atraso) == 4: break
        return top8 + top4_atraso, []
    else:
        return todos_forca[:12], todos_forca[12:14]

def gerar_backtest_e_status(historico):
    if len(historico) < 30: return pd.DataFrame(), False
    derrotas = 0
    resultados = []
    inicio = max(0, len(historico) - 25)
    
    for i in range(inicio, len(historico)):
        saiu = historico[i]
        passado = historico[:i]
        crise = derrotas >= 2
        p_princ, p_cob = gerar_palpite_estrategico(passado, crise)
        
        status = "❌"
        if saiu in (p_princ + p_cob):
            status = "💚"
            derrotas = 0
        else:
            derrotas += 1
            
        if i >= len(historico) - 5:
            resultados.append({"JOGO": f"#{len(historico)-i}", "SAIU": f"{saiu:02}", "RES": status})
            
    return pd.DataFrame(resultados[::-1]), derrotas >= 2

# =============================================================================
# --- 4. INTERFACE PRINCIPAL (DASHBOARD) ---
# =============================================================================
# BARRA LATERAL (CONTROLES)
with st.sidebar:
    st.header("🦅 MENU DE COMANDO")
    banca_selecionada = st.selectbox("Escolha a Banca:", BANCA_OPCOES)
    
    st.markdown("---")
    st.write("📝 **Novo Resultado**")
    novo_bicho = st.number_input("Grupo:", 1, 25, 1)
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 SALVAR", type="primary"):
            aba = conectar_planilha(banca_selecionada)
            if aba and salvar_na_nuvem(aba, novo_bicho):
                st.toast("Salvo com sucesso!", icon="✅")
                st.rerun()
    with col_btn2:
        if st.button("🔄 REBOOT"):
            st.rerun()

    with st.expander("🗑️ Área de Perigo"):
        st.write("Apagar o último registro:")
        if st.button("CONFIRMAR EXCLUSÃO"):
            aba = conectar_planilha(banca_selecionada)
            if aba and deletar_ultimo_registro(aba):
                st.toast("Apagado!", icon="🗑️")
                st.rerun()

# TELA PRINCIPAL
st.title("🦅 BICHOS da LOTECA")
aba_ativa = conectar_planilha(banca_selecionada)

if aba_ativa:
    historico = carregar_dados(aba_ativa)
    
    if len(historico) > 0:
        # --- CABEÇALHO (PLACAR) ---
        score, status_dna = analisar_dna_banca(historico)
        ultimo = historico[-1]
        link = URLS_BANCAS.get(banca_selecionada)
        site_on, site_tit, _ = verificar_atualizacao_site(link)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Obediência", f"{int(score)}%")
        c2.metric("Status DNA", "Caótico" if score < 40 else "Disciplinado")
        c3.metric("Último Saiu", f"{ultimo:02}")
        with c4:
            st.write(f"Monitor: {site_tit}")
            if link: st.link_button("🔗 Abrir Site", link)

        st.markdown("---")
        
        # --- LÓGICA ---
        df_back, EM_CRISE = gerar_backtest_e_status(historico)
        palpite_p, palpite_c = gerar_palpite_estrategico(historico, EM_CRISE)
        
        # --- VISUALIZAÇÃO DOS PALPITES ---
        if EM_CRISE:
            st.error("🚨 MODO CRISE ATIVADO: Jogando RECUPERAÇÃO (Quentes + Atrasados)")
            
            st.markdown("### 🛡️ LISTA DE RECUPERAÇÃO (12)")
            # Bolas Vermelhas
            st.markdown(html_bolas(palpite_p, "vermelha"), unsafe_allow_html=True)
            
            # Botão de Copiar
            lista_str = ", ".join([f"{n:02}" for n in palpite_p])
            st.caption("📋 Copiar Lista:")
            st.code(lista_str, language="text")
            
        else:
            col_princ, col_cob = st.columns([2, 1])
            
            with col_princ:
                st.success("🔥 PALPITE PRINCIPAL (TOP 12)")
                # Bolas Verdes
                st.markdown(html_bolas(palpite_p, "verde"), unsafe_allow_html=True)
                
                # Copiar
                lista_str = ", ".join([f"{n:02}" for n in palpite_p])
                st.code(lista_str, language="text")
                
            with col_cob:
                st.info("❄️ COBERTURA (2)")
                # Bolas Azuis
                st.markdown(html_bolas(palpite_c, "azul"), unsafe_allow_html=True)
                
                # Copiar
                lista_cob_str = ", ".join([f"{n:02}" for n in palpite_c])
                st.code(lista_cob_str, language="text")

        # --- BACKTEST ---
        with st.expander("📊 Ver Histórico de Acertos"):
            if not df_back.empty: st.table(df_back)

    else:
        st.warning("⚠️ Planilha vazia. Adicione dados pela barra lateral.")

else:
    st.info("Conectando ao banco de dados...")
