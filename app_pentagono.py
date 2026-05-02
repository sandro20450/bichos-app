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
st.set_page_config(page_title="Pentágono V46 - Fechamento de Fixos", page_icon="🎯", layout="wide")

def conectar_sheets():
    """Conecta com segurança à API do Google Sheets."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client.open("CentralBichos")
    except Exception as e:
        st.error(f"Erro na conexão com Google Sheets: {e}")
        return None

def salvar_sem_duplicar(ws, dados_novos):
    """Filtro para evitar que sorteios repetidos sejam salvos na base."""
    try:
        existentes = ws.get_all_values()
        set_existentes = set()
        for row in existentes:
            if len(row) >= 2:
                set_existentes.add(f"{str(row[0]).strip()}_{str(row[1]).strip()}")
        
        para_inserir = []
        duplicados = 0
        for linha in dados_novos:
            chave = f"{str(linha[0]).strip()}_{str(linha[1]).strip()}"
            if chave in set_existentes:
                duplicados += 1
            else:
                para_inserir.append(linha)
                set_existentes.add(chave)
                
        if para_inserir:
            ws.append_rows(para_inserir, value_input_option="RAW")
            
        return len(para_inserir), duplicados
    except Exception as e:
        st.error(f"Erro ao salvar na planilha: {e}")
        return 0, 0

MAPA_ABAS = {
    "Tradicional": "TRADICIONAL_MILHAR",
    "Caminho da Sorte": "CAMINHO_MILHAR",
    "Monte Carlos": "MONTE_MILHAR",
    "Lotep": "LOTEP_MILHAR"
}

BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-",
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-",
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-",
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

# =============================================================================
# --- 2. MOTORES DE EXTRAÇÃO (WEB SCRAPING) ---
# =============================================================================
def extrair_dia(banca, data_alvo):
    """Rastreador web que busca os resultados do dia diretamente na fonte."""
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
# --- 3. MENU LATERAL ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=80)
    st.header("🎯 Pentágono V46")
    menu = st.radio("Selecione a Base:", ["📡 Extração & Automação", "🧠 Cérebro IA (Algoritmo)"])

# =============================================================================
# --- 4. TELA 1: EXTRAÇÃO MULTI-MODAL ---
# =============================================================================
if menu == "📡 Extração & Automação":
    st.title("📡 Automação CentralBichos")
    banca_sel = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    tab1, tab2, tab3 = st.tabs(["📅 Dia Específico", "🚀 Extração em Massa", "✍️ Inserção Manual"])
    
    with tab1:
        dt_alvo = st.date_input("Data do Sorteio:", value=date.today(), key="data_unica")
        if st.button("🚀 EXTRAIR E SALVAR (1 DIA)", use_container_width=True):
            with st.spinner("Conectando e verificando duplicatas..."):
                dados = extrair_dia(banca_sel, dt_alvo)
                if dados:
                    sh = conectar_sheets()
                    if sh:
                        ws = sh.worksheet(MAPA_ABAS[banca_sel])
                        inseridos, repetidos = salvar_sem_duplicar(ws, dados)
                        if inseridos > 0: st.success(f"✅ {inseridos} sorteios salvos na aba {MAPA_ABAS[banca_sel]}!")
                        if repetidos > 0: st.warning(f"⚠️ {repetidos} sorteio(s) já existiam.")
                else: st.error("Nenhum dado encontrado no site.")
                
    with tab2:
        col_m1, col_m2 = st.columns(2)
        with col_m1: dt_inicio = st.date_input("Data Inicial:", value=date.today() - timedelta(days=2))
        with col_m2: dt_fim = st.date_input("Data Final:", value=date.today())
        if st.button("🚀 SALVAR MASSA NA PLANILHA", use_container_width=True):
            with st.spinner("Varrendo servidores..."):
                todos = []
                for i in range((dt_fim - dt_inicio).days + 1): 
                    todos.extend(extrair_dia(banca_sel, dt_inicio + timedelta(days=i)))
                if todos:
                    sh = conectar_sheets()
                    if sh:
                        ws = sh.worksheet(MAPA_ABAS[banca_sel])
                        inseridos, repetidos = salvar_sem_duplicar(ws, todos)
                        if inseridos > 0: st.success(f"✅ {inseridos} novos sorteios salvos!")
                        if repetidos > 0: st.warning(f"⚠️ {repetidos} sorteios ignorados.")
                else: st.error("Nenhum dado no período.")
                
    with tab3:
        st.info("💡 Após digitar o último número, clique fora da tabela antes de clicar em Salvar.")
        df_manual = pd.DataFrame([{"Data": date.today().strftime('%Y-%m-%d'), "Sorteio": "", "1º": "", "2º": "", "3º": "", "4º": "", "5º": ""}], dtype=str)
        df_editado = st.data_editor(df_manual, num_rows="dynamic", use_container_width=True)
        
        if st.button("💾 SALVAR DADOS MANUAIS", use_container_width=True):
            with st.spinner("Analisando células..."):
                limpos = []
                for r in df_editado.values.tolist():
                    data_v = str(r[0]).strip()
                    sort_v = str(r[1]).strip()
                    if sort_v != "" and sort_v != "nan" and sort_v != "None":
                        linha = [data_v, sort_v]
                        for v in r[2:7]: 
                            v_str = str(v).replace(".0", "").strip()
                            linha.append("" if v_str == "" or v_str.lower() in ["nan", "none"] else v_str.zfill(4))
                        limpos.append(linha)
                
                if limpos:
                    sh = conectar_sheets()
                    if sh:
                        ws = sh.worksheet(MAPA_ABAS[banca_sel])
                        inseridos, repetidos = salvar_sem_duplicar(ws, limpos)
                        if inseridos > 0: st.success(f"✅ {inseridos} resultados manuais inseridos!")
                        if repetidos > 0: st.warning(f"⚠️ {repetidos} sorteio(s) já constavam na planilha.")
                else:
                    st.warning("Preencha ao menos o Sorteio!")

# =============================================================================
# --- 5. TELA 2: CÉREBRO IA (ESTRATÉGIA: GRUPOS FIXOS) ---
# =============================================================================
elif menu == "🧠 Cérebro IA (Algoritmo)":
    st.title("🧠 Algoritmo: Fechamento com Fixo")
    st.info("O sistema agora isola os **5 Grupos Mais Fortes** e gera automaticamente as 24 combinações de Duque para cada um deles.")
    
    banca_ia = st.selectbox("Selecione a Banca Alvo para Análise:", list(BANCAS_CONFIG.keys()), key="sel_banca_ia")
    
    if st.button("Processar Dados Matemáticos", use_container_width=True):
        with st.spinner("Analisando base e isolando os alvos de Elite..."):
            try:
                sh = conectar_sheets()
                if sh:
                    ws = sh.worksheet(MAPA_ABAS[banca_ia])
                    dados_brutos = ws.get_all_values()
                    
                    if len(dados_brutos) < 2:
                        st.error("Dados insuficientes na aba selecionada.")
                    else:
                        df = pd.DataFrame(dados_brutos)
                        for i in range(len(df.columns), 7): df[i] = ""
                        df = df.iloc[:, :7]
                        df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
                        
                        df = df[df["P1"].astype(str).str.strip() != ""]
                        df = df[df["P1"].astype(str).str.lower() != "p1"]
                        df = df[~df["P1"].astype(str).str.contains("---")]
                        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
                        
                        def get_grupo(m):
                            try:
                                d = int(str(m)[-2:])
                                return "25" if d == 0 else str(math.ceil(d/4)).zfill(2)
                            except: return None
                        
                        scores = {str(i).zfill(2): {'puxada': 0, 'ruptura': 0, 'semana': 0, 'total': 0} for i in range(1, 26)}
                        
                        # --- CÁLCULOS DO ALGORITMO ---
                        atr_g = {str(i).zfill(2): {'t': 0, 'max': 0} for i in range(1, 26)}
                        for i in range(len(df)):
                            g_v = get_grupo(df.iloc[i]["P1"])
                            if g_v:
                                for k in atr_g:
                                    atr_g[k]['t'] = 0 if k == g_v else atr_g[k]['t'] + 1
                                    if atr_g[k]['t'] > atr_g[k]['max']: atr_g[k]['max'] = atr_g[k]['t']
                        
                        for k, v in atr_g.items():
                            if v['t'] > 0 and v['t'] >= (v['max'] - 2):
                                scores[k]['ruptura'] += 4  
                        
                        ult_m = str(df.iloc[-1]["P1"]).zfill(4)
                        ult_nome = str(df.iloc[-1]["Sorteio"])
                        ult_g = get_grupo(ult_m)
                        
                        duque_dz = []
                        
                        for i in range(len(df)-1):
                            if get_grupo(str(df.iloc[i]["P1"]).zfill(4)) == ult_g:
                                g_p1 = get_grupo(df.iloc[i+1]["P1"])
                                g_p2 = get_grupo(df.iloc[i+1]["P2"])
                                if g_p1: scores[g_p1]['puxada'] += 7 
                                if g_p2: scores[g_p2]['puxada'] += 5 
                                
                                for p in ["P1", "P2"]:
                                    m_duq = str(df.iloc[i+1][p]).zfill(4)
                                    if len(m_duq) == 4 and m_duq != "0000":
                                        duque_dz.append(m_duq[-2]) 
                        
                        limite_data = df['Data'].max() - timedelta(days=7)
                        df_semana = df[df['Data'] >= limite_data]
                        
                        for i in range(len(df_semana)):
                            for p in ["P1", "P2", "P3", "P4", "P5"]:
                                g_v = get_grupo(df_semana.iloc[i][p])
                                if g_v: scores[g_v]['semana'] += 2
                        
                        for k in scores:
                            scores[k]['total'] = scores[k]['puxada'] + scores[k]['ruptura'] + scores[k]['semana']
                            
                        ranking = sorted(scores.items(), key=lambda x: x[1]['total'], reverse=True)
                        
                        # DOCUMENTAÇÃO: O fatiamento foi drasticamente afunilado para os TOP 5 Grupos absolutos.
                        top_5_grupos = [x[0] for x in ranking[:5]]
                        top_5_udz = pd.Series(duque_dz).value_counts().head(5).index.tolist() if duque_dz else []

                        # =================================================================
                        # RENDERIZAÇÃO: OS 5 FIXOS E SEUS FECHAMENTOS
                        # =================================================================
                        st.success(f"**Gatilho Identificado:** Sorteio {ult_nome} | Milhar {ult_m} | Grupo {ult_g}")
                        
                        st.subheader("🎯 Os 5 Grupos Fixos (Alta Probabilidade)")
                        st.write("Estes são os 5 grupos mais fortes do cenário. Escolha um (ou mais) para usar como Fixo.")
                        
                        # Exibe os 5 Fixos lado a lado
                        colunas_fixos = st.columns(5)
                        for idx, grupo in enumerate(top_5_grupos):
                            pontos = scores[grupo]['total']
                            with colunas_fixos[idx]:
                                st.metric(label=f"Fixo {idx+1}º Lugar", value=grupo, delta=f"{pontos} pts")
                        
                        st.divider()

                        st.subheader("⚔️ Arsenal de Fechamento (Fixo x 24 Grupos)")
                        st.write("Abaixo estão as 24 combinações prontas para cada Fixo. Se o seu Fixo sair, o Duque é infalível.")
                        
                        # DOCUMENTAÇÃO: Fábrica de Duques com Fixo.
                        # O laço (for) percorre cada um dos 5 grupos escolhidos.
                        for fixo in top_5_grupos:
                            st.markdown(f"<h4 style='color:#4CAF50;'>► Fechamento usando o Grupo Fixo {fixo}</h4>", unsafe_allow_html=True)
                            
                            combos_fixo = []
                            # O laço secundário cruza o Fixo com todos os números de 1 a 25.
                            for i in range(1, 26):
                                numero_alvo = str(i).zfill(2)
                                # Impede que o fixo cruze com ele mesmo (ex: 09-09)
                                if numero_alvo != fixo:
                                    # Organiza para o menor número ficar na frente
                                    menor = min(int(fixo), int(numero_alvo))
                                    maior = max(int(fixo), int(numero_alvo))
                                    combos_fixo.append(f"{str(menor).zfill(2)}-{str(maior).zfill(2)}")
                            
                            # Exibe o arsenal em uma caixa de código pronta para cópia
                            texto_fechamento = "  |  ".join(combos_fixo)
                            st.code(texto_fechamento, language="text")

                        st.divider()
                        
                        st.subheader("🔟 Top 5 Unidades de Dezena (3º Dígito)")
                        st.write("Os algarismos com maior probabilidade de entrarem na casa da dezena (1º ou 2º prêmio).")
                        
                        col_d1, col_d2, col_d3, col_d4, col_d5 = st.columns(5)
                        colunas_dz = [col_d1, col_d2, col_d3, col_d4, col_d5]
                        
                        for idx, digito in enumerate(top_5_udz):
                            with colunas_dz[idx]:
                                st.metric(label=f"Posição {idx+1}", value=digito)

            except Exception as e:
                st.error(f"Erro na conexão em tempo real: {e}")
