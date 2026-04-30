import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
import re
import math
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import itertools # Biblioteca especialista em combinações

# =============================================================================
# --- 1. CONFIGURAÇÕES E CONEXÃO GOOGLE SHEETS ---
# =============================================================================
# DOCUMENTAÇÃO: Configuração inicial da página atualizada para V45.
st.set_page_config(page_title="Pentágono V45 - 120 Duques", page_icon="🎯", layout="wide")

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
    st.header("🎯 Pentágono V45")
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
# --- 5. TELA 2: CÉREBRO IA (FÁBRICA DE DUQUES - TOP 16) ---
# =============================================================================
elif menu == "🧠 Cérebro IA (Algoritmo)":
    st.title("🧠 Algoritmo de Confluência Tática")
    st.info("O sistema agora cruza automaticamente os **Top 16 Grupos**, forjando **120 duplas perfeitas** para garantir maior cobertura estatística.")
    
    banca_ia = st.selectbox("Selecione a Banca Alvo para Análise:", list(BANCAS_CONFIG.keys()), key="sel_banca_ia")
    
    if st.button("Processar Dados Matemáticos", use_container_width=True):
        with st.spinner("Calculando pontuações e forjando combinações de Duques (120 alvos)..."):
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
                        
                        # DOCUMENTAÇÃO: O fatiamento (slice) foi alterado de 15 para 16
                        # Isso garante que a máquina capte o 16º grupo para cruzar.
                        top_16_grupos = [x[0] for x in ranking[:16]]
                        top_5_udz = pd.Series(duque_dz).value_counts().head(5).index.tolist() if duque_dz else []

                        # =================================================================
                        # RENDERIZAÇÃO E COMBINATÓRIA (FÁBRICA DE DUQUES - 120)
                        # =================================================================
                        st.success(f"**Gatilho Identificado:** Sorteio {ult_nome} | Milhar {ult_m} | Grupo {ult_g}")
                        
                        st.subheader("🎯 Top 16 Grupos de Elite")
                        
                        # DOCUMENTAÇÃO: Design Simétrico. Criamos 4 linhas com 4 colunas (4x4 = 16)
                        # Isso evita falhas de renderização e mantém o painel limpo.
                        linhas_colunas = [st.columns(4), st.columns(4), st.columns(4), st.columns(4)]
                        
                        for idx, grupo in enumerate(top_16_grupos):
                            linha_atual = idx // 4  # Determina qual das 4 linhas o item pertence (0, 1, 2 ou 3)
                            coluna_atual = idx % 4  # Determina qual coluna o item entra (0 a 3)
                            
                            pontos = scores[grupo]['total']
                            with linhas_colunas[linha_atual][coluna_atual]:
                                st.metric(label=f"{idx+1}º Lugar (Grupo)", value=grupo, delta=f"{pontos} pts")
                        
                        st.divider()

                        # DOCUMENTAÇÃO: A Combinatória Matemática.
                        # 1. Organizamos os 16 grupos do menor para o maior para facilitar a cópia.
                        top_16_ints = sorted([int(g) for g in top_16_grupos])
                        
                        # 2. O itertools cruza os 16 grupos de 2 em 2, resultando obrigatoriamente em 120 combinações.
                        duplas = list(itertools.combinations(top_16_ints, 2))
                        
                        # 3. Transformamos os números novamente em texto com 2 casas decimais (ex: '05', não '5').
                        lista_formatada = [f"{str(d[0]).zfill(2)}-{str(d[1]).zfill(2)}" for d in duplas]
                        
                        st.subheader("⚔️ Arsenal de Duques Gerados (120 Combinações)")
                        st.write("Aumento massivo de assertividade: 120 duplas perfeitas geradas pela análise profunda de 16 alvos.")
                        
                        # Renderiza as duplas prontas para cópia
                        texto_duplas = "  |  ".join(lista_formatada)
                        st.code(texto_duplas, language="text")

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
