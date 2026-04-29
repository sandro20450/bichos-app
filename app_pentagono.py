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
st.set_page_config(page_title="Pentágono V32.1 - Arsenal Completo", page_icon="🎯", layout="wide")

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
    .titulo-card { color: #ffb74d; font-weight: bold; font-size: 1.25em; margin-bottom: 10px;}
    .dado-destaque { font-size: 2em; font-weight: bold; color: #fff; }
    .label-destaque { color: #4CAF50; font-weight: bold; font-size: 1.1em; }
    .sub-dado { color: #aaa; font-size: 0.9em; margin-left: 10px; }
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
    st.header("🎯 Pentágono V32.1")
    menu = st.radio("Selecione a Base:", ["📡 Extração & Automação", "🔮 Conselheiro Tático (IA)"])

# =============================================================================
# --- 4. TELA 1: EXTRAÇÃO MULTI-MODAL ---
# =============================================================================
if menu == "📡 Extração & Automação":
    st.title("📡 Automação CentralBichos")
    banca_sel = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    
    tab1, tab2, tab3 = st.tabs(["📅 Dia Específico", "🚀 Extração em Massa", "✍️ Inserção Manual"])
    
    # -------------------------------------------------------------------------
    # ABA 1: DIA ESPECÍFICO
    # -------------------------------------------------------------------------
    with tab1:
        dt_alvo = st.date_input("Data do Sorteio:", value=date.today(), key="data_unica")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔍 Apenas Visualizar", use_container_width=True, key="btn_vis_1"):
                dados = extrair_dia(banca_sel, dt_alvo)
                if dados: st.table(pd.DataFrame(dados, columns=["Data", "Sorteio", "1º", "2º", "3º", "4º", "5º"]))
                else: st.error("Nenhum dado encontrado.")
        with c2:
            if st.button("🚀 EXTRAIR E SALVAR (1 DIA)", use_container_width=True, key="btn_salv_1"):
                with st.spinner("Conectando e salvando..."):
                    dados = extrair_dia(banca_sel, dt_alvo)
                    if dados:
                        sh = conectar_sheets()
                        if sh:
                            ws = sh.worksheet(MAPA_ABAS[banca_sel])
                            # Modo RAW força o Google a aceitar zeros à esquerda
                            ws.append_rows(dados, value_input_option="RAW")
                            st.success(f"✅ {len(dados)} sorteios salvos na aba {MAPA_ABAS[banca_sel]}!")
                    else: st.error("Erro ao extrair.")

    # -------------------------------------------------------------------------
    # ABA 2: EXTRAÇÃO EM MASSA
    # -------------------------------------------------------------------------
    with tab2:
        col_m1, col_m2 = st.columns(2)
        with col_m1: dt_inicio = st.date_input("Data Inicial:", value=date.today() - timedelta(days=2))
        with col_m2: dt_fim = st.date_input("Data Final:", value=date.today())
        
        c3, c4 = st.columns(2)
        with c3:
            if st.button("🔍 Visualizar Massa", use_container_width=True):
                with st.spinner("Varrendo histórico..."):
                    todos_dados = []
                    delta = dt_fim - dt_inicio
                    for i in range(delta.days + 1):
                        dia_atual = dt_inicio + timedelta(days=i)
                        todos_dados.extend(extrair_dia(banca_sel, dia_atual))
                    if todos_dados: st.dataframe(pd.DataFrame(todos_dados, columns=["Data", "Sorteio", "1º", "2º", "3º", "4º", "5º"]), use_container_width=True)
                    else: st.warning("Nenhum dado no período.")
        with c4:
            if st.button("🚀 SALVAR MASSA NA PLANILHA", use_container_width=True):
                with st.spinner("Varrendo servidores e enviando para o Google..."):
                    todos_dados = []
                    delta = dt_fim - dt_inicio
                    for i in range(delta.days + 1):
                        dia_atual = dt_inicio + timedelta(days=i)
                        todos_dados.extend(extrair_dia(banca_sel, dia_atual))
                    
                    if todos_dados:
                        sh = conectar_sheets()
                        if sh:
                            ws = sh.worksheet(MAPA_ABAS[banca_sel])
                            ws.append_rows(todos_dados, value_input_option="RAW")
                            st.success(f"✅ {len(todos_dados)} sorteios salvos na aba {MAPA_ABAS[banca_sel]}!")
                    else: st.error("Nenhum dado encontrado no período.")

    # -------------------------------------------------------------------------
    # ABA 3: INSERÇÃO MANUAL (CORRIGIDA)
    # -------------------------------------------------------------------------
    with tab3:
        st.write("Digite os resultados manualmente. O sistema forçará 4 dígitos (ex: '911' vira '0911').")
        
        # dtype=str blinda a tabela contra interpretações matemáticas indesejadas
        df_manual = pd.DataFrame([{
            "Data": date.today().strftime('%Y-%m-%d'), 
            "Sorteio": "", "1º": "", "2º": "", "3º": "", "4º": "", "5º": ""
        }], dtype=str)
        
        df_editado = st.data_editor(df_manual, num_rows="dynamic", use_container_width=True)
        
        if st.button("💾 SALVAR DADOS MANUAIS", use_container_width=True):
            with st.spinner("Formatando e Gravando..."):
                dados_limpos = []
                for row in df_editado.values.tolist():
                    if str(row[1]).strip() != "" and str(row[1]).strip() != "nan":
                        linha_formatada = [str(row[0]).strip(), str(row[1]).strip()]
                        
                        # Blinda cada milhar, remove ".0" se o pandas tiver convertido, e força 4 zeros
                        for val in row[2:7]:
                            v_str = str(val).replace(".0", "").strip()
                            if v_str == "nan" or v_str == "":
                                linha_formatada.append("")
                            else:
                                linha_formatada.append(v_str.zfill(4)) # Transforma 911 em 0911
                                
                        dados_limpos.append(linha_formatada)
                
                if dados_limpos:
                    sh = conectar_sheets()
                    if sh:
                        ws = sh.worksheet(MAPA_ABAS[banca_sel])
                        # value_input_option="RAW" impede o Sheets de deletar o zero inicial
                        ws.append_rows(dados_limpos, value_input_option="RAW")
                        st.success(f"✅ {len(dados_limpos)} sorteio(s) manuais inseridos perfeitamente!")
                else:
                    st.warning("Preencha ao menos o campo 'Sorteio' e os prêmios para salvar.")

# =============================================================================
# --- 5. TELA 2: CONSELHEIRO TÁTICO ---
# =============================================================================
elif menu == "🔮 Conselheiro Tático (IA)":
    st.title("🔮 Inteligência Artificial de Combate")
    st.markdown("Análise profunda de **Grupos** e **Unidades de Milhar** baseada no seu histórico.")
    
    link_csv = st.text_input("🔗 Link Público CSV do Google Sheets:")
    
    if link_csv:
        if st.button("Gerar Relatórios de Ataque", use_container_width=True):
            with st.spinner("Varrendo histórico e fatiando milhares..."):
                try:
                    df = pd.read_csv(link_csv, header=None)
                    df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
                    
                    def get_grupo(m):
                        try:
                            d = int(str(m)[-2:])
                            return "25" if d == 0 else str(math.ceil(d/4)).zfill(2)
                        except: return None
                    
                    atr_g = {str(i).zfill(2): {'t': 0, 'max': 0} for i in range(1, 26)}
                    atr_um = {str(i): {'t': 0, 'max': 0} for i in range(10)} 
                    
                    for i in range(len(df)):
                        m_str = str(df.iloc[i]["P1"]).zfill(4)
                        if m_str == "nan" or "---" in m_str: continue
                        
                        g_val = get_grupo(m_str)
                        um_val = m_str[0]
                        
                        if g_val:
                            for k in atr_g:
                                atr_g[k]['t'] = 0 if k == g_val else atr_g[k]['t'] + 1
                                if atr_g[k]['t'] > atr_g[k]['max']: atr_g[k]['max'] = atr_g[k]['t']
                        for k in atr_um:
                            atr_um[k]['t'] = 0 if k == um_val else atr_um[k]['t'] + 1
                            if atr_um[k]['t'] > atr_um[k]['max']: atr_um[k]['max'] = atr_um[k]['t']

                    ult_m = str(df.iloc[-1]["P1"]).zfill(4)
                    ult_g = get_grupo(ult_m)
                    
                    prox_g, prox_um = [], []
                    for i in range(len(df)-1):
                        if get_grupo(str(df.iloc[i]["P1"]).zfill(4)) == ult_g:
                            p_m = str(df.iloc[i+1]["P1"]).zfill(4)
                            prox_g.append(get_grupo(p_m))
                            prox_um.append(p_m[0])
                            
                    t_g = pd.Series(prox_g).mode()[0] if prox_g else "N/A"
                    t_um = pd.Series(prox_um).mode()[0] if prox_um else "N/A"

                    st.success(f"Base Carregada! Analisando após: {ult_m} (Grupo {ult_g})")

                    st.markdown(f"""
                    <div class="card-tatico">
                        <div class="titulo-card">🔮 1. Previsor Markov (Próximo Sorteio no 1º Prêmio)</div>
                        Historicamente, após o Grupo <b>{ult_g}</b> sair, a banca costuma soltar:<br><br>
                        <span class="label-destaque">🎯 GRUPO ALVO:</span> <span class="dado-destaque">{t_g}</span><br>
                        <span class="label-destaque">🎯 UNIDADE DE MILHAR ALVO (1º Dígito):</span> <span class="dado-destaque">{t_um}</span>
                    </div>
                    """, unsafe_allow_html=True)

                    def gerar_alertas(dic, pref):
                        alertas = []
                        for k, v in dic.items():
                            if v['t'] > 0 and v['t'] >= (v['max'] - 2):
                                alertas.append(f"• {pref} **{k}** <span class='sub-dado'>(Atraso: {v['t']} | Recorde: {v['max']})</span>")
                        return "<br>".join(alertas) if alertas else "Tudo sob controle."

                    al_g = gerar_alertas(atr_g, "Grupo")
                    al_um = gerar_alertas(atr_um, "Unid. Milhar")

                    st.markdown(f"""
                    <div class="card-alerta">
                        <div class="titulo-card" style="color:#ff4b4b;">⏳ 2. Alerta de Ponto Crítico (Ruptura)</div>
                        Alvos em zona de risco (perto do recorde máximo de atraso):<br><br>
                        <div style="color:#fff;">
                        <b style="color:#ffb74d;">🦁 GRUPOS:</b><br>{al_g}<br><br>
                        <b style="color:#ffb74d;">🥇 UNIDADES DE MILHAR (1º Dígito):</b><br>{al_um}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Erro no processamento: {e}")
