import streamlit as st
import pandas as pd
from collections import Counter
import gspread
from google.oauth2.service_account import Credentials
import requests
from datetime import datetime, timedelta
import pytz
import time
import base64
import re
from bs4 import BeautifulSoup 

# =============================================================================
# --- 1. CONFIGURAÇÕES VISUAIS E SOM ---
# =============================================================================
st.set_page_config(page_title="BICHOS da LOTECA", page_icon="🦅", layout="wide")

# CONFIGURAÇÃO DE PAGAMENTO
COTACAO_GRUPO = 23.0 

# --- CENTRAL DE CONFIGURAÇÃO ---
CONFIG_BANCAS = {
    "LOTEP": {
        "display_name": "LOTEP PARAÍBA",
        "logo_url": "https://cdn-icons-png.flaticon.com/512/731/731985.png", 
        "cor_fundo": "#003366", 
        "cor_texto": "#ffffff",
        "card_bg": "rgba(255, 255, 255, 0.1)",
        "url_site": "https://www.resultadofacil.com.br/resultados-lotep-de-hoje",
        "horarios": {
            "segsab": "10:45 🔹 12:45 🔹 15:45 🔹 18:00",
            "dom": "10:00 🔹 12:45"
        }
    },
    "CAMINHODASORTE": {
        "display_name": "CAMINHO DA SORTE",
        "logo_url": "https://cdn-icons-png.flaticon.com/512/732/732220.png", 
        "cor_fundo": "#054a29", 
        "cor_texto": "#ffffff",
        "card_bg": "rgba(255, 255, 255, 0.1)",
        "url_site": "https://www.resultadofacil.com.br/resultados-caminho-da-sorte-de-hoje",
        "horarios": {
            "segsab": "09:40 🔹 11:00 🔹 12:40 🔹 14:00 🔹 15:40 🔹 17:00 🔹 18:30 🔹 20:00 🔹 21:00",
            "dom": "09:40 🔹 11:00 🔹 12:40"
        }
    },
    "MONTECAI": {
        "display_name": "MONTE CARLOS",
        "logo_url": "https://cdn-icons-png.flaticon.com/512/732/732217.png", 
        "cor_fundo": "#b71c1c", 
        "cor_texto": "#ffffff",
        "card_bg": "rgba(255, 255, 255, 0.1)",
        "url_site": "https://www.resultadofacil.com.br/resultados-nordeste-monte-carlos-de-hoje",
        "horarios": {
            "segsab": "10:00 🔹 11:00 🔹 12:40 🔹 14:00 🔹 15:40 🔹 17:00 🔹 18:30 🔹 21:00",
            "dom": "10:00 🔹 11:00 🔹 12:40"
        }
    }
}

BANCA_OPCOES = list(CONFIG_BANCAS.keys())

# Estados de Som
if 'tocar_som_salvar' not in st.session_state: st.session_state['tocar_som_salvar'] = False
if 'tocar_som_apagar' not in st.session_state: st.session_state['tocar_som_apagar'] = False
if 'auto_grupo' not in st.session_state: st.session_state['auto_grupo'] = 1
if 'auto_horario_idx' not in st.session_state: st.session_state['auto_horario_idx'] = 0

def reproduzir_som(tipo):
    if tipo == 'sucesso':
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=success-1-6297.mp3"
    elif tipo == 'alerta':
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/09/audio_0083556434.mp3?filename=error-2-126514.mp3"
    else:
        sound_url = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3?filename=crumpling-paper-1-6240.mp3"
    st.markdown(f"""<audio autoplay style="display:none;"><source src="{sound_url}" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

def aplicar_estilo_banca(banca_key):
    config = CONFIG_BANCAS.get(banca_key)
    bg_color = config["cor_fundo"]
    text_color = config["cor_texto"]
    card_bg = config["card_bg"]

    st.markdown(f"""
    <style>
        [data-testid="stAppViewContainer"] {{ background-color: {bg_color}; transition: background-color 0.5s; }}
        h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {{ color: {text_color} !important; }}
        .stNumberInput input {{ color: white !important; caret-color: white !important; }}
        .stSelectbox div[data-baseweb="select"] > div {{ color: black !important; }}
        [data-testid="stTable"] {{ background-color: transparent !important; color: white !important; }}
        thead tr th {{ color: {text_color} !important; text-align: center !important; border-bottom: 1px solid rgba(255,255,255,0.3) !important; }}
        tbody tr td {{ color: {text_color} !important; text-align: center !important; border-bottom: 1px solid rgba(255,255,255,0.1) !important; }}
        .metric-card {{ background-color: {card_bg}; padding: 10px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.2); text-align: center; }}
        
        .bola-verde {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #28a745; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-azul {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #17a2b8; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-cinza {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #555; color: #ccc !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #777; }}
        .bola-25 {{ display: inline-block; width: 40px; height: 40px; line-height: 40px; border-radius: 50%; background-color: white; color: black !important; text-align: center; font-weight: bold; margin: 2px; border: 3px solid #d4af37; box-shadow: 0px 0px 10px #d4af37; }}
        
        .bola-b {{ display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #17a2b8; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #fff; }}
        .bola-m {{ display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #fd7e14; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #fff; }}
        .bola-a {{ display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #dc3545; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #fff; }}
    </style>
    """, unsafe_allow_html=True)

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
        except: return None
    return None

def carregar_dados(worksheet):
    if worksheet:
        valores = worksheet.col_values(1)
        grupos = [int(v) for v in valores if v.isdigit()]
        try:
            horarios = worksheet.col_values(2)
            ultimo_horario = horarios[-1] if horarios else ""
        except: ultimo_horario = ""
        return grupos, ultimo_horario
    return [], ""

def salvar_na_nuvem(worksheet, dados_jogo, horario):
    if worksheet:
        try:
            data_hoje = datetime.now().strftime("%Y-%m-%d")
            linha = [int(dados_jogo), str(horario), data_hoje]
            worksheet.append_row(linha)
            return True
        except: return False
    return False

def deletar_ultimo_registro(worksheet):
    if worksheet:
        try:
            todos = worksheet.get_all_values()
            total_linhas = len(todos)
            if total_linhas > 0:
                worksheet.delete_rows(total_linhas)
                return True
        except: return False
    return False

# =============================================================================
# --- 3. LÓGICA DO ROBÔ ---
# =============================================================================
def html_bolas(lista, cor="verde"):
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
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            datas = [hoje.strftime("%d/%m/%Y"), hoje.strftime("%d-%m-%Y"), hoje.strftime("%d de")]
            for d in datas:
                if d in r.text: return True, "🟢 SITE ATUALIZADO", f"Data: {d}"
            return False, "🟡 DATA AUSENTE", "Site online, sem data de hoje."
        return False, "🔴 OFF", "Erro site."
    except: return False, "🔴 ERRO", "Falha conexão."

def raspar_ultimo_resultado_real(url, banca_key):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code != 200: return None, None, "Erro Site"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        # Lógica simplificada
        candidatos = []
        tabelas = soup.find_all('table')
        for tabela in tabelas:
            if "1º" in tabela.get_text() or "Pri" in tabela.get_text():
                horario_str = "00:00"
                prev = tabela.find_previous(string=re.compile(r'\d{2}:\d{2}'))
                if prev: 
                    m = re.search(r'(\d{2}:\d{2})', prev)
                    if m: horario_str = m.group(1)
                linhas = tabela.find_all('tr')
                for linha in linhas:
                    colunas = linha.find_all('td')
                    if len(colunas) >= 3:
                        premio = colunas[0].get_text().strip()
                        if any(x in premio for x in ['1º', '1', 'Pri']):
                            grp = colunas[2].get_text().strip()
                            if grp.isdigit():
                                candidatos.append((horario_str, int(grp)))
                                break
        if not candidatos: return None, None, "Não encontrado"
        return candidatos[0][1], candidatos[0][0], "Sucesso"
    except Exception as e: return None, None, f"Erro: {e}"

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

def gerar_palpite_estrategico(historico):
    todos_forca = calcular_ranking_forca_completo(historico)
    return todos_forca[:12]

# --- LÓGICA DE CICLOS (NOVO) ---
def analisar_ciclo_atual(historico):
    if not historico: return [], 0, [], 0
    ciclos_fechados = []
    conjunto_atual = set()
    inicio_ciclo = 0
    
    for i, bicho in enumerate(historico):
        conjunto_atual.add(bicho)
        if len(conjunto_atual) == 25:
            duracao = i - inicio_ciclo + 1
            ciclos_fechados.append(duracao)
            conjunto_atual = set()
            inicio_ciclo = i + 1
            
    # Estado atual
    faltam_sair = list(set(range(1, 26)) - conjunto_atual)
    faltam_sair.sort()
    duracao_atual = len(historico) - inicio_ciclo
    
    return faltam_sair, duracao_atual, ciclos_fechados, len(conjunto_atual)

def gerar_backtest_e_status(historico):
    if len(historico) < 30: return pd.DataFrame(), 0, 0, 0, 0
    resultados = []
    
    # AJUSTE: Mostrar os últimos 25 jogos na tabela
    inicio = max(0, len(historico) - 25)
    
    max_loss = 0; temp_loss = 0; max_win = 0; temp_win = 0
    inicio_risk = max(0, len(historico) - 50)
    for i in range(inicio_risk, len(historico)):
        saiu = historico[i]
        passado = historico[:i]
        p_princ = gerar_palpite_estrategico(passado)
        if saiu not in p_princ:
            temp_loss += 1; temp_win = 0
        else:
            temp_win += 1; temp_loss = 0
        if temp_loss > max_loss: max_loss = temp_loss
        if temp_win > max_win: max_win = temp_win
    
    for i in range(inicio, len(historico)):
        saiu = historico[i]
        passado = historico[:i]
        p_princ = gerar_palpite_estrategico(passado)
        status = "❌"
        if saiu in p_princ: status = "💚"
        resultados.append({"JOGO": f"#{len(historico)-i}", "SAIU": f"{saiu:02}", "TOP 12": status})
    
    curr_streak = 0; curr_win_streak = 0
    for res in reversed(resultados):
        if res["TOP 12"] == "❌": curr_streak += 1
        else: break
    for res in reversed(resultados):
        if res["TOP 12"] == "💚": curr_win_streak += 1
        else: break
    return pd.DataFrame(resultados[::-1]), curr_streak, max_loss, max_win, curr_win_streak

def analisar_setores_bma_com_maximo(historico):
    if not historico: return {}, {}, [], []
    setor_b = list(range(1, 9))
    setor_m = list(range(9, 17))
    setor_a = list(range(17, 25))
    setor_25 = [25]
    def calcular_atrasos(lista_alvo, hist):
        atraso_atual = 0; max_atraso = 0; contador_temp = 0
        for x in reversed(hist):
            if x in lista_alvo: break
            atraso_atual += 1
        for x in hist:
            if x not in lista_alvo: contador_temp += 1
            else:
                if contador_temp > max_atraso: max_atraso = contador_temp
                contador_temp = 0
        if contador_temp > max_atraso: max_atraso = contador_temp
        return atraso_atual, max_atraso
    def calcular_max_sequencia(lista_alvo, hist):
        max_seq = 0; curr_seq = 0
        for x in hist:
            if x in lista_alvo: curr_seq += 1
            else:
                if curr_seq > max_seq: max_seq = curr_seq
                curr_seq = 0
        if curr_seq > max_seq: max_seq = curr_seq
        return max_seq
    
    curr_b, max_b_loss = calcular_atrasos(setor_b, historico)
    curr_m, max_m_loss = calcular_atrasos(setor_m, historico)
    curr_a, max_a_loss = calcular_atrasos(setor_a, historico)
    curr_25, max_25_loss = calcular_atrasos(setor_25, historico)
    
    max_b_win = calcular_max_sequencia(setor_b, historico)
    max_m_win = calcular_max_sequencia(setor_m, historico)
    max_a_win = calcular_max_sequencia(setor_a, historico)
    max_25_win = calcular_max_sequencia(setor_25, historico)
    
    df_setores = pd.DataFrame([
        {"SETOR": "BAIXO (01-08)", "ATRASO": curr_b, "REC. ATRASO": max_b_loss, "REC. SEQ. (V)": max_b_win},
        {"SETOR": "MÉDIO (09-16)", "ATRASO": curr_m, "REC. ATRASO": max_m_loss, "REC. SEQ. (V)": max_m_win},
        {"SETOR": "ALTO (17-24)", "ATRASO": curr_a, "REC. ATRASO": max_a_loss, "REC. SEQ. (V)": max_a_win},
        {"SETOR": "VACA (25)", "ATRASO": curr_25, "REC. ATRASO": max_25_loss, "REC. SEQ. (V)": max_25_win}
    ])
    
    sequencia_visual = []
    for x in historico[::-1][:12]:
        if x == 25: sigla, classe = "25", "bola-25"
        elif x <= 8: sigla, classe = "B", "bola-b"
        elif x <= 16: sigla, classe = "M", "bola-m"
        else: sigla, classe = "A", "bola-a"
        sequencia_visual.append((sigla, classe))
    return df_setores, sequencia_visual

def analisar_dna_fixo_historico(historico):
    if len(historico) < 50: return [], pd.DataFrame(), 0, 0, 0, 0
    contagem_total = Counter(historico)
    top_12_fixo = [g for g, freq in contagem_total.most_common(12)]
    max_loss = 0; temp_loss = 0; max_win = 0; temp_win = 0
    inicio_risk = max(0, len(historico) - 50)
    for i in range(inicio_risk, len(historico)):
        if historico[i] not in top_12_fixo: 
            temp_loss += 1; temp_win = 0
        else:
            temp_win += 1; temp_loss = 0
        if temp_loss > max_loss: max_loss = temp_loss
        if temp_win > max_win: max_win = temp_win
    
    resultados_simulacao = []
    # AJUSTE: Mostrar 25 jogos na tabela Bunker
    for i, saiu in enumerate(historico[-25:]):
        status = "❌"
        if saiu in top_12_fixo: status = "💚"
        resultados_simulacao.insert(0, {"JOGO": f"Ult-{25-i}", "SAIU": f"{saiu:02}", "BUNKER 12": status})
        
    curr_streak = 0; curr_win_streak = 0
    for res in resultados_simulacao: 
        if res["BUNKER 12"] == "❌": curr_streak += 1
        else: break
    for res in resultados_simulacao:
        if res["BUNKER 12"] == "💚": curr_win_streak += 1
        else: break
    return top_12_fixo, pd.DataFrame(resultados_simulacao), max_loss, curr_streak, max_win, curr_win_streak

def gerar_palpite_setorizado(historico):
    ranking = calcular_ranking_forca_completo(historico)
    setor_b = [g for g in ranking if 1 <= g <= 8]
    setor_m = [g for g in ranking if 9 <= g <= 16]
    setor_a = [g for g in ranking if 17 <= g <= 25] 
    top4_b = setor_b[:4]; top4_m = setor_m[:4]; top4_a = setor_a[:4]
    palpite = top4_b + top4_m + top4_a
    palpite.sort()
    return palpite

def gerar_backtest_setorizado(historico):
    if len(historico) < 30: return pd.DataFrame(), [], 0, 0, 0, 0
    resultados = []
    # AJUSTE: Mostrar 25 jogos na tabela Setorizada
    inicio = max(0, len(historico) - 25)
    
    lista_atual = gerar_palpite_setorizado(historico)
    max_derrotas = 0; temp_derrotas = 0; max_win = 0; temp_win = 0
    inicio_risk = max(0, len(historico) - 50)
    for i in range(inicio_risk, len(historico)):
        saiu = historico[i]
        passado = historico[:i]
        pulp = gerar_palpite_setorizado(passado)
        if saiu not in pulp:
            temp_derrotas += 1; temp_win = 0
        else:
            temp_win += 1; temp_derrotas = 0
        if temp_derrotas > max_derrotas: max_derrotas = temp_derrotas
        if temp_win > max_win: max_win = temp_win
        
    for i in range(inicio, len(historico)):
        saiu = historico[i]
        passado = historico[:i]
        palpite_da_epoca = gerar_palpite_setorizado(passado)
        status = "❌"
        if saiu in palpite_da_epoca: status = "💚"
        resultados.append({"JOGO": f"#{len(historico)-i}", "SAIU": f"{saiu:02}", "RES (4x4x4)": status})
        
    curr_streak = 0; curr_win_streak = 0
    for res in reversed(resultados):
        if res["RES (4x4x4)"] == "❌": curr_streak += 1
        else: break
    for res in reversed(resultados):
        if res["RES (4x4x4)"] == "💚": curr_win_streak += 1
        else: break
    return pd.DataFrame(resultados[::-1]), lista_atual, max_derrotas, curr_streak, max_win, curr_win_streak

def identificar_bma_crise_tendencia(historico):
    if not historico: return [], "", ""
    mapa_setores = {"BAIXO": list(range(1, 9)), "MÉDIO": list(range(9, 17)), "ALTO": list(range(17, 25))}
    atrasos = {"BAIXO": 0, "MÉDIO": 0, "ALTO": 0}
    for nome, nums in mapa_setores.items():
        cnt = 0
        for x in reversed(historico):
            if x in nums: break
            cnt += 1
        atrasos[nome] = cnt
    setor_crise = max(atrasos, key=atrasos.get)
    recorte = historico[-10:]
    freqs = {"BAIXO": 0, "MÉDIO": 0, "ALTO": 0}
    for x in recorte:
        if 1 <= x <= 8: freqs["BAIXO"] += 1
        elif 9 <= x <= 16: freqs["MÉDIO"] += 1
        elif 17 <= x <= 24: freqs["ALTO"] += 1
    setor_tendencia = max(freqs, key=freqs.get)
    
    ranking_geral = calcular_ranking_forca_completo(historico)
    def filtrar_top6(setor_nome):
        candidatos = mapa_setores[setor_nome]
        candidatos_ordenados = sorted(candidatos, key=lambda x: ranking_geral.index(x) if x in ranking_geral else 99)
        return candidatos_ordenados[:6]
    top6_crise = filtrar_top6(setor_crise)
    top6_tendencia = filtrar_top6(setor_tendencia)
    palpite = list(set(top6_crise + top6_tendencia))
    palpite.sort()
    return palpite, setor_crise, setor_tendencia

def gerar_backtest_bma(historico):
    resultados = []
    palpite_atual, crise, trend = identificar_bma_crise_tendencia(historico)
    max_loss = 0; temp_loss = 0; max_win = 0; temp_win = 0
    inicio_risk = max(0, len(historico) - 50)
    for i in range(inicio_risk, len(historico)):
        saiu = historico[i]
        passado = historico[:i]
        pulp, _, _ = identificar_bma_crise_tendencia(passado)
        if saiu not in pulp:
            temp_loss += 1; temp_win = 0
        else:
            temp_win += 1; temp_loss = 0
        if temp_loss > max_loss: max_loss = temp_loss
        if temp_win > max_win: max_win = temp_win
        
    # AJUSTE: Mostrar 25 jogos na tabela BMA
    inicio = max(0, len(historico) - 25)
    
    for i in range(inicio, len(historico)):
        saiu = historico[i]
        passado = historico[:i]
        palpite_epoca, _, _ = identificar_bma_crise_tendencia(passado)
        status = "❌"
        if saiu in palpite_epoca: status = "💚"
        resultados.append({"JOGO": f"#{len(historico)-i}", "SAIU": f"{saiu:02}", "BMA (C+T)": status})
        
    curr_streak = 0; curr_win_streak = 0
    for res in reversed(resultados):
        if res["BMA (C+T)"] == "❌": curr_streak += 1
        else: break
    for res in reversed(resultados):
        if res["BMA (C+T)"] == "💚": curr_win_streak += 1
        else: break
    return pd.DataFrame(resultados[::-1]), palpite_atual, crise, trend, max_loss, curr_streak, max_win, curr_win_streak

def calcular_inverso(palpite):
    universo = set(range(1, 26))
    palpite_set = set(palpite)
    inverso = list(universo - palpite_set)
    inverso.sort()
    return inverso

def monitorar_oportunidades(historico):
    alertas = []; tipos = []; sugestoes = []
    
    # 1. Top 12
    _, curr_loss_12, max_loss_12, max_win_12, curr_win_12 = gerar_backtest_e_status(historico)
    palp_12 = gerar_palpite_estrategico(historico)
    if curr_loss_12 >= (max_loss_12 - 1) and curr_loss_12 > 0:
        alertas.append(f"⚡ TOP 12: Derrotas ({curr_loss_12}) perto do Recorde ({max_loss_12})!"); tipos.append("erro"); sugestoes.append(None)
    if curr_win_12 >= (max_win_12 - 1) and curr_win_12 > 0:
        alertas.append(f"🛑 TOP 12: {curr_win_12} Vitórias. Perto do Recorde ({max_win_12})!"); tipos.append("aviso"); sugestoes.append(calcular_inverso(palp_12))
        
    # 2. Bunker
    palp_bunker, _, max_loss_bun, curr_loss_bun, max_win_bun, curr_win_bun = analisar_dna_fixo_historico(historico)
    if curr_loss_bun >= (max_loss_bun - 1) and curr_loss_bun > 0:
        alertas.append(f"🛡️ BUNKER: Derrotas ({curr_loss_bun}) perto do Recorde ({max_loss_bun})!"); tipos.append("erro"); sugestoes.append(None)
    if curr_win_bun >= (max_win_bun - 1) and curr_win_bun > 0:
        alertas.append(f"🛑 BUNKER: {curr_win_bun} Vitórias. Perto do Recorde ({max_win_bun})!"); tipos.append("aviso"); sugestoes.append(calcular_inverso(palp_bunker))
        
    # 3. BMA
    _, palp_bma, _, _, risk_bma, curr_loss_bma, max_win_bma, curr_win_bma = gerar_backtest_bma(historico)
    if curr_loss_bma >= (risk_bma - 1) and curr_loss_bma > 0:
        alertas.append(f"🔥 BMA: Derrotas ({curr_loss_bma}) perto do Recorde ({risk_bma})!"); tipos.append("erro"); sugestoes.append(None)
    if curr_win_bma >= (max_win_bma - 1) and curr_win_bma > 0:
        alertas.append(f"🛑 BMA: {curr_win_bma} Vitórias. Perto do Recorde ({max_win_bma})!"); tipos.append("aviso"); sugestoes.append(calcular_inverso(palp_bma))
        
    # 4. Setorizada
    _, palp_set, risk_set, curr_loss_set, max_win_set, curr_win_set = gerar_backtest_setorizado(historico)
    if curr_loss_set >= (risk_set - 1) and curr_loss_set > 0:
        alertas.append(f"⚖️ SETORIZADA: Derrotas ({curr_loss_set}) perto do Recorde ({risk_set})!"); tipos.append("erro"); sugestoes.append(None)
    if curr_win_set >= (max_win_set - 1) and curr_win_set > 0:
        alertas.append(f"🛑 SETORIZADA: {curr_win_set} Vitórias. Perto do Recorde ({max_win_set})!"); tipos.append("aviso"); sugestoes.append(calcular_inverso(palp_set))
        
    return alertas, tipos, sugestoes

# =============================================================================
# --- 6. INTERFACE PRINCIPAL ---
# =============================================================================

if st.session_state['tocar_som_salvar']: reproduzir_som('sucesso'); st.session_state['tocar_som_salvar'] = False
if st.session_state['tocar_som_apagar']: reproduzir_som('apagar'); st.session_state['tocar_som_apagar'] = False

with st.sidebar:
    st.header("🦅 MENU DE JOGO")
    banca_selecionada = st.selectbox("Selecione a Banca:", BANCA_OPCOES)
    config_banca = CONFIG_BANCAS[banca_selecionada]
    
    fuso_br = pytz.timezone('America/Sao_Paulo')
    dia_semana = datetime.now(fuso_br).weekday()
    lista_horarios_str = config_banca['horarios']['dom'] if dia_semana == 6 else config_banca['horarios']['segsab']
    lista_horarios = [h.strip() for h in lista_horarios_str.split('🔹')]
    
    if st.session_state.get('auto_horario_idx', 0) >= len(lista_horarios):
        st.session_state['auto_horario_idx'] = 0
    
    st.markdown("---")
    
    c1_imp, c2_link = st.columns(2)
    with c1_imp:
        if st.button("📡 Importar"):
            with st.spinner("Buscando dados..."):
                grp, hor, msg = raspar_ultimo_resultado_real(config_banca['url_site'], banca_selecionada)
                if grp:
                    st.success(f"G{grp:02} às {hor}")
                    st.session_state['auto_grupo'] = grp
                    if hor in lista_horarios:
                        st.session_state['auto_horario_idx'] = lista_horarios.index(hor)
                else:
                    st.error(f"Erro: {msg}")
    
    with c2_link:
        st.link_button("🔗 Ver Site", config_banca['url_site'])
    
    st.write("📝 **Registrar Sorteio**")
    novo_horario = st.selectbox("Horário:", lista_horarios, index=st.session_state.get('auto_horario_idx', 0))
    novo_bicho = st.number_input("Grupo:", 1, 25, st.session_state.get('auto_grupo', 1))
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 SALVAR", type="primary"):
            aba = conectar_planilha(banca_selecionada)
            if aba and salvar_na_nuvem(aba, novo_bicho, novo_horario):
                st.session_state['tocar_som_salvar'] = True
                st.toast("Salvo! 🔔", icon="✅"); time.sleep(0.5); st.rerun()
    with col_btn2:
        if st.button("🔄 REBOOT"): st.rerun()
            
    with st.expander("🗑️ Área de Perigo"):
        if st.button("APAGAR ÚLTIMO"):
            aba = conectar_planilha(banca_selecionada)
            if aba and deletar_ultimo_registro(aba):
                st.session_state['tocar_som_apagar'] = True
                st.toast("Apagado! 🗑️", icon="🗑️"); time.sleep(0.5); st.rerun()

aba_ativa = conectar_planilha(banca_selecionada)

if aba_ativa:
    historico, ultimo_horario_salvo = carregar_dados(aba_ativa)
    
    if len(historico) > 0:
        aplicar_estilo_banca(banca_selecionada)
        config_atual = CONFIG_BANCAS[banca_selecionada]
        
        # --- PROCESSAMENTO ---
        df_top12, curr_loss_12, max_loss_12, max_win_12, curr_win_12 = gerar_backtest_e_status(historico)
        palp_top12 = gerar_palpite_estrategico(historico)
        
        df_setores, seq_visual = analisar_setores_bma_com_maximo(historico)
        
        lista_bunker, df_bunker, max_loss_bun, curr_loss_bun, max_win_bun, curr_win_bun = analisar_dna_fixo_historico(historico)
        
        df_setor, lista_setor, risk_setor, curr_loss_set, max_win_set, curr_win_set = gerar_backtest_setorizado(historico)
        
        df_bma, palp_bma, crise_bma, trend_bma, risk_bma, curr_loss_bma, max_win_bma, curr_win_bma = gerar_backtest_bma(historico)
        
        # --- CICLOS ---
        bichos_faltantes, duracao_ciclo, historico_ciclos, progresso_ciclo = analisar_ciclo_atual(historico)
        
        alertas, tipos, sugestoes = monitorar_oportunidades(historico)

        # Cabeçalho
        col_head1, col_head2 = st.columns([1, 4])
        with col_head1: st.image(config_atual['logo_url'], width=80)
        with col_head2:
            st.markdown(f"## {config_atual['display_name']}")
            st.caption(f"Último: Grupo {historico[-1]:02} | Hora: {ultimo_horario_salvo}")

        site_on, site_tit, _ = verificar_atualizacao_site(config_atual['url_site'])
        if not site_on: st.warning(f"Status do Site: {site_tit}")

        # --- PAINEL DE ALERTAS ---
        if alertas:
            with st.expander("🚨 CENTRO DE ALERTAS", expanded=True):
                for i, alerta in enumerate(alertas):
                    if tipos[i] == "erro": st.error(alerta)
                    else: st.warning(alerta)
                    if sugestoes[i]:
                        st.info("👻 **MODO INVERSO (Os 13 do Contra):**")
                        # Lista copiável
                        txt_inv = ", ".join([f"{n:02}" for n in sugestoes[i]])
                        st.code(txt_inv, language="text")

        # --- ABAS PRINCIPAIS ---
        tab_setores, tab_comp, tab_ciclos = st.tabs(["🎯 Setores & Estratégias", "🆚 Comparativo (2 Mesas)", "🔄 Ciclos"])
        
        with tab_setores:
            st.write("Visual Recente (⬅️ Mais Novo):")
            html_seq = "<div>"
            for sigla, classe in seq_visual: html_seq += f"<div class='{classe}'>{sigla}</div>"
            html_seq += "</div>"
            st.markdown(html_seq, unsafe_allow_html=True)
            st.markdown("---")
            st.write("📊 **Tabela de Stress (Atraso vs Recorde):**")
            st.table(df_setores)
            
            c_strat1, c_strat2 = st.columns(2)
            with c_strat1:
                st.write("🔥 **Estratégia 1: BMA (Crise + Tendência)**")
                st.caption(f"Foco: {crise_bma} + {trend_bma}")
                st.table(df_bma)
                st.warning(f"⚠️ Rec. Derrotas: {risk_bma} | 🏆 Rec. Vitórias: {max_win_bma}")
                with st.expander("Ver Palpite BMA"): st.markdown(html_bolas(palp_bma, "verde"), unsafe_allow_html=True)
                
            with c_strat2:
                st.write("⚖️ **Estratégia 2: Setorizada (4x4x4)**")
                st.caption("Equilíbrio dos 3 setores")
                st.table(df_setor)
                st.warning(f"⚠️ Rec. Derrotas: {risk_setor} | 🏆 Rec. Vitórias: {max_win_set}")
                with st.expander("Ver Palpite Setorizada"): st.markdown(html_bolas(lista_setor, "verde"), unsafe_allow_html=True)

        with tab_comp:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🔥 Top 12 (Dinâmico)")
                st.caption("Baseado na frequência recente")
                st.table(df_top12)
                st.warning(f"⚠️ Rec. Derrotas: {max_loss_12} | 🏆 Rec. Vitórias: {max_win_12}")
                with st.expander("Ver Palpite Top 12"): st.markdown(html_bolas(palp_top12, "verde"), unsafe_allow_html=True)
                
            with col2:
                st.subheader("🧬 Bunker 12 (Fixo)")
                st.caption("Baseado na frequência histórica total")
                st.table(df_bunker)
                st.warning(f"⚠️ Rec. Derrotas: {max_loss_bun} | 🏆 Rec. Vitórias: {max_win_bun}")
                with st.expander("Ver Palpite Bunker"): st.markdown(html_bolas(lista_bunker, "azul"), unsafe_allow_html=True)
        
        with tab_ciclos:
            st.subheader("🔄 Monitor de Ciclos (1-25)")
            st.write(f"**Status Atual:** {progresso_ciclo} de 25 bichos já saíram.")
            st.progress(progresso_ciclo / 25)
            
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.metric("Jogos no Ciclo Atual", f"{duracao_ciclo} Jogos")
            with col_c2:
                if historico_ciclos:
                    avg_ciclo = sum(historico_ciclos) / len(historico_ciclos)
                    st.metric("Média Histórica para Fechar", f"{avg_ciclo:.1f} Jogos")
            
            st.markdown("### 🎯 Faltam Sair (Sugestão de Jogo):")
            if bichos_faltantes:
                txt_ciclo = ", ".join([f"{n:02}" for n in bichos_faltantes])
                st.code(txt_ciclo, language="text")
            else:
                st.success("O ciclo acabou de fechar! Um novo começou agora.")

        st.markdown("---")
        with st.expander("🕒 Grade de Horários da Banca"):
            st.write(config_atual['horarios'])

    else:
        st.warning("⚠️ Planilha vazia. Adicione o primeiro resultado.")
else:
    st.info("Conectando...")
