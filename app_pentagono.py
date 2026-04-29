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
st.set_page_config(page_title="Pentágono V36 - Tempo Real", page_icon="🎯", layout="wide")

def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client.open("CentralBichos")
    except Exception as e:
        st.error(f"Erro na conexão com Google Sheets: {e}")
        return None

# --- MOTOR DE SALVAMENTO SEGURO (ANTI-DUPLICAÇÃO) ---
def salvar_sem_duplicar(ws, dados_novos):
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

st.markdown("""
<style>
    .stApp { background-color: #1e1e1e; color: #f0f0f0; }
    h1, h2, h3 { color: #4CAF50 !important; }
    .stButton > button { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 8px; }
    hr { border-color: #4CAF50; opacity: 0.3; }
    .card-tatico { background-color: #001a00; padding: 20px; border-radius: 10px; border: 1px solid #4CAF50; margin-bottom: 15px; }
    .card-alerta { background-color: #2b0000; padding: 20px; border-radius: 10px; border: 1px solid #ff4b4b; margin-bottom: 15px; }
    .titulo-card { color: #ffb74d; font-weight: bold; font-size: 1.25em; margin-bottom: 10px;}
    .dado-destaque { font-size: 1.8em; font-weight: bold; color: #fff; }
    .label-destaque { color: #4CAF50; font-weight: bold; font-size: 1.1em; }
    .sub-dado { color: #aaa; font-size: 0.85em; margin-left: 10px; }
    .badge-cercado { background-color: #1a3a5a; padding: 5px 10px; border-radius: 5px; color: #fff; font-weight: bold; border: 1px solid #2196F3; display: inline-block; margin-right: 5px; }
    .badge-duque { background-color: #4b3800; padding: 5px 10px; border-radius: 5px; color: #ffb74d; font-weight: bold; border: 1px solid #ffb74d; display: inline-block; margin-right: 5px; }
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
# --- 3. MENU LATERAL ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=80)
    st.header("🎯 Pentágono V36")
    menu = st.radio("Selecione a Base:", ["📡 Extração & Automação", "🔮 Conselheiro Tático (IA)"])

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
                        if inseridos > 0:
                            st.toast(f"✅ {inseridos} sorteios salvos!", icon="✅")
                            st.success(f"✅ {inseridos} sorteios salvos na aba {MAPA_ABAS[banca_sel]}!")
                        if repetidos > 0:
                            st.toast(f"⚠️ {repetidos} já existiam.", icon="⚠️")
                            st.warning(f"⚠️ {repetidos} sorteio(s) já existiam e foram ignorados para não duplicar.")
                else: st.error("Nenhum dado encontrado no site.")
                
    with tab2:
        col_m1, col_m2 = st.columns(2)
        with col_m1: dt_inicio = st.date_input("Data Inicial:", value=date.today() - timedelta(days=2))
        with col_m2: dt_fim = st.date_input("Data Final:", value=date.today())
        if st.button("🚀 SALVAR MASSA NA PLANILHA", use_container_width=True):
            with st.spinner("Varrendo servidores e validando dados..."):
                todos = []
                for i in range((dt_fim - dt_inicio).days + 1): 
                    todos.extend(extrair_dia(banca_sel, dt_inicio + timedelta(days=i)))
                if todos:
                    sh = conectar_sheets()
                    if sh:
                        ws = sh.worksheet(MAPA_ABAS[banca_sel])
                        inseridos, repetidos = salvar_sem_duplicar(ws, todos)
                        if inseridos > 0:
                            st.toast(f"✅ Massa concluída: {inseridos} novos.", icon="✅")
                            st.success(f"✅ {inseridos} novos sorteios salvos!")
                        if repetidos > 0:
                            st.toast(f"⚠️ {repetidos} ignorados (duplicados).", icon="⚠️")
                            st.warning(f"⚠️ {repetidos} sorteios ignorados (já estavam na planilha).")
                else: st.error("Nenhum dado no período.")
                
    with tab3:
        st.info("💡 **DICA:** Após digitar o último número, clique fora da tabela ou aperte ENTER antes de clicar em Salvar.")
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
                            if v_str == "" or v_str.lower() == "nan" or v_str == "none":
                                linha.append("") 
                            else:
                                linha.append(v_str.zfill(4))
                        limpos.append(linha)
                
                if limpos:
                    sh = conectar_sheets()
                    if sh:
                        ws = sh.worksheet(MAPA_ABAS[banca_sel])
                        inseridos, repetidos = salvar_sem_duplicar(ws, limpos)
                        if inseridos > 0:
                            st.toast(f"🎯 Salvo com sucesso! ({inseridos})", icon="✅")
                            st.success(f"✅ {inseridos} resultados manuais inseridos!")
                        if repetidos > 0:
                            st.toast(f"🚫 {repetidos} duplicados bloqueados.", icon="🚫")
                            st.warning(f"⚠️ {repetidos} sorteio(s) já constavam na planilha.")
                        if inseridos == 0 and repetidos == 0:
                            st.toast("Erro inesperado ou tabela vazia.", icon="❌")
                else:
                    st.toast("Preencha ao menos o Sorteio!", icon="⚠️")

# =============================================================================
# --- 5. TELA 2: CONSELHEIRO TÁTICO (TEMPO REAL VIA API) ---
# =============================================================================
elif menu == "🔮 Conselheiro Tático (IA)":
    st.title("🔮 Inteligência Artificial de Combate")
    st.markdown("O Pentágono agora puxa os seus dados **diretamente da API em tempo real**, sem atrasos de cache!")
    
    # AGORA SELECIONA A BANCA EM VEZ DE COLAR O LINK
    banca_ia = st.selectbox("Selecione a Banca Alvo para Análise:", list(BANCAS_CONFIG.keys()), key="sel_banca_ia")
    
    if st.button("Gerar Relatórios de Ataque", use_container_width=True):
        with st.spinner("Puxando histórico em tempo real da CentralBichos..."):
            try:
                sh = conectar_sheets()
                if sh:
                    ws = sh.worksheet(MAPA_ABAS[banca_ia])
                    dados_brutos = ws.get_all_values()
                    
                    if not dados_brutos:
                        st.error("A aba selecionada está vazia.")
                    else:
                        df = pd.DataFrame(dados_brutos)
                        
                        # Garante que tenha pelo menos 7 colunas e nomeia
                        for i in range(len(df.columns), 7): df[i] = ""
                        df = df.iloc[:, :7]
                        df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
                        
                        # Limpeza Pesada: Remove cabeçalhos e linhas vazias
                        df = df[df["P1"].astype(str).str.strip() != ""]
                        df = df[df["P1"].astype(str).str.lower() != "nan"]
                        df = df[df["P1"].astype(str).str.lower() != "none"]
                        df = df[df["P1"].astype(str).str.lower() != "p1"]
                        df = df[~df["P1"].astype(str).str.contains("---")]

                        if df.empty:
                            st.warning("Não há dados válidos de prêmios nesta aba para analisar.")
                        else:
                            def get_grupo(m):
                                try:
                                    d = int(str(m)[-2:])
                                    return "25" if d == 0 else str(math.ceil(d/4)).zfill(2)
                                except: return None
                            
                            atr_g = {str(i).zfill(2): {'t': 0, 'max': 0} for i in range(1, 26)}
                            atr_um = {str(i): {'t': 0, 'max': 0} for i in range(10)} 
                            
                            for i in range(len(df)):
                                m_str = str(df.iloc[i]["P1"]).zfill(4)
                                g_v, um_v = get_grupo(m_str), m_str[0]
                                if g_v:
                                    for k in atr_g:
                                        atr_g[k]['t'] = 0 if k == g_v else atr_g[k]['t'] + 1
                                        if atr_g[k]['t'] > atr_g[k]['max']: atr_g[k]['max'] = atr_g[k]['t']
                                for k in atr_um:
                                    atr_um[k]['t'] = 0 if k == um_v else atr_um[k]['t'] + 1
                                    if atr_um[k]['t'] > atr_um[k]['max']: atr_um[k]['max'] = atr_um[k]['t']

                            # Pegando o ÚLTIMO SORTEIO REAL
                            ult_m = str(df.iloc[-1]["P1"]).zfill(4)
                            ult_nome = str(df.iloc[-1]["Sorteio"])
                            ult_g = get_grupo(ult_m)
                            
                            seco_g, seco_um = [], []
                            duque_g = [] 
                            cercado_g, cercado_um = [], []

                            for i in range(len(df)-1):
                                if get_grupo(str(df.iloc[i]["P1"]).zfill(4)) == ult_g:
                                    p_m_seco = str(df.iloc[i+1]["P1"]).zfill(4)
                                    seco_g.append(get_grupo(p_m_seco))
                                    seco_um.append(p_m_seco[0])
                                    
                                    for p in ["P1", "P2"]:
                                        p_m_duq = str(df.iloc[i+1][p]).zfill(4)
                                        if p_m_duq != "nan" and "---" not in p_m_duq and p_m_duq != "":
                                            g_duq = get_grupo(p_m_duq)
                                            if g_duq: duque_g.append(g_duq)
                                            
                                    for p in ["P1", "P2", "P3", "P4", "P5"]:
                                        p_m_all = str(df.iloc[i+1][p]).zfill(4)
                                        if p_m_all != "nan" and "---" not in p_m_all and p_m_all != "":
                                            g_cerc = get_grupo(p_m_all)
                                            if g_cerc: cercado_g.append(g_cerc)
                                            cercado_um.append(p_m_all[0])
                                    
                            top_seco_g = pd.Series(seco_g).mode()[0] if seco_g else "N/A"
                            top_seco_um = pd.Series(seco_um).mode()[0] if seco_um else "N/A"
                            top_duq_g = pd.Series(duque_g).value_counts().head(2).index.tolist() if duque_g else []
                            top_cerc_g = pd.Series(cercado_g).value_counts().head(3).index.tolist() if cercado_g else []
                            top_cerc_um = pd.Series(cercado_um).value_counts().head(3).index.tolist() if cercado_um else []

                            st.success(f"Base Sincronizada ao Vivo! Último Sorteio Encontrado: {ult_nome} - Milhar {ult_m} (Grupo {ult_g})")

                            st.markdown(f"""
<div class="card-tatico">
<div class="titulo-card">🔮 1. Oráculo Markov (Predição Pós-Grupo {ult_g})</div>

<div style="margin-bottom: 20px;">
<span class="label-destaque">🎯 ALVO SECO (Para o 1º Prêmio):</span><br>
Grupo Alvo: <span class="dado-destaque">{top_seco_g}</span> | 
Unid. Milhar: <span class="dado-destaque">{top_seco_um}</span>
</div>

<hr>

<div style="margin-bottom: 20px; margin-top: 10px;">
<span class="label-destaque" style="color:#ffb74d;">⚔️ DUQUE DE GRUPO (Para sair no 1º ou 2º Prêmio):</span><br>
<p style="color:#aaa; font-size:0.9em; margin-bottom: 5px;">Aposte casando estes dois grupos na cabeça e segundo.</p>
<b>TOP 2 GRUPOS:</b> {' '.join([f'<span class="badge-duque">{x}</span>' for x in top_duq_g])}
</div>

<hr>

<div style="margin-top: 10px;">
<span class="label-destaque">🛡️ ALVOS CERCADOS (Para sair do 1º ao 5º):</span><br>
<p style="color:#aaa; font-size:0.9em; margin-bottom: 5px;">Estes são os números que mais aparecem em qualquer posição após o grupo gatilho.</p>
<b>TOP GRUPOS:</b> {' '.join([f'<span class="badge-cercado">{x}</span>' for x in top_cerc_g])}<br><br>
<b>TOP UNIDADES MILHAR:</b> {' '.join([f'<span class="badge-cercado">{x}</span>' for x in top_cerc_um])}
</div>
</div>
""", unsafe_allow_html=True)

                            def gerar_alertas(dic, pref):
                                alertas = []
                                for k, v in dic.items():
                                    if v['t'] > 0 and v['t'] >= (v['max'] - 2):
                                        alertas.append(f"• {pref} **{k}** <span class='sub-dado'>(Atraso: {v['t']} | Recorde: {v['max']})</span>")
                                return "<br>".join(alertas) if alertas else "Sem rupturas iminentes."

                            st.markdown(f"""
<div class="card-alerta">
<div class="titulo-card" style="color:#ff4b4b;">⏳ 2. Alerta de Ponto Crítico (Ruptura)</div>
<b style="color:#ffb74d;">🦁 GRUPOS (1º Prêmio):</b><br>{gerar_alertas(atr_g, "Grupo")}<br><br>
<b style="color:#ffb74d;">🥇 UNID. MILHAR (1º Prêmio):</b><br>{gerar_alertas(atr_um, "UM")}
</div>
""", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Erro na conexão em tempo real: {e}")
