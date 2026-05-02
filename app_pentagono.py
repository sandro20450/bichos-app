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
st.set_page_config(page_title="Pentágono V47 - Backtest IA", page_icon="🎯", layout="wide")

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
    """Filtro para evitar que sorteios repetidos sejam salvos."""
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
    """Busca os resultados do dia diretamente na fonte."""
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
    st.header("🎯 Pentágono V47")
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
# --- 5. TELA 2: CÉREBRO IA (BACKTEST E GRUPOS FIXOS) ---
# =============================================================================
elif menu == "🧠 Cérebro IA (Algoritmo)":
    st.title("🧠 Algoritmo de Grupos Fixos e Backtest")
    st.info("Validação do passado e projeção dos **5 Grupos Mais Fortes** para uso como base nos seus jogos.")
    
    banca_ia = st.selectbox("Selecione a Banca Alvo para Análise:", list(BANCAS_CONFIG.keys()), key="sel_banca_ia")
    
    def get_grupo(m):
        """Função auxiliar para identificar o grupo (01 a 25) a partir de uma milhar."""
        try:
            d = int(str(m)[-2:])
            return "25" if d == 0 else str(math.ceil(d/4)).zfill(2)
        except: return None
        
    def calcular_top5(df_analise):
        """
        DOCUMENTAÇÃO DO MÉTODO:
        Esta função encapsula todo o cérebro matemático.
        Permite que o código a chame tanto para prever o FUTURO (sorteio atual)
        quanto para prever o PASSADO (máquina do tempo do Backtest).
        """
        scores_tmp = {str(i).zfill(2): {'puxada': 0, 'ruptura': 0, 'semana': 0, 'total': 0} for i in range(1, 26)}
        
        # 1. Ruptura
        atr_g = {str(i).zfill(2): {'t': 0, 'max': 0} for i in range(1, 26)}
        for i in range(len(df_analise)):
            g_v = get_grupo(df_analise.iloc[i]["P1"])
            if g_v:
                for k in atr_g:
                    atr_g[k]['t'] = 0 if k == g_v else atr_g[k]['t'] + 1
                    if atr_g[k]['t'] > atr_g[k]['max']: atr_g[k]['max'] = atr_g[k]['t']
        
        for k, v in atr_g.items():
            if v['t'] > 0 and v['t'] >= (v['max'] - 2):
                scores_tmp[k]['ruptura'] += 4  
        
        # 2. Puxada
        if len(df_analise) > 0:
            ult_g = get_grupo(df_analise.iloc[-1]["P1"])
            for i in range(len(df_analise)-1):
                if get_grupo(str(df_analise.iloc[i]["P1"]).zfill(4)) == ult_g:
                    g_p1 = get_grupo(df_analise.iloc[i+1]["P1"])
                    g_p2 = get_grupo(df_analise.iloc[i+1]["P2"])
                    if g_p1: scores_tmp[g_p1]['puxada'] += 7 
                    if g_p2: scores_tmp[g_p2]['puxada'] += 5 
        
        # 3. Semana
        if len(df_analise) > 0:
            limite_data = df_analise['Data'].max() - timedelta(days=7)
            df_semana = df_analise[df_analise['Data'] >= limite_data]
            for i in range(len(df_semana)):
                for p in ["P1", "P2", "P3", "P4", "P5"]:
                    g_v = get_grupo(df_semana.iloc[i][p])
                    if g_v: scores_tmp[g_v]['semana'] += 2
        
        for k in scores_tmp:
            scores_tmp[k]['total'] = scores_tmp[k]['puxada'] + scores_tmp[k]['ruptura'] + scores_tmp[k]['semana']
            
        ranking_tmp = sorted(scores_tmp.items(), key=lambda x: x[1]['total'], reverse=True)
        return [x[0] for x in ranking_tmp[:5]], scores_tmp

    if st.button("Processar Dados Matemáticos", use_container_width=True):
        with st.spinner("Analisando base, executando backtests e isolando os alvos de Elite..."):
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
                        
                        # =================================================================
                        # ROTINA DE BACKTEST (MÁQUINA DO TEMPO)
                        # =================================================================
                        resultados_bt = []
                        qtd_testes = min(5, len(df) - 1) # Previne erro se a planilha tiver poucos dados
                        
                        if qtd_testes > 0:
                            # O Python vai olhar as últimas linhas do histórico
                            for i in range(len(df) - qtd_testes, len(df)):
                                # Esconde o futuro do robô: corta a planilha ANTES do sorteio acontecer
                                df_passado = df.iloc[:i].copy() 
                                sorteio_alvo = str(df.iloc[i]["Sorteio"]).strip()
                                
                                # O robô prevê os Top 5 baseado APENAS no que sabia até aquele momento
                                top5_passado, _ = calcular_top5(df_passado)
                                
                                # O que REALMENTE saiu no 1º e 2º prêmio daquele momento?
                                g1_real = get_grupo(df.iloc[i]["P1"])
                                g2_real = get_grupo(df.iloc[i]["P2"])
                                
                                # Verifica a assertividade: se um dos reais estava no top 5 passado
                                if (g1_real in top5_passado) or (g2_real in top5_passado):
                                    resultados_bt.append(f"{sorteio_alvo} 🟢")
                                else:
                                    resultados_bt.append(f"{sorteio_alvo} ❌")

                        # =================================================================
                        # PREVISÃO PARA O PRESENTE (FUTURO)
                        # =================================================================
                        ult_m = str(df.iloc[-1]["P1"]).zfill(4)
                        ult_nome = str(df.iloc[-1]["Sorteio"])
                        ult_g = get_grupo(ult_m)
                        
                        top_5_grupos, scores = calcular_top5(df)

                        # =================================================================
                        # RENDERIZAÇÃO NA TELA
                        # =================================================================
                        
                        # 1. Painel de Backtest
                        st.markdown("### 🔙 Radar de Assertividade (Backtest)")
                        st.write("Verificamos a performance das previsões nos últimos 5 sorteios históricos do 1º e 2º Prêmio.")
                        
                        if resultados_bt:
                            st.info(" **-** ".join(resultados_bt))
                        else:
                            st.write("Sem histórico suficiente para backtest.")
                            
                        st.divider()

                        # 2. Painel de Gatilho e Previsão
                        st.success(f"**Gatilho Identificado:** Sorteio {ult_nome} | Milhar {ult_m} | Grupo {ult_g}")
                        
                        st.subheader("🎯 Os 5 Grupos Fixos (Alta Probabilidade)")
                        st.write("Estes são os 5 grupos mais fortes para o **próximo sorteio**. Utilize como Fixo nas suas estratégias.")
                        
                        colunas_fixos = st.columns(5)
                        for idx, grupo in enumerate(top_5_grupos):
                            pontos = scores[grupo]['total']
                            with colunas_fixos[idx]:
                                st.metric(label=f"Fixo {idx+1}º Lugar", value=grupo, delta=f"{pontos} pts")

            except Exception as e:
                st.error(f"Erro na conexão em tempo real: {e}")
