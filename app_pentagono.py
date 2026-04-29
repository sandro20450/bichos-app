import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =============================================================================
# --- 1. CONFIGURAÇÕES E CONEXÃO GOOGLE SHEETS ---
# =============================================================================
st.set_page_config(page_title="Pentágono V29 - Conselheiro IA", page_icon="🎯", layout="wide")

def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client.open("CentralBichos")
    except Exception as e:
        st.error(f"Erro na conexão com Google Sheets: {e}")
        return None

MAPA_ABAS = {
    "Tradicional": "TRADICIONAL_MILHAR",
    "Caminho da Sorte": "CAMINHO_MILHAR",
    "Monte Carlos": "MONTE_MILHAR",
    "Lotep": "LOTEP_MILHAR"
}

st.markdown("""
<style>
    .stApp { background-color: #1e1e1e; color: #f0f0f0; }
    h1, h2, h3 { color: #4CAF50 !important; }
    .stButton > button { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 8px; }
    hr { border-color: #4CAF50; opacity: 0.3; }
    .card-tatico { background-color: #001a00; padding: 20px; border-radius: 10px; border: 1px solid #4CAF50; margin-bottom: 15px; }
    .card-alerta { background-color: #2b0000; padding: 20px; border-radius: 10px; border: 1px solid #ff4b4b; margin-bottom: 15px; }
    .titulo-card { color: #ffb74d; font-weight: bold; font-size: 1.2em; margin-bottom: 10px;}
    .dado-destaque { font-size: 1.8em; font-weight: bold; color: #fff; }
</style>
""", unsafe_allow_html=True)

BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-",
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-",
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-",
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

# =============================================================================
# --- 2. MOTORES DE EXTRAÇÃO ---
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
            
            milhares = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhar = nums[0].zfill(4) if nums and len(nums[0]) >= 3 else "----"
                    milhares.append(milhar)
                    
            if len(milhares) >= 5:
                resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

# =============================================================================
# --- 3. FUNÇÕES TÁTICAS (IA) ---
# =============================================================================
def calc_grupo(milhar):
    try:
        dez = int(str(milhar)[-2:])
        if dez == 0: return "25"
        return str(math.ceil(dez/4)).zfill(2)
    except: return None

def calc_dezena(milhar):
    try: return str(milhar)[-2:].zfill(2)
    except: return None

# =============================================================================
# --- 4. MENU LATERAL ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=80)
    st.header("🎯 Pentágono V29")
    menu = st.radio("Selecione a Base:", ["📡 Extração & Automação", "🔮 Conselheiro Tático (IA)"])

# =============================================================================
# --- 5. TELA 1: EXTRAÇÃO ---
# =============================================================================
if menu == "📡 Extração & Automação":
    st.title("📡 Automação CentralBichos")
    banca_sel = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    dt_alvo = st.date_input("Data do Sorteio:", value=date.today())
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔍 Apenas Visualizar", use_container_width=True):
            dados = extrair_dia(banca_sel, dt_alvo)
            if dados: st.table(pd.DataFrame(dados, columns=["Data", "Horário", "1º", "2º", "3º", "4º", "5º"]))
            else: st.error("Nenhum dado encontrado.")
    with col2:
        if st.button("🚀 EXTRAIR E SALVAR", use_container_width=True):
            with st.spinner("Conectando e salvando..."):
                dados = extrair_dia(banca_sel, dt_alvo)
                if dados:
                    sh = conectar_sheets()
                    if sh:
                        ws = sh.worksheet(MAPA_ABAS[banca_sel])
                        ws.append_rows(dados)
                        st.success(f"✅ {len(dados)} sorteios salvos na aba {MAPA_ABAS[banca_sel]}!")
                else: st.error("Erro ao extrair.")

# =============================================================================
# --- 6. TELA 2: CONSELHEIRO TÁTICO ---
# =============================================================================
elif menu == "🔮 Conselheiro Tático (IA)":
    st.title("🔮 Inteligência Artificial de Combate")
    st.markdown("Cole o link CSV da sua aba de Milhares para gerar os Relatórios de Ataque Automáticos.")
    
    link_csv = st.text_input("🔗 Link Público CSV do Google Sheets:", placeholder="Cole aqui o link da planilha...")
    
    if link_csv:
        if st.button("Gerar Relatórios de Ataque", use_container_width=True):
            with st.spinner("Analisando matriz de dados..."):
                try:
                    df = pd.read_csv(link_csv, header=None)
                    df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
                    
                    # Pegar a última linha (Último sorteio)
                    ultimo_sorteio = df.iloc[-1]
                    ult_milhar_1 = str(ultimo_sorteio["P1"])
                    ult_grupo_1 = calc_grupo(ult_milhar_1)
                    ult_dez_1 = calc_dezena(ult_milhar_1)
                    
                    st.success(f"Base Carregada! Analisando após o último sorteio: {ult_milhar_1} (Grupo {ult_grupo_1})...")
                    
                    # ---------------------------------------------------------
                    # ESTRATÉGIA 1: MARKOV AUTOMÁTICO (O QUE SAI DEPOIS)
                    # ---------------------------------------------------------
                    proximos_grupos = []
                    proximas_dezenas = []
                    for i in range(len(df)-1):
                        g_atual = calc_grupo(df.iloc[i]["P1"])
                        if g_atual == ult_grupo_1:
                            prox_m = str(df.iloc[i+1]["P1"])
                            proximos_grupos.append(calc_grupo(prox_m))
                            proximas_dezenas.append(calc_dezena(prox_m))
                            
                    top_g_markov = pd.Series(proximos_grupos).mode()[0] if proximos_grupos else "N/A"
                    top_d_markov = pd.Series(proximas_dezenas).mode()[0] if proximas_dezenas else "N/A"
                    
                    st.markdown("""
                    <div class="card-tatico">
                        <div class="titulo-card">🔮 1. Previsor Markov (Próximo Combate)</div>
                        O último 1º prêmio foi do Grupo <b>{}</b>. Historicamente, quando ele sai, a banca costuma soltar no sorteio seguinte:<br><br>
                        🎯 Grupo Alvo (1º Prêmio): <span class="dado-destaque">{}</span><br>
                        🎯 Dezena Alvo (1º Prêmio): <span class="dado-destaque">{}</span>
                    </div>
                    """.format(ult_grupo_1, top_g_markov, top_d_markov), unsafe_allow_html=True)

                    # ---------------------------------------------------------
                    # ESTRATÉGIA 2: PONTO CRÍTICO (RECORDES DE GRUPOS NO 1º)
                    # ---------------------------------------------------------
                    atrasos = {str(i).zfill(2): {'temp': 0, 'max': 0} for i in range(1, 26)}
                    for i in range(len(df)):
                        g_linha = calc_grupo(df.iloc[i]["P1"])
                        for g in atrasos:
                            if g == g_linha:
                                atrasos[g]['temp'] = 0
                            else:
                                atrasos[g]['temp'] += 1
                                if atrasos[g]['temp'] > atrasos[g]['max']:
                                    atrasos[g]['max'] = atrasos[g]['temp']
                                    
                    # Filtrar quem está no limite
                    alertas = []
                    for g, dados in atrasos.items():
                        # Se o atraso atual está a 2 ou menos jogos do recorde máximo
                        if dados['temp'] > 0 and dados['temp'] >= (dados['max'] - 2):
                            alertas.append(f"Grupo {g} (Atraso: {dados['temp']} | Recorde: {dados['max']})")
                            
                    alerta_txt = "<br>".join(alertas) if alertas else "Nenhum grupo na zona de risco no momento."
                    
                    st.markdown(f"""
                    <div class="card-alerta">
                        <div class="titulo-card" style="color:#ff4b4b;">⏳ 2. Alerta de Ponto Crítico (Ruptura)</div>
                        Estes grupos estão próximos ou ultrapassaram o seu limite máximo histórico de atraso no 1º prêmio. Prepare o cerco:<br><br>
                        <span style="color:#fff; font-weight:bold;">{alerta_txt}</span>
                    </div>
                    """, unsafe_allow_html=True)

                    # ---------------------------------------------------------
                    # ESTRATÉGIA 3: TROPAS ALIADAS (DOBRADINHAS 2º AO 5º)
                    # ---------------------------------------------------------
                    aliados = []
                    for i in range(len(df)):
                        if calc_grupo(df.iloc[i]["P1"]) == ult_grupo_1:
                            for p in ["P2", "P3", "P4", "P5"]:
                                aliados.append(calc_grupo(df.iloc[i][p]))
                                
                    if aliados:
                        top_aliados = pd.Series(aliados).value_counts().head(2).index.tolist()
                        aliados_str = " e ".join(top_aliados)
                    else:
                        aliados_str = "N/A"
                        
                    st.markdown(f"""
                    <div class="card-tatico" style="border-color:#2196F3;">
                        <div class="titulo-card" style="color:#2196F3;">🤝 3. Radar de Tropas Aliadas (Casadinha)</div>
                        Sempre que o Grupo {ult_grupo_1} sai no 1º prêmio, ele costuma puxar estes grupos do 2º ao 5º prêmio no mesmo sorteio:<br><br>
                        🎯 Grupos Aliados Fortes: <span class="dado-destaque">{aliados_str}</span>
                    </div>
                    """, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Erro ao analisar o campo de batalha. Verifique o link e os dados: {e}")
