import streamlit as st
import pandas as pd
from collections import Counter
import gspread
from google.oauth2.service_account import Credentials

# =============================================================================
# --- 1. CONFIGURAÇÕES INICIAIS ---
# =============================================================================
st.set_page_config(page_title="Central de Análises", page_icon="🦅")

# Nomes exatos das abas que estão na sua planilha do Google
# Se na planilha estiver diferente (ex: "MONTECARLO"), altere aqui dentro das aspas.
BANCA_OPCOES = ["TRADICIONAL", "CAMINHODASORTE", "MONTECAI"]

# =============================================================================
# --- 2. CONEXÃO COM O GOOGLE SHEETS ---
# =============================================================================
def conectar_planilha(nome_aba):
    """Conecta na planilha e seleciona a aba escolhida"""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Tenta ler as credenciais secretas do Streamlit Cloud
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        
        try:
            # Tenta abrir a planilha principal
            sh = gc.open("CentralBichos") 
            # Seleciona a aba específica
            worksheet = sh.worksheet(nome_aba)
            return worksheet
        except Exception as e:
            st.error(f"Erro ao abrir a aba '{nome_aba}'. Verifique se o nome está idêntico na planilha.")
            st.error(f"Detalhe do erro: {e}")
            return None
    else:
        st.warning("⚠️ As chaves de segurança (Secrets) não foram configuradas ainda.")
        return None

def carregar_dados(worksheet):
    """Lê todos os números da coluna A"""
    if worksheet:
        # Pega todos os valores da primeira coluna
        valores = worksheet.col_values(1)
        dados_limpos = []
        for v in valores:
            if v.isdigit(): # Garante que é número
                dados_limpos.append(int(v))
        return dados_limpos
    return []

def salvar_na_nuvem(worksheet, numero):
    """Escreve o novo número na última linha vazia"""
    if worksheet:
        try:
            worksheet.append_row([int(numero)])
            return True
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
            return False
    return False

# =============================================================================
# --- 3. A LÓGICA MATEMÁTICA (MONTE CARLOS V11) ---
# =============================================================================
def calcular_previsao(historico):
    if not historico:
        return []

    # Como sua planilha tem o MAIS RECENTE no FINAL (lá embaixo),
    # precisamos inverter a lista para a matemática funcionar (queremos o recente primeiro)
    hist_reverso = historico[::-1] 
    
    # Pega os últimos 10 (que agora são os primeiros da lista invertida)
    curto_prazo = hist_reverso[:10]
    medio_prazo = hist_reverso[:50]

    scores = {g: 0 for g in range(1, 26)}

    # Aplica os pesos
    c_curto = Counter(curto_prazo)
    for g, freq in c_curto.items():
        scores[g] += (freq * 2.0)

    c_medio = Counter(medio_prazo)
    for g, freq in c_medio.items():
        scores[g] += (freq * 1.0)

    # Ordena os melhores
    rank = sorted(scores.items(), key=lambda x: -x[1])
    top_14 = [g for g, s in rank[:14]]
    
    return sorted(top_14)

# =============================================================================
# --- 4. A TELA DO APLICATIVO (FRONT-END) ---
# =============================================================================
st.title("🦅 App Análise de Loterias")

# --- MENU LATERAL ---
st.sidebar.header("Escolha a Banca")
banca_selecionada = st.sidebar.selectbox("Banca:", BANCA_OPCOES)

st.sidebar.markdown("---")

# --- LÓGICA PRINCIPAL ---
aba_ativa = conectar_planilha(banca_selecionada)

if aba_ativa:
    # 1. Carrega os dados
    historico = carregar_dados(aba_ativa)
    
    if len(historico) > 0:
        ultimo_sorteio = historico[-1] # Pega o último da lista
        st.info(f"📊 Banca **{banca_selecionada}** carregada com **{len(historico)}** jogos.")
        st.markdown(f"**Último resultado registrado:** Grupo `{ultimo_sorteio:02}`")

        # 2. Formulário para adicionar novo
        st.sidebar.subheader("Novo Resultado")
        novo_bicho = st.sidebar.number_input(f"O que deu na {banca_selecionada}?", min_value=1, max_value=25, value=1)
        
        if st.sidebar.button("💾 Salvar Resultado"):
            with st.spinner("Enviando para o Google Sheets..."):
                sucesso = salvar_na_nuvem(aba_ativa, novo_bicho)
                if sucesso:
                    st.success("✅ Atualizado com sucesso!")
                    st.rerun() # Atualiza a tela

        # 3. Mostra a Previsão
        st.divider()
        st.subheader(f"🎯 Palpite para {banca_selecionada}")
        
        palpite = calcular_previsao(historico)
        
        # Formatação bonita dos números
        lista_visual = [f"{n:02}" for n in palpite]
        st.success(f"👉 **JOGAR NESTES:** {', '.join(lista_visual)}")
        
        # Cartões visuais
        colunas = st.columns(7)
        for i, numero in enumerate(palpite):
            if i < 7:
                colunas[i].metric("Grupo", f"{numero:02}")
            # Se quiser mostrar a segunda linha de palpites, descomente abaixo
            # elif i < 14:
            #     colunas[i-7].metric("Grupo", f"{numero:02}")

    else:
        st.warning("A aba parece vazia ou não consegui ler os números.")
else:
    st.info("👆 Configure as chaves no Streamlit Cloud para conectar.")