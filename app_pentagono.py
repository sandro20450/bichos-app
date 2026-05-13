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
# --- 1. CONFIGURAÇÕES, CSS E CONEXÃO ---
# =============================================================================
st.set_page_config(page_title="Pentágono V57.0 - Radar Total", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.flex-container { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-start; margin-bottom: 20px; }
.grupo-card-zebra { background-color: #1a0000; border: 1px solid #ff4b4b; border-radius: 6px; padding: 10px; text-align: center; flex: 1 1 80px; max-width: 100px; box-shadow: 0 4px 6px rgba(0,0,0,0.5); }
.grupo-numero { font-size: 24px; font-weight: bold; color: #ffffff; margin: 2px 0; }
.grupo-pontos-zebra { font-size: 12px; color: #ff4b4b; font-weight: bold; }
.grupo-posicao { font-size: 10px; color: #aaaaaa; text-transform: uppercase; }
.backtest-box { background-color: #0e1117; padding: 15px; border-radius: 8px; border-left: 5px solid #ff4b4b; margin-bottom: 15px; border-right: 1px solid #333; border-top: 1px solid #333; border-bottom: 1px solid #333;}
.gatilho-ativo { background-color: #001a00; border: 1px solid #00ff00; padding: 12px; margin-top: 10px; border-radius: 5px; color: #00ff00; font-weight: bold; text-align: center;}
.gatilho-espera { background-color: #1a1a1a; border: 1px solid #555555; padding: 12px; margin-top: 10px; border-radius: 5px; color: #aaaaaa; font-size: 13px; text-align: center;}
.banner-info { background-color: #000; border: 1px solid #4CAF50; padding: 12px; border-radius: 10px; text-align: center; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

MAPA_ABAS = {"Tradicional": "TRADICIONAL_MILHAR", "Caminho da Sorte": "CAMINHO_MILHAR", "Monte Carlos": "MONTE_MILHAR", "Lotep": "LOTEP_MILHAR"}
BANCAS_CONFIG = {
    "Tradicional": "https://playbicho.com/resultado-jogo-do-bicho/tradicional-do-dia-", 
    "Caminho da Sorte": "https://playbicho.com/resultado-jogo-do-bicho/caminho-da-sorte-do-dia-", 
    "Monte Carlos": "https://playbicho.com/resultado-jogo-do-bicho/nordeste-montes-claros-do-dia-", 
    "Lotep": "https://www.resultadofacil.com.br/resultados-lotep-do-dia-"
}

def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds).open("CentralBichos")
    except: return None

# =============================================================================
# 🚀 SISTEMA DE CACHE: Mantém a velocidade ultra rápida
# =============================================================================
@st.cache_data(ttl=600, show_spinner=False)
def carregar_dados_em_memoria(banca_nome):
    sh = conectar_sheets()
    if not sh: return pd.DataFrame()
    try:
        ws = sh.worksheet(MAPA_ABAS[banca_nome])
        dados = ws.get_all_values()
        if len(dados) < 2: return pd.DataFrame()
        df = pd.DataFrame(dados[1:])
        df = df.iloc[:, :7]
        df.columns = ["Data", "Sorteio", "P1", "P2", "P3", "P4", "P5"]
        df = df[df["P1"].astype(str).str.strip() != ""]
        return df
    except: return pd.DataFrame()

def exibir_banner_sorteio(df, banca):
    if not df.empty:
        ult_nome = str(df.iloc[-1]["Sorteio"])
        st.markdown(f"""
        <div class="banner-info">
            <span style='color: #4CAF50; font-size: 11px; font-weight: bold;'>📡 ÚLTIMA ATUALIZAÇÃO MONITORADA:</span><br>
            <span style='color: white; font-size: 18px; font-weight: bold;'>{banca} - {ult_nome}</span>
        </div>
        """, unsafe_allow_html=True)

def get_grupo_str(m):
    try:
        d = int(str(m)[-2:])
        return "25" if d == 0 else str(math.ceil(d/4)).zfill(2)
    except: return None

# =============================================================================
# --- MOTOR DE EXTRAÇÃO (PRESERVADO) ---
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
            th_tag = tab.find('th')
            txt_th = th_tag.get_text().upper() if th_tag else ""
            prev = tab.find_previous(['h2', 'h3', 'h4', 'strong', 'b'])
            txt_prev = prev.get_text().upper() if prev else ""
            texto_alvo = txt_th if re.search(r'\d{2}:\d{2}h?|\d{2}h', txt_th) else txt_prev
            if "FEDERAL" in texto_alvo.upper(): continue
            match_hora = re.search(r'(\d{2}):(\d{2})h?|(\d{2})h', texto_alvo, re.IGNORECASE)
            nome = f"{match_hora.group(3)}:00" if match_hora and match_hora.group(3) else (f"{match_hora.group(1)}:{match_hora.group(2)}" if match_hora else "Extra")
            milhares = []
            for row in tab.find_all('tr'):
                cols = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if cols and any(x in cols[0].lower() for x in ['1º', '2º', '3º', '4º', '5º', '1°', '2°', '3°', '4°', '5°']):
                    nums = re.findall(r'\d+', "".join(cols[1:]))
                    milhares.append(nums[0][:4].zfill(4) if nums and len(nums[0]) >= 3 else "----")
            if len(milhares) >= 5:
                resultados.append([data_alvo.strftime('%Y-%m-%d'), nome, milhares[0], milhares[1], milhares[2], milhares[3], milhares[4]])
        return resultados
    except: return []

# =============================================================================
# --- NOVA LÓGICA: RADAR ZEBRA 1º AO 5º ---
# =============================================================================
def calcular_ranking_cegos_1_ao_5(df_analise):
    # Dicionário para rastrear atraso atual e atraso máximo
    scores_tmp = {str(i).zfill(2): {'atraso_atual': 0, 'atraso_max': 0, 'total': 0} for i in range(1, 26)}
    
    for i in range(len(df_analise)):
        # Captura os 5 grupos que saíram neste sorteio
        sorteio_atual = [
            get_grupo_str(df_analise.iloc[i]["P1"]),
            get_grupo_str(df_analise.iloc[i]["P2"]),
            get_grupo_str(df_analise.iloc[i]["P3"]),
            get_grupo_str(df_analise.iloc[i]["P4"]),
            get_grupo_str(df_analise.iloc[i]["P5"])
        ]
        
        for g in scores_tmp:
            if g in sorteio_atual:
                # Se o grupo saiu em QUALQUER uma das 5 posições, zera o atraso
                scores_tmp[g]['atraso_atual'] = 0
            else:
                # Se não saiu, incrementa o atraso
                scores_tmp[g]['atraso_atual'] += 1
                
            # Atualiza o recorde de atraso histórico
            if scores_tmp[g]['atraso_atual'] > scores_tmp[g]['atraso_max']:
                scores_tmp[g]['atraso_max'] = scores_tmp[g]['atraso_atual']
                
    # O "Total" para o ranking é o atraso atual (Zebra)
    for g in scores_tmp:
        scores_tmp[g]['total'] = scores_tmp[g]['atraso_atual']
        
    ranking = sorted(scores_tmp.items(), key=lambda x: x[1]['total'], reverse=True)
    return [x[0] for x in ranking], scores_tmp

# =============================================================================
# --- INTERFACE DE COMANDO ---
# =============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2070/2070051.png", width=60)
    st.header("Pentágono V57.0")
    menu = st.radio("Selecione:", ["📊 Radar Zebra (1º ao 5º)", "📡 Extração Central"])

if menu == "📊 Radar Zebra (1º ao 5º)":
    st.title("🚨 Radar de Exclusão (1º ao 5º Prêmio)")
    st.info("Monitorando grupos que não aparecem em nenhuma das 5 primeiras posições.")
    banca_ia = st.selectbox("Selecione a Banca:", list(BANCAS_CONFIG.keys()))
    
    if st.button("VARREDURA TOTAL DE ATRASOS", use_container_width=True, type="primary"):
        with st.spinner("Analisando 1º ao 5º prêmio..."):
            df = carregar_dados_em_memoria(banca_ia)
            if not df.empty:
                exibir_banner_sorteio(df, banca_ia)
                
                # Análise Zebra focada nos últimos 400 sorteios para precisão
                df_radar = df.tail(400).reset_index(drop=True)
                ranking_final, scores = calcular_ranking_cegos_1_ao_5(df_radar)
                
                # Os 6 grupos mais atrasados (Zebra)
                cegos_atuais = ranking_final[:6]
                
                # Pega o bicho mais atrasado de todos para o destaque
                topo_zebra = cegos_atuais[0]
                atraso_topo = scores[topo_zebra]['atraso_atual']
                recorde_topo = scores[topo_zebra]['atraso_max']
                
                st.markdown(f"""
                <div class="backtest-box">
                    <b>Bicho em Alerta Máximo:</b> Grupo {topo_zebra}<br>
                    <b>Atraso Atual (1º-5º):</b> {atraso_topo} sorteios sem aparecer.<br>
                    <b>Recorde de Atraso nesta banca:</b> {recorde_topo} sorteios.
                </div>
                """, unsafe_allow_html=True)
                
                if atraso_topo >= (recorde_topo - 1) and atraso_topo > 0:
                    st.markdown(f'<div class="gatilho-ativo">🚀 GATILHO TÁTICO ATIVADO! Grupo {topo_zebra} atingiu o limite de exaustão!</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="gatilho-espera">⏳ Monitorando exaustão... (Próximo alvo provável: {topo_zebra})</div>', unsafe_allow_html=True)
                
                st.subheader("🏁 Os 6 Grupos Mais Atrasados (Zebra 1º-5º):")
                html = '<div class="flex-container">'
                for idx, g in enumerate(cegos_atuais):
                    pts = scores[g]['total']
                    html += f'<div class="grupo-card-zebra"><div class="grupo-posicao">{idx+1}º ZEBRA</div><div class="grupo-numero">{g}</div><div class="grupo-pontos-zebra">{pts} ATRASOS</div></div>'
                st.markdown(html + '</div>', unsafe_allow_html=True)
            else:
                st.error("Erro ao carregar base. Execute uma extração primeiro.")

elif menu == "📡 Extração Central":
    st.title("📡 Extração e Automação")
    banca_ex = st.selectbox("Banca para Extração:", list(BANCAS_CONFIG.keys()))
    dt = st.date_input("Data do Sorteio:", value=date.today())
    
    if st.button("🚀 INICIAR COLETA", use_container_width=True):
        with st.spinner("Acessando servidores externos..."):
            res = extrair_dia(banca_ex, dt)
            if res:
                sh = conectar_sheets()
                if sh:
                    ws = sh.worksheet(MAPA_ABAS[banca_ex])
                    existentes = ws.get_all_values()
                    set_exist = {f"{str(r[0]).strip()}_{str(r[1]).strip()}" for r in existentes if len(r) >= 2}
                    p_ins = [l for l in res if f"{str(l[0]).strip()}_{str(l[1]).strip()}" not in set_exist]
                    if p_ins: 
                        ws.append_rows(p_ins, value_input_option="RAW")
                        st.success(f"✅ Missão Cumprida: {len(p_ins)} novos registros salvos.")
                        carregar_dados_em_memoria.clear() # Limpa o cache para atualizar o radar
                    else:
                        st.info("Todos os dados já estão no banco de dados.")
            else: st.error("Nenhum resultado disponível para esta data.")
