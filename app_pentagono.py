import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
import re
import math

# =============================================================================
# --- 1. CONFIGURAÇÕES E ESTILIZAÇÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono V27 - Oráculo Markov", page_icon="🎯", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #1e1e1e; color: #f0f0f0; }
    h1, h2, h3 { color: #4CAF50 !important; }
    .stButton > button { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 8px; }
    hr { border-color: #4CAF50; opacity: 0.3; }
    .markov-card { background-color: #001a00; padding: 20px; border-radius: 10px; border: 1px solid #4CAF50; }
    .alerta-markov { color: #ffb74d; font-weight: bold; font-size: 1.2em; text-align: center; margin-bottom: 15px;}
</style>
""", unsafe_allow_html=True)

BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-",
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-",
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-",
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

# =============================================================================
# --- 2. MOTORES DE EXTRAÇÃO BASE ---
# =============================================================================
def extrair_dia(banca, data_alvo):
    url = f"{BANCAS_CONFIG[banca]}{data_alvo.strftime('%Y-%m-%d')}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        tabelas = soup.find_all('table')
        resultados = []
        for tab in tabelas:
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b'])
            txt_prev = prev.get_text().upper() if prev else ""
            if "FEDERAL" in txt_prev or "FEDERAL" in tab.get_text().upper(): continue 
            nome = txt_prev.split("-")[0].strip() if prev else "Sorteio"
            
            grupos = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhar = nums[0].zfill(4) if nums and len(nums[0]) >= 3 else "----"
                    dez = int(milhar[-2:]) if milhar != "----" else 0
                    g = str(25 if dez == 0 else math.ceil(dez/4)).zfill(2) if milhar != "----" else "--"
                    grupos.append(f"{milhar} ({g})")
                    
            if len(grupos) >= 5:
                resultados.append({
                    "Data": data_alvo.strftime('%d/%m/%Y'),
                    "Sorteio": nome,
                    "1º": grupos[0], "2º": grupos[1], "3º": grupos[2], "4º": grupos[3], "5º": grupos[4]
                })
        return resultados
    except: return []

# =============================================================================
# --- 3. MENU LATERAL ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=80)
    st.header("🎯 Pentágono V27")
    menu = st.radio("Selecione a Operação:", ["📡 Máquina de Extração", "🧠 Oráculo de Padrões (Sheets)"])

# =============================================================================
# --- 4. TELA 1: MÁQUINA DE EXTRAÇÃO ---
# =============================================================================
if menu == "📡 Máquina de Extração":
    st.title("📡 Extrator de Resultados (Base)")
    banca_selecionada = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    
    tab1, tab2, tab3 = st.tabs(["📅 Dia Específico", "🚀 Extração em Massa", "✍️ Inserção Manual"])
    
    with tab1:
        dt_alvo = st.date_input("Escolha a Data:")
        if st.button("Puxar Resultados do Dia"):
            with st.spinner("Extraindo..."):
                dados = extrair_dia(banca_selecionada, dt_alvo)
                if dados: st.dataframe(pd.DataFrame(dados), use_container_width=True)
                else: st.warning("Nenhum dado encontrado para esta data.")
                
    with tab2:
        col1, col2 = st.columns(2)
        with col1: dt_inicio = st.date_input("Data Inicial:", value=date.today() - timedelta(days=5))
        with col2: dt_fim = st.date_input("Data Final:", value=date.today())
        
        if st.button("Iniciar Varredura em Massa"):
            with st.spinner("Varrendo os servidores..."):
                todos_dados = []
                delta = dt_fim - dt_inicio
                for i in range(delta.days + 1):
                    dia_atual = dt_inicio + timedelta(days=i)
                    todos_dados.extend(extrair_dia(banca_selecionada, dia_atual))
                
                if todos_dados:
                    df_massa = pd.DataFrame(todos_dados)
                    st.dataframe(df_massa, use_container_width=True)
                    csv = df_massa.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Baixar Dados (CSV)", data=csv, file_name=f"extracao_{banca_selecionada}.csv", mime="text/csv")
                else: st.warning("Nenhum dado encontrado no período.")

    with tab3:
        st.write("Insira os dados manualmente caso o site da banca esteja fora do ar.")
        df_manual = pd.DataFrame([{"Data": "", "Sorteio": "", "1º": "", "2º": "", "3º": "", "4º": "", "5º": ""}])
        df_editado = st.data_editor(df_manual, num_rows="dynamic", use_container_width=True)

# =============================================================================
# --- 5. TELA 2: ORÁCULO DE PADRÕES (GOOGLE SHEETS) ---
# =============================================================================
elif menu == "🧠 Oráculo de Padrões (Sheets)":
    st.title("🧠 Oráculo de Padrões (Cadeias de Markov)")
    st.markdown("Conecte a sua planilha confidencial para caçar as **Sombras e Repetições** da Banca.")
    
    link_csv = st.text_input("🔗 Link Público CSV do Google Sheets:", placeholder="https://docs.google.com/spreadsheets/d/e/.../pub?output=csv")
    
    if link_csv:
        try:
            # header=None evita que a primeira linha de dados vire título da coluna!
            # Adicionamos um prefixo genérico para você saber qual coluna é qual
            df_sheets = pd.read_csv(link_csv, header=None)
            df_sheets.columns = [f"Coluna {i}" for i in range(len(df_sheets.columns))]
            
            st.success(f"✅ Planilha conectada! {len(df_sheets)} sorteios carregados para análise.")
            
            with st.expander("👀 Ver Dados Brutos Carregados"):
                st.dataframe(df_sheets.head(10), use_container_width=True)
            
            st.markdown("---")
            
            # --- MOTOR DE MARKOV ---
            st.markdown("### 🕵️‍♂️ Rastreador de Sombras (Algoritmo Preditor)")
            st.markdown("Configure o radar: O que você quer procurar no passado para prever o futuro?")
            
            colunas_disponiveis = df_sheets.columns.tolist()
            
            c1, c2, c3 = st.columns(3)
            with c1:
                col_gatilho = st.selectbox("1. Onde ocorre o GATILHO?", colunas_disponiveis, help="A coluna onde o evento inicial acontece. Ex: Coluna do 1º Prêmio.")
            with c2:
                val_gatilho = st.text_input("2. Qual o NÚMERO do Gatilho?", placeholder="Ex: 15 (Grupo) ou 34 (Dezena)")
            with c3:
                col_sombra = st.selectbox("3. Onde a SOMBRA vai aparecer?", colunas_disponiveis, help="A coluna que você quer prever no JOGO SEGUINTE.")

            if st.button("Executar Varredura Histórica", use_container_width=True):
                if not val_gatilho:
                    st.error("⚠️ Você precisa digitar um número de Gatilho para iniciar a caçada.")
                else:
                    with st.spinner("Analisando cadeia de eventos em todo o histórico..."):
                        resultados_sombra = []
                        # O loop vai até o penúltimo para podermos olhar o "jogo seguinte" (i + 1)
                        for i in range(len(df_sheets) - 1):
                            # Verifica se o gatilho aconteceu nesta linha
                            valor_linha_atual = str(df_sheets.iloc[i][col_gatilho]).strip()
                            
                            # Se o gatilho for encontrado, olha para a próxima linha (O Sorteio Seguinte)
                            if valor_gatilho in valor_linha_atual:
                                sombra_encontrada = str(df_sheets.iloc[i+1][col_sombra]).strip()
                                # Limpeza básica para não pegar valores vazios
                                if sombra_encontrada and sombra_encontrada.lower() != 'nan':
                                    resultados_sombra.append(sombra_encontrada)
                        
                        st.markdown(f'<div class="markov-card">', unsafe_allow_html=True)
                        if resultados_sombra:
                            freq = pd.Series(resultados_sombra).value_counts().reset_index()
                            freq.columns = ["O Que Saiu no Sorteio Seguinte", "Frequência (Vezes)"]
                            
                            st.markdown(f'<div class="alerta-markov">🚨 GATILHO "{val_gatilho}" ENCONTRADO {len(resultados_sombra)} VEZES!</div>', unsafe_allow_html=True)
                            st.markdown("Sempre que o seu gatilho saiu, estes foram os números que a banca soltou logo em seguida na posição que você escolheu:")
                            
                            # Mostra o Top 10 mais frequentes no jogo seguinte
                            st.dataframe(freq.head(10), use_container_width=True, hide_index=True)
                        else:
                            st.warning(f"O radar não encontrou o gatilho '{val_gatilho}' no histórico fornecido ou não houve sorteio seguinte para ele.")
                        st.markdown('</div>', unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Erro ao ler a planilha. Verifique o link. Erro técnico: {e}")
