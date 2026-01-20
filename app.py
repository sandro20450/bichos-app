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
if 'tocar_som_salvar' not in st.session_state:
    st.session_state['tocar_som_salvar'] = False
if 'tocar_som_apagar' not in st.session_state:
    st.session_state['tocar_som_apagar'] = False
if 'auto_grupo' not in st.session_state:
    st.session_state['auto_grupo'] = 1
if 'auto_horario_idx' not in st.session_state:
    st.session_state['auto_horario_idx'] = 0

def reproduzir_som(tipo):
    if tipo == 'sucesso':
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=success-1-6297.mp3"
    elif tipo == 'alerta':
        sound_url = "https://cdn.pixabay.com/download/audio/2021/08/09/audio_0083556434.mp3?filename=error-2-126514.mp3"
    else:
        sound_url = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3?filename=crumpling-paper-1-6240.mp3"
    st.markdown(f"""
        <audio autoplay style="display:none;">
            <source src="{sound_url}" type="audio/mpeg">
        </audio>
    """, unsafe_allow_html=True)

def aplicar_estilo_banca(banca_key, bloqueado=False):
    config = CONFIG_BANCAS.get(banca_key)
    if bloqueado:
        bg_color, text_color, card_bg = "#1a1a1a", "#a0a0a0", "#000000"
    else:
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
        .stAudio {{ display: none; }}
        
        .bola-verde {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #28a745; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-azul {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #17a2b8; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-vermelha {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #dc3545; color: white !important; text-align: center; font-weight: bold; margin: 2px; box-shadow: 2px 2px 4px rgba(0,0,0,0.3); border: 2px solid white; }}
        .bola-cinza {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #555; color: #ccc !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #777; }}
        .bola-25 {{ display: inline-block; width: 40px; height: 40px; line-height: 40px; border-radius: 50%; background-color: white; color: black !important; text-align: center; font-weight: bold; margin: 2px; border: 3px solid #d4af37; box-shadow: 0px 0px 10px #d4af37; }}
        .bola-fantasma {{ display: inline-block; width: 38px; height: 38px; line-height: 38px; border-radius: 50%; background-color: #6f42c1; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; }}
        
        .bola-b {{ display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #17a2b8; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #fff; }}
        .bola-m {{ display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #fd7e14; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #fff; }}
        .bola-a {{ display: inline-block; width: 35px; height: 35px; line-height: 35px; border-radius: 50%; background-color: #dc3545; color: white !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid #fff; }}
        
        .bola-puxada {{ display: inline-block; width: 45px; height: 45px; line-height: 45px; border-radius: 50%; background-color: #ffd700; color: black !important; text-align: center; font-weight: bold; margin: 2px; border: 2px solid white; box-shadow: 0 0 10px rgba(255, 215, 0, 0.5); }}
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

def salvar_na_nuvem(worksheet, numero, horario):
    if worksheet:
        try:
            data_hoje = datetime.now().strftime("%Y-%m-%d")
            worksheet.append_row([int(numero), str(horario), data_hoje])
            return True
        except: return False
    return False

def deletar_ultimo_registro(worksheet):
    if worksheet:
        try:
            valores = worksheet.col_values(1)
            total_linhas = len(valores)
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

def extrair_hora_minuto(texto_hora):
    try:
        partes = texto_hora.split(':')
        return int(partes[0]), int(partes[1])
    except: return 0, 0

def calcular_proximo_horario_real(banca):
    fuso_br = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(fuso_br)
    dia_semana = agora.weekday()
    config = CONFIG_BANCAS[banca]
    lista_str = config['horarios']['dom'] if dia_semana == 6 else config['horarios']['segsab']
    lista_horarios = [h.strip() for h in lista_str.split('🔹')]
    for h in lista_horarios:
        hh, mm = extrair_hora_minuto(h)
        horario_dt = agora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if horario_dt > agora:
            return h, horario_dt
    return "Amanhã", agora + timedelta(days=1)

def calcular_proximo_horario(banca, ultimo_horario):
    if not ultimo_horario: return "Próximo Sorteio"
    fuso_br = pytz.timezone('America/Sao_Paulo')
    dia_semana = datetime.now(fuso_br).weekday()
    config = CONFIG_BANCAS[banca]
    lista_str = config['horarios']['dom'] if dia_semana == 6 else config['horarios']['segsab']
    lista_horarios = [h.strip() for h in lista_str.split('🔹')]
    try:
        indice_atual = lista_horarios.index(ultimo_horario)
        if indice_atual + 1 < len(lista_horarios):
            return f"Palpite para: {lista_horarios[indice_atual + 1]}"
        return "Palpite para: Amanhã/Próximo Dia"
    except: return "Palpite para: Próximo Sorteio"

# --- SCRAPING AVANÇADO ---
def raspar_ultimo_resultado_real(url, banca_key):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code != 200: return None, None, "Erro Site"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        fuso_br = pytz.timezone('America/Sao_Paulo')
        hoje_str = datetime.now(fuso_br).strftime("%d/%m/%Y")
        
        candidatos = [] 
        elementos_data = soup.find_all(string=re.compile(re.escape(hoje_str)))
        
        for elem in elementos_data:
            container = elem.parent
            for _ in range(3): 
                if container:
                    texto_container = container.get_text()
                    match_hora = re.search(r'(\d{2}[:h]\d{2})', texto_container)
                    if match_hora:
                        horario_str = match_hora.group(1).replace('h', ':')
                        tabela = container.find_next('table')
                        if tabela:
                            linhas = tabela.find_all('tr')
                            for linha in linhas:
                                colunas = linha.find_all('td')
                                if len(colunas) >= 3:
                                    premio = colunas[0].get_text().strip()
                                    if '1º' in premio or '1' in premio:
                                        grupo = colunas[2].get_text().strip()
                                        if grupo.isdigit():
                                            candidatos.append((horario_str, int(grupo)))
                                            break 
                        break 
                    container = container.parent
                else:
                    break

        if not candidatos: return None, None, "Data Ausente"
        candidatos.sort(key=lambda x: x[0], reverse=True)
        candidatos_unicos = []
        vistos = set()
        for h, g in candidatos:
            if h not in vistos:
                candidatos_unicos.append((h, g))
                vistos.add(h)
        return candidatos_unicos[0][1], candidatos_unicos[0][0], "Sucesso"
        
    except Exception as e: return None, None, f"Erro: {e}"

# --- RADAR DE VÍCIO ---
def detecting_vicio_repeticao(historico):
    if len(historico) < 10: return False
    repeticoes = 0
    recorte = historico[-15:]
    for i in range(len(recorte)-1):
        if recorte[i] == recorte[i+1]:
            repeticoes += 1
    return repeticoes >= 2

# --- CÁLCULO DE PUXADAS ---
def calcular_puxada_do_ultimo(historico):
    if len(historico) < 2: return None, []
    ultimo = historico[-1]
    seguintes = []
    for i in range(len(historico)-1):
        if historico[i] == ultimo:
            seguintes.append(historico[i+1])
    if not seguintes: return ultimo, []
    contagem = Counter(seguintes)
    total_ocorrencias = len(seguintes)
    rank = contagem.most_common(3)
    puxadas_com_pct = []
    for grupo, freq in rank:
        pct = (freq / total_ocorrencias) * 100
        puxadas_com_pct.append((grupo, pct))
    return ultimo, puxadas_com_pct

def calcular_ranking_forca_completo(historico, banca="PADRAO"):
    if not historico: return []
    hist_reverso = historico[::-1]
    scores = {g: 0 for g in range(1, 26)}
    if banca == "CAMINHODASORTE" or banca == "MONTECAI":
        c_ultra_curto = Counter(hist_reverso[:8])
        for g, f in c_ultra_curto.items(): scores[g] += (f * 4.0)
        c_curto = Counter(hist_reverso[:15])
        for g, f in c_curto.items(): scores[g] += (f * 1.0)
    else:
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

def gerar_palpite_estrategico(historico, banca, modo_crise=False):
    todos_forca = calcular_ranking_forca_completo(historico, banca)
    if modo_crise:
        top8 = todos_forca[:8]
        todos_atrasos = calcular_ranking_atraso_completo(historico)
        top4_atraso = []
        for b in todos_atrasos:
            if b not in top8: top4_atraso.append(b)
            if len(top4_atraso) == 4: break
        return top8 + top4_atraso, []
    top12 = todos_forca[:12]
    vicio = detecting_vicio_repeticao(historico)
    ultimo = historico[-1]
    if vicio and (ultimo not in top12):
        top12.pop() 
        top12.insert(0, ultimo) 
    cob2 = todos_forca[12:14]
    return top12, cob2

def gerar_backtest_e_status(historico, banca):
    if len(historico) < 30: return pd.DataFrame(), False, 0
    derrotas = 0
    resultados = []
    inicio = max(0, len(historico) - 25)
    for i in range(inicio, len(historico)):
        saiu = historico[i]
        passado = historico[:i]
        crise = derrotas >= 2
        p_princ, _ = gerar_palpite_estrategico(passado, banca, crise)
        status = "❌"
        if saiu in p_princ:
            status = "💚"
            derrotas = 0
        else:
            derrotas += 1
        if i >= len(historico) - 5:
            resultados.append({"JOGO": f"#{len(historico)-i}", "SAIU": f"{saiu:02}", "TOP 12": status})
    return pd.DataFrame(resultados[::-1]), derrotas >= 2, derrotas

def gerar_backtest_top17(historico, banca):
    if len(historico) < 30: return pd.DataFrame(), [], False, False, []
    resultados = []
    falha_recente = False
    contagem_derrotas_17 = 0
    
    # AUMENTADO PARA 20 JOGOS
    inicio = max(0, len(historico) - 20)
    
    ranking_bruto_atual = calcular_ranking_forca_completo(historico, banca)
    top12_atual, _ = gerar_palpite_estrategico(historico, banca, modo_crise=False) 
    sobras_atual = [x for x in ranking_bruto_atual if x not in top12_atual]
    top17_atual = top12_atual + sobras_atual[:5]
    zebras_atual = sobras_atual[5:]
    
    for i in range(inicio, len(historico)):
        saiu = historico[i]
        passado = historico[:i]
        top12_da_epoca, _ = gerar_palpite_estrategico(passado, banca, modo_crise=False)
        ranking_bruto_da_epoca = calcular_ranking_forca_completo(passado, banca)
        sobras = [x for x in ranking_bruto_da_epoca if x not in top12_da_epoca]
        top17_da_epoca = top12_da_epoca + sobras[:5]
        status = "❌"
        if saiu in top17_da_epoca:
            status = "💚"
            contagem_derrotas_17 = 0
        else:
            contagem_derrotas_17 += 1
            if i == len(historico) - 1: falha_recente = True
        resultados.append({"JOGO": f"#{len(historico)-i}", "SAIU": f"{saiu:02}", "TOP 17": status})
    modo_inverso = contagem_derrotas_17 >= 3
    return pd.DataFrame(resultados[::-1]), top17_atual, falha_recente, modo_inverso, zebras_atual

# --- ANALISE DE SETORES BMA + 25 COM PORCENTAGEM ---
def analisar_setores_bma_com_maximo(historico):
    if not historico: return {}, {}, [], {}
    
    setor_b = list(range(1, 9))
    setor_m = list(range(9, 17))
    setor_a = list(range(17, 25))
    setor_25 = [25]
    
    recorte_50 = historico[-50:]
    total_50 = len(recorte_50)
    
    def calc_pct(lista_alvo):
        qtd = len([x for x in recorte_50 if x in lista_alvo])
        return (qtd / total_50) * 100 if total_50 > 0 else 0
    
    porcentagens = {
        "BAIXO (01-08)": calc_pct(setor_b),
        "MÉDIO (09-16)": calc_pct(setor_m),
        "ALTO (17-24)": calc_pct(setor_a),
        "CORINGA (25)": calc_pct(setor_25)
    }
    
    def calcular_atrasos(lista_alvo, hist):
        atraso_atual = 0
        max_atraso = 0
        contador_temp = 0
        for x in reversed(hist):
            if x in lista_alvo: break
            atraso_atual += 1
        for x in hist:
            if x not in lista_alvo:
                contador_temp += 1
            else:
                if contador_temp > max_atraso: max_atraso = contador_temp
                contador_temp = 0
        if contador_temp > max_atraso: max_atraso = contador_temp
        return atraso_atual, max_atraso
        
    curr_b, max_b = calcular_atrasos(setor_b, historico)
    curr_m, max_m = calcular_atrasos(setor_m, historico)
    curr_a, max_a = calcular_atrasos(setor_a, historico)
    curr_25, max_25 = calcular_atrasos(setor_25, historico)
    
    dados_atual = {"BAIXO (01-08)": curr_b, "MÉDIO (09-16)": curr_m, "ALTO (17-24)": curr_a, "CORINGA (25)": curr_25}
    dados_maximo = {"BAIXO (01-08)": max_b, "MÉDIO (09-16)": max_m, "ALTO (17-24)": max_a, "CORINGA (25)": max_25}
    
    sequencia_visual = []
    for x in historico[::-1][:10]:
        if x == 25: sigla, classe = "25", "bola-25"
        elif x <= 8: sigla, classe = "B", "bola-b"
        elif x <= 16: sigla, classe = "M", "bola-m"
        else: sigla, classe = "A", "bola-a"
        sequencia_visual.append((sigla, classe))
        
    return dados_atual, dados_maximo, sequencia_visual, porcentagens

# --- DNA FIXO (BUNKER) ---
def analisar_dna_fixo_historico(historico):
    if len(historico) < 50: return [], pd.DataFrame(), 0.0
    contagem_total = Counter(historico)
    top_17_fixo = [g for g, freq in contagem_total.most_common(17)]
    resultados_simulacao = []
    acertos = 0
    recorte_teste = historico[-20:]
    for i, saiu in enumerate(recorte_teste):
        status = "❌"
        if saiu in top_17_fixo:
            status = "💚"
            acertos += 1
        resultados_simulacao.insert(0, {"JOGO": f"Ult-{20-i}", "SAIU": f"{saiu:02}", "BUNKER": status})
    taxa_acerto = (acertos / 20) * 100
    return top_17_fixo, pd.DataFrame(resultados_simulacao), taxa_acerto

# =============================================================================
# --- 4. INTERFACE PRINCIPAL ---
# =============================================================================

if st.session_state['tocar_som_salvar']:
    reproduzir_som('sucesso')
    st.session_state['tocar_som_salvar'] = False

if st.session_state['tocar_som_apagar']:
    reproduzir_som('apagar')
    st.session_state['tocar_som_apagar'] = False

with st.sidebar:
    st.header("🦅 MENU DE JOGO")
    banca_selecionada = st.selectbox("Selecione a Banca:", BANCA_OPCOES)
    
    fuso_br = pytz.timezone('America/Sao_Paulo')
    dia_semana = datetime.now(fuso_br).weekday()
    config_banca = CONFIG_BANCAS[banca_selecionada]
    lista_horarios_str = config_banca['horarios']['dom'] if dia_semana == 6 else config_banca['horarios']['segsab']
    lista_horarios = [h.strip() for h in lista_horarios_str.split('🔹')]
    
    st.markdown("---")
    
    col_import, _ = st.columns([1, 0.1])
    with col_import:
        if st.button("📡 Importar Resultado do Site"):
            with st.spinner("Buscando dados na central..."):
                grp, hor, msg = raspar_ultimo_resultado_real(config_banca['url_site'], banca_selecionada)
                if grp:
                    st.success(f"Encontrado! G{grp:02} às {hor}")
                    st.session_state['auto_grupo'] = grp
                    try:
                        idx_h = lista_horarios.index(hor)
                        st.session_state['auto_horario_idx'] = idx_h
                    except: 
                        st.session_state['auto_horario_idx'] = 0
                else:
                    st.error(f"Não encontrado ou Data antiga ({msg})")
    
    st.write("📝 **Registrar Sorteio**")
    
    novo_horario = st.selectbox("Horário:", lista_horarios, index=st.session_state.get('auto_horario_idx', 0))
    novo_bicho = st.number_input("Grupo:", 1, 25, st.session_state.get('auto_grupo', 1))
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 SALVAR", type="primary"):
            aba = conectar_planilha(banca_selecionada)
            if aba and salvar_na_nuvem(aba, novo_bicho, novo_horario):
                st.session_state['tocar_som_salvar'] = True
                st.toast("Salvo! 🔔", icon="✅")
                time.sleep(0.5)
                st.rerun()
    with col_btn2:
        if st.button("🔄 REBOOT"):
            st.rerun()
            
    with st.expander("🗑️ Área de Perigo"):
        if st.button("APAGAR ÚLTIMO"):
            aba = conectar_planilha(banca_selecionada)
            if aba and deletar_ultimo_registro(aba):
                st.session_state['tocar_som_apagar'] = True
                st.toast("Apagado! 🗑️", icon="🗑️")
                time.sleep(0.5)
                st.rerun()

aba_ativa = conectar_planilha(banca_selecionada)

if aba_ativa:
    historico, ultimo_horario_salvo = carregar_dados(aba_ativa)
    
    if len(historico) > 0:
        
        # CÁLCULOS
        df_back, EM_CRISE, qtd_derrotas = gerar_backtest_e_status(historico, banca_selecionada)
        palpite_p, palpite_cob = gerar_palpite_estrategico(historico, banca_selecionada, EM_CRISE)
        texto_horario_futuro = calcular_proximo_horario(banca_selecionada, ultimo_horario_salvo)
        vicio_ativo = detecting_vicio_repeticao(historico)
        
        # V55/V56 - NOVOS DADOS
        dados_atual, dados_maximo, seq_visual_setores, porcentagens = analisar_setores_bma_com_maximo(historico)
        df_top17, lista_top17, ALERTA_FALHA_17, MODO_INVERSO_ATIVO, zebras = gerar_backtest_top17(historico, banca_selecionada)
        ultimo_bicho, lista_puxadas = calcular_puxada_do_ultimo(historico)
        lista_bunker, df_bunker, taxa_bunker = analisar_dna_fixo_historico(historico)
        
        MODO_BLOQUEIO = False
        if (banca_selecionada == "CAMINHODASORTE" or banca_selecionada == "MONTECAI") and qtd_derrotas >= 3:
            MODO_BLOQUEIO = True
        
        aplicar_estilo_banca(banca_selecionada, bloqueado=MODO_BLOQUEIO)
        config_atual = CONFIG_BANCAS[banca_selecionada]

        col_head1, col_head2, col_head3 = st.columns([1, 2, 1])
        with col_head2:
            st.markdown(f"""
                <div style='text-align: center;'>
                    <img src='{config_atual['logo_url']}' width='100' style='margin-bottom: 10px;'>
                    <h1 style='margin:0; padding:0; font-size: 2.5rem;'>{config_atual['display_name']}</h1>
                </div>
            """, unsafe_allow_html=True)
        st.write("") 

        link = config_atual['url_site']
        site_on, site_tit, _ = verificar_atualizacao_site(link)
        col_mon1, col_mon2 = st.columns([3, 1])
        with col_mon1: 
            info_ultimo = f"Último: Grupo {historico[-1]:02}"
            if ultimo_horario_salvo: info_ultimo += f" ({ultimo_horario_salvo})"
            st.caption(f"📡 {site_tit}  |  🏁 {info_ultimo}")
        with col_mon2: 
            if link: st.link_button("🔗 Abrir Site", link)

        # PAINEL DE CONTROLE (V54 - COM BUNKER)
        with st.expander("📊 Painel de Controle (Local)", expanded=True):
            tab_diag_12, tab_diag_17, tab_bunker = st.tabs(["🔍 Top 12 (Padrão)", "🛡️ Top 17 (Segurança)", "🧬 DNA Fixo (Bunker)"])
            
            with tab_diag_12:
                c_palp1, c_palp2 = st.columns(2)
                with c_palp1:
                    st.write("🔥 **TOP 12 (Principal):**")
                    if vicio_ativo: st.warning("⚠️ Vício detectado")
                    st.code(", ".join([f"{n:02}" for n in palpite_p]), language="text")
                with c_palp2:
                    st.write("❄️ **COBERTURA (2):**")
                    st.code(", ".join([f"{n:02}" for n in palpite_cob]), language="text")
                
                st.write("Diagnóstico Clássico:")
                st.table(df_back) 
                
            with tab_diag_17:
                if MODO_INVERSO_ATIVO:
                    st.error("👻 MODO INVERSO ATIVO! Aposte nas ZEBRAS.")
                    st.code(", ".join([f"{n:02}" for n in zebras]), language="text")
                elif ALERTA_FALHA_17:
                    st.error("🚨 O Top 17 Falhou! Chance de acerto alta.")
                
                st.write("📋 **Lista dos 17 Grupos:**")
                st.code(", ".join([f"{n:02}" for n in lista_top17]), language="text")
                st.table(df_top17)
                
            with tab_bunker:
                st.write(f"### 🧬 DNA Histórico (Bunker)")
                col_b1, col_b2 = st.columns([3, 1])
                with col_b1:
                    st.code(", ".join([f"{n:02}" for n in lista_bunker]), language="text")
                with col_b2:
                    st.metric("Acertos (Ult. 20)", f"{int(taxa_bunker)}%")
                st.caption("Comparativo Bunker (Fixo) vs Realidade Recente:")
                st.table(df_bunker)

        with st.expander("🕒 Grade de Horários da Banca"):
            df_horarios = pd.DataFrame({
                "DIA DA SEMANA": ["Segunda a Sábado", "Domingo"],
                "HORÁRIOS": [config_atual['horarios']['segsab'], config_atual['horarios']['dom']]
            })
            st.table(df_horarios)

        st.markdown("---")

        if MODO_BLOQUEIO:
            st.error(f"⛔ TRAVA DE SEGURANÇA: {qtd_derrotas} Derrotas Seguidas")
            st.markdown("""
            <div style="background-color: #330000; padding: 20px; border-radius: 10px; border: 2px solid red; text-align: center;">
                <h2>NÃO APOSTE AGORA!</h2>
                <p>A banca está muito instável. Aguarde uma vitória virtual.</p>
            </div>
            """, unsafe_allow_html=True)
            st.write("🤖 Palpites de Simulação:")
            st.markdown(html_bolas(palpite_p, "cinza"), unsafe_allow_html=True)
            st.markdown("---")

        # ABAS PRINCIPAIS
        tab_puxadas, tab_setores, tab_graficos = st.tabs(["🧲 Puxadas (Markov)", "🎯 Setores (B/M/A)", "📈 Gráficos"])
        
        with tab_puxadas:
            st.write(f"### 🧲 Quem puxa quem?")
            st.write(f"Análise baseada no último bicho: **Grupo {ultimo_bicho:02}**")
            if lista_puxadas:
                st.markdown("---")
                col_p1, col_p2, col_p3 = st.columns(3)
                cols = [col_p1, col_p2, col_p3]
                for i, (grupo, pct) in enumerate(lista_puxadas):
                    with cols[i]:
                        st.markdown(f"<div style='text-align:center;'><h4>{i+1}º Mais Forte</h4></div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='display:flex;justify-content:center;'><div class='bola-puxada'>{grupo:02}</div></div>", unsafe_allow_html=True)
                        st.progress(int(pct))
                        st.caption(f"Frequência: {int(pct)}%")
            else:
                st.warning("Dados insuficientes para calcular puxada.")

        with tab_setores:
            st.write("### 🎯 Análise de Setores (B.M.A.)")
            st.write("Histórico Recente (⬅️ Mais Novo):")
            html_seq = "<div>"
            for sigla, classe in seq_visual_setores:
                html_seq += f"<div class='{classe}'>{sigla}</div>"
            html_seq += "</div>"
            st.markdown(html_seq, unsafe_allow_html=True)
            st.markdown("---")
            
            c_b, c_m, c_a, c_25 = st.columns(4)
            recomendacoes = []
            
            # Helper de cor para %
            def cor_pct(val): return "red" if val > 40 else "blue" if val < 20 else "green"
            
            with c_b:
                val = dados_atual['BAIXO (01-08)']
                lim = dados_maximo['BAIXO (01-08)']
                pct = porcentagens['BAIXO (01-08)']
                st.metric("BAIXO (01-08)", f"{val}", delta=f"Recorde: {lim}")
                st.markdown(f"**{pct:.0f}%** (50 jogos)", unsafe_allow_html=True)
                if val >= (lim - 1): recomendacoes.append("BAIXO")
                
            with c_m:
                val = dados_atual['MÉDIO (09-16)']
                lim = dados_maximo['MÉDIO (09-16)']
                pct = porcentagens['MÉDIO (09-16)']
                st.metric("MÉDIO (09-16)", f"{val}", delta=f"Recorde: {lim}")
                st.markdown(f"**{pct:.0f}%** (50 jogos)", unsafe_allow_html=True)
                if val >= (lim - 1): recomendacoes.append("MÉDIO")
                
            with c_a:
                val = dados_atual['ALTO (17-24)']
                lim = dados_maximo['ALTO (17-24)']
                pct = porcentagens['ALTO (17-24)']
                st.metric("ALTO (17-24)", f"{val}", delta=f"Recorde: {lim}")
                st.markdown(f"**{pct:.0f}%** (50 jogos)", unsafe_allow_html=True)
                if val >= (lim - 1): recomendacoes.append("ALTO")
                
            with c_25:
                val = dados_atual['CORINGA (25)']
                lim = dados_maximo['CORINGA (25)']
                pct = porcentagens['CORINGA (25)']
                st.metric("VACA (25)", f"{val}", delta=f"Recorde: {lim}")
                st.markdown(f"**{pct:.0f}%** (50 jogos)", unsafe_allow_html=True)
            
            st.markdown("---")
            if recomendacoes:
                st.error(f"🚨 **ALERTA MÁXIMO:** O setor **{' + '.join(recomendacoes)}** está perto do RECORDE HISTÓRICO de atraso!")
            else:
                st.info("Nenhum setor em nível crítico de stress.")

        with tab_graficos:
            st.write("### 🐢 Top Atrasados")
            todos_atrasos = calcular_ranking_atraso_completo(historico)
            atrasos_dict = {}
            total = len(historico)
            for b in todos_atrasos[:12]:
                indices = [i for i, x in enumerate(historico) if x == b]
                val = total - 1 - indices[-1] if indices else total
                atrasos_dict[f"Gr {b:02}"] = val
            st.bar_chart(pd.DataFrame.from_dict(atrasos_dict, orient='index', columns=['Jogos']))
            
            st.write("### 📊 Frequência")
            recentes = historico[-50:] 
            contagem = Counter(recentes)
            df_freq = pd.DataFrame.from_dict(contagem, orient='index', columns=['Vezes'])
            st.bar_chart(df_freq)

    else:
        st.warning("⚠️ Planilha vazia. Adicione o primeiro resultado.")
else:
    st.info("Conectando...")
