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
        blocos = soup.find_all(['h5', 'h4', 'h3']) 
        
        for bloco in blocos:
            texto = bloco.get_text().strip()
            if hoje_str in texto:
                match = re.search(r'\d{2}:\d{2}', texto)
                if match:
                    horario_str = match.group(0)
                    tabela = bloco.find_next('table')
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
        
        if not candidatos: return None, None, "Data Ausente"
        candidatos.sort(key=lambda x: x[0], reverse=True)
        return candidatos[0][1], candidatos[0][0], "Sucesso"
        
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

def analisar_dna_banca(historico, banca):
    if len(historico) < 35: return 0, "Calibrando..."
    acertos = 0
    analise = 25
    for i in range(analise):
        idx = len(historico) - 1 - i
        saiu = historico[idx]
        passado = historico[:idx]
        ranking = calcular_ranking_forca_completo(passado, banca)[:12]
        if saiu in ranking: acertos += 1
    score = (acertos / analise) * 100
    if score >= 65: status = "DISCIPLINADA"
    elif score >= 45: status = "EQUILIBRADA"
    else: status = "CAÓTICA"
    return score, status

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

# --- NOVO: ANALISAR TENDENCIA DE VITORIA/DERROTA (V49) ---
def analisar_tendencia_vitoria(historico, banca):
    """
    Analisa se Vitoria puxa Vitoria ou se Derrota puxa Vitoria.
    """
    if len(historico) < 30: return 0, 0, "Dados insuficientes"
    
    # 1. Gera o status de cada jogo (Green/Red)
    status_lista = []
    # Usamos Top 12 (Padrão) para essa análise
    for i in range(len(historico)-30, len(historico)):
        saiu = historico[i]
        passado = historico[:i]
        palpite, _ = gerar_palpite_estrategico(passado, banca)
        status_lista.append(1 if saiu in palpite else 0) # 1=Green, 0=Red
        
    # 2. Analisa Transições
    vitoria_pos_vitoria = 0
    total_vitorias = 0
    vitoria_pos_derrota = 0
    total_derrotas = 0
    
    for i in range(len(status_lista)-1):
        if status_lista[i] == 1: # Se foi Green
            total_vitorias += 1
            if status_lista[i+1] == 1: # E o proximo foi Green
                vitoria_pos_vitoria += 1
        else: # Se foi Red
            total_derrotas += 1
            if status_lista[i+1] == 1: # E o proximo foi Green
                vitoria_pos_derrota += 1
                
    pct_win_pos_win = (vitoria_pos_vitoria / total_vitorias * 100) if total_vitorias > 0 else 0
    pct_win_pos_loss = (vitoria_pos_derrota / total_derrotas * 100) if total_derrotas > 0 else 0
    
    return pct_win_pos_win, pct_win_pos_loss

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
    inicio = max(0, len(historico) - 5)
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

def analisar_par_impar_neutro(historico):
    if not historico: return None, 0, 0, 0, 0
    hist_validos = [x for x in historico if x != 25]
    if not hist_validos: return "NEUTRO", 0, 0, 0, 0
    ultimo_valido = hist_validos[-1]
    eh_par = (ultimo_valido % 2 == 0)
    tipo_atual = "PAR" if eh_par else "ÍMPAR"
    seq = 0
    for x in reversed(hist_validos):
        if (x % 2 == 0) == eh_par: seq += 1
        else: break
    recorte = hist_validos[-50:]
    qtd_par = len([x for x in recorte if x % 2 == 0])
    qtd_impar = len([x for x in recorte if x % 2 != 0])
    atraso_25 = 0
    for x in reversed(historico):
        if x == 25: break
        atraso_25 += 1
    return tipo_atual, seq, qtd_par, qtd_impar, atraso_25

def analisar_alto_baixo_neutro(historico):
    if not historico: return None, 0, 0, 0, 0
    hist_validos = [x for x in historico if x != 25]
    if not hist_validos: return "NEUTRO", 0, 0, 0, 0
    ultimo_valido = hist_validos[-1]
    eh_baixo = (1 <= ultimo_valido <= 12)
    tipo_atual = "BAIXO" if eh_baixo else "ALTO"
    seq = 0
    for x in reversed(hist_validos):
        x_baixo = (1 <= x <= 12)
        if x_baixo == eh_baixo: seq += 1
        else: break
    recorte = hist_validos[-50:]
    qtd_baixo = len([x for x in recorte if 1 <= x <= 12])
    qtd_alto = len([x for x in recorte if 13 <= x <= 24])
    atraso_25 = 0
    for x in reversed(historico):
        if x == 25: break
        atraso_25 += 1
    return tipo_atual, seq, qtd_baixo, qtd_alto, atraso_25

def gerar_bussola_dia(historico):
    if len(historico) < 10: return "Aguardando dados..."
    recorte = historico[-10:]
    pares = len([x for x in recorte if x%2==0 and x!=25])
    impares = len([x for x in recorte if x%2!=0 and x!=25])
    tend_pi = "PARES" if pares > impares else "ÍMPARES"
    baixos = len([x for x in recorte if 1<=x<=12])
    altos = len([x for x in recorte if 13<=x<=24])
    tend_ab = "BAIXOS" if baixos > altos else "ALTOS"
    return f"Tendência do Dia: **{tend_pi}** e **{tend_ab}** (Base últimos 10 jogos)"

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
        bussola_texto = gerar_bussola_dia(historico)
        vicio_ativo = detecting_vicio_repeticao(historico)
        tipo_pi, seq_pi, t_par, t_impar, atr_25 = analisar_par_impar_neutro(historico)
        tipo_ab, seq_ab, t_baixo, t_alto, _ = analisar_alto_baixo_neutro(historico)
        df_top17, lista_top17, ALERTA_FALHA_17, MODO_INVERSO_ATIVO, zebras = gerar_backtest_top17(historico, banca_selecionada)
        ultimo_bicho, lista_puxadas = calcular_puxada_do_ultimo(historico)
        
        # NOVO: ANALISE TENDENCIA V49
        pct_win_win, pct_loss_win = analisar_tendencia_vitoria(historico, banca_selecionada)
        
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

        st.info(f"🧭 {bussola_texto}")

        link = config_atual['url_site']
        site_on, site_tit, _ = verificar_atualizacao_site(link)
        col_mon1, col_mon2 = st.columns([3, 1])
        with col_mon1: 
            info_ultimo = f"Último: Grupo {historico[-1]:02}"
            if ultimo_horario_salvo: info_ultimo += f" ({ultimo_horario_salvo})"
            st.caption(f"📡 {site_tit}  |  🏁 {info_ultimo}")
        with col_mon2: 
            if link: st.link_button("🔗 Abrir Site", link)

        # PAINEL DE CONTROLE LOCAL (V49 - COM IA DE TENDENCIA)
        with st.expander("📊 Painel de Controle (Local)", expanded=True):
            tab_diag_12, tab_diag_17 = st.tabs(["🔍 Top 12 (Padrão)", "🛡️ Top 17 (Segurança)"])
            
            with tab_diag_12:
                # EXIBIÇÃO DA IA DE TENDÊNCIA
                c_ia1, c_ia2 = st.columns(2)
                with c_ia1:
                    st.metric("🏄 Chance de Surf (Win puxa Win)", f"{int(pct_win_win)}%")
                    if pct_win_win > 50: st.caption("👉 **DICA:** Se o último foi Green, jogue novamente!")
                    else: st.caption("Cuidado: A banca costuma alternar.")
                
                with c_ia2:
                    st.metric("♻️ Chance de Recuperação (Loss puxa Win)", f"{int(pct_loss_win)}%")
                    if pct_loss_win < 30: st.caption("⛔ **ALERTA:** Não faça Gale! Derrotas vêm em bloco aqui.")
                    else: st.caption("Padrão normal de recuperação.")
                
                st.markdown("---")
                st.write("Diagnóstico Clássico:")
                st.table(df_back) 
                
            with tab_diag_17:
                if MODO_INVERSO_ATIVO:
                    st.markdown("""
                    <div style="background-color: #6f42c1; padding: 15px; border-radius: 10px; text-align: center; border: 2px solid white;">
                        <h2>👻 MODO CAÇA-FANTASMAS ATIVO!</h2>
                        <p>A banca <b>INVERTEU A LÓGICA</b> (3+ derrotas no Top 17).</p>
                        <p>Não jogue no Top 17 agora. <b>Aposte nas ZEBRAS (Bottom 8).</b></p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.write("👻 **ZEBRAS SUGERIDAS (Bottom 8):**")
                    st.markdown(html_bolas(zebras, "fantasma"), unsafe_allow_html=True)
                    st.code(", ".join([f"{n:02}" for n in zebras]), language="text")
                    
                elif ALERTA_FALHA_17:
                    st.error("🚨 **OPORTUNIDADE RARA: O Top 17 Falhou!** A chance de acerto agora é muito alta.")
                    st.write("📋 **Lista dos 17 Grupos para jogar:**")
                    st.code(", ".join([f"{n:02}" for n in lista_top17]), language="text")
                else:
                    st.success("✅ Top 17 operando normalmente.")
                    st.write("📋 **Lista dos 17 Grupos para jogar:**")
                    st.code(", ".join([f"{n:02}" for n in lista_top17]), language="text")
                
                st.table(df_top17)

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

        tab_palpites, tab_puxadas, tab_parimpar, tab_altobaixo, tab_graficos = st.tabs(["🏠 Palpites", "🧲 Puxadas (Markov)", "⚖️ Par/Ímpar", "📏 Alto/Baixo", "📈 Gráficos"])

        with tab_palpites:
            if MODO_BLOQUEIO:
                st.info("👀 Modo Simulação Ativo. Veja os palpites cinzas acima.")
            else:
                if EM_CRISE:
                    st.error(f"🚨 MODO CRISE - {texto_horario_futuro}")
                    st.markdown(html_bolas(palpite_p, "vermelha"), unsafe_allow_html=True)
                    st.code(", ".join([f"{n:02}" for n in palpite_p]), language="text")
                else:
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        if vicio_ativo:
                            st.warning("⚠️ RADAR DE VÍCIO ATIVADO! (Repetições detectadas)")
                        st.success(f"🔥 TOP 12 - {texto_horario_futuro}")
                        st.markdown(html_bolas(palpite_p, "verde"), unsafe_allow_html=True)
                        st.code(", ".join([f"{n:02}" for n in palpite_p]), language="text")
                    with c2:
                        st.info("❄️ COB (2)")
                        st.markdown(html_bolas(palpite_cob, "azul"), unsafe_allow_html=True)
                        st.code(", ".join([f"{n:02}" for n in palpite_cob]), language="text")
        
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

        with tab_parimpar:
            st.write("### 🐮 Fator 25 (Neutro)")
            col_v1, col_v2 = st.columns([1, 3])
            with col_v1: st.markdown(f"<div class='bola-25'>25</div>", unsafe_allow_html=True)
            with col_v2:
                if atr_25 == 0: st.warning("⚠️ O 25 ACABOU DE SAIR!")
                elif atr_25 >= 15: st.success(f"🚨 **ATRASADO HÁ {atr_25} JOGOS!**")
                else: st.info(f"Atraso normal: {atr_25}")
            
            st.markdown("---")
            st.write("### ⚖️ Balança P/I (Sem o 25)")
            col_pi1, col_pi2 = st.columns(2)
            total_validos = t_par + t_impar if (t_par + t_impar) > 0 else 1
            pct_par = (t_par/total_validos)*100
            
            col_pi1.metric("Pares", f"{t_par}", delta=f"{pct_par:.0f}%")
            col_pi2.metric("Ímpares", f"{t_impar}", delta=f"{(100-pct_par):.0f}%")
            
            cor_alerta = "green"
            texto_alerta = "Equilibrado"
            sugestao = "Aguarde..."
            if pct_par < 40:
                sugestao = "📈 Desequilíbrio: Jogue PAR"
                cor_alerta = "orange"
                texto_alerta = "Chance %"
            elif pct_par > 60:
                sugestao = "📈 Desequilíbrio: Jogue ÍMPAR"
                cor_alerta = "orange"
                texto_alerta = "Chance %"
            if seq_pi >= 4:
                cor_alerta = "red"
                texto_alerta = f"⚠️ ALERTA: {seq_pi} {tipo_pi}ES SEGUIDOS!"
                oposto = 'ÍMPAR' if tipo_pi == 'PAR' else 'PAR'
                sugestao = f"👉 Dica: Aposte no **{oposto}**"

            st.markdown(f"<h3 style='color:{cor_alerta}'>{texto_alerta}</h3>", unsafe_allow_html=True)
            st.info(sugestao)
            
            st.write("Histórico:")
            html_seq = "<div>"
            for x in historico[::-1][:12]:
                if x == 25:
                    txt, cor_b, cor_txt, borda = "25", "white", "black", "3px solid #d4af37"
                else:
                    txt = "P" if x%2==0 else "I"
                    cor_b = "#007bff" if txt=="P" else "#ffc107"
                    cor_txt = "#000" if txt=="I" else "#fff"
                    borda = "none"
                html_seq += f"<span style='display:inline-block;width:30px;height:30px;line-height:30px;border-radius:50%;background-color:{cor_b};color:{cor_txt};text-align:center;margin:2px;font-weight:bold;border:{borda}'>{txt}</span>"
            html_seq += "</div>"
            st.markdown(html_seq, unsafe_allow_html=True)

        with tab_altobaixo:
            st.write("### 📏 Balança A/B (Sem o 25)")
            col_ab1, col_ab2 = st.columns(2)
            tot_v_ab = t_baixo + t_alto if (t_baixo + t_alto) > 0 else 1
            pct_baixo = (t_baixo/tot_v_ab)*100
            col_ab1.metric("Baixos", f"{t_baixo}", delta=f"{pct_baixo:.0f}%")
            col_ab2.metric("Altos", f"{t_alto}", delta=f"{(100-pct_baixo):.0f}%")
            
            cor_alerta_ab = "green"
            texto_alerta_ab = "Equilibrado"
            sugestao_ab = "Aguarde..."
            if pct_baixo < 40:
                sugestao_ab = "📈 Desequilíbrio: Jogue BAIXO"
                cor_alerta_ab = "orange"
                texto_alerta_ab = "Chance %"
            elif pct_baixo > 60:
                sugestao_ab = "📈 Desequilíbrio: Jogue ALTO"
                cor_alerta_ab = "orange"
                texto_alerta_ab = "Chance %"
            if seq_ab >= 4:
                cor_alerta_ab = "red"
                texto_alerta_ab = f"⚠️ ALERTA: {seq_ab} {tipo_ab}OS SEGUIDOS!"
                oposto = 'ALTO' if tipo_ab == 'BAIXO' else 'BAIXO'
                sugestao_ab = f"👉 Dica: Aposte no **{oposto}**"
            
            st.markdown(f"<h3 style='color:{cor_alerta_ab}'>{texto_alerta_ab}</h3>", unsafe_allow_html=True)
            st.info(sugestao_ab)
            
            st.write("Histórico:")
            html_seq_ab = "<div>"
            for x in historico[::-1][:12]:
                if x == 25:
                    txt, cor_b, cor_txt, borda = "25", "white", "black", "3px solid #d4af37"
                else:
                    is_low = (1 <= x <= 12)
                    txt = "B" if is_low else "A"
                    cor_b = "#17a2b8" if is_low else "#fd7e14"
                    cor_txt = "white"
                    borda = "none"
                html_seq_ab += f"<span style='display:inline-block;width:30px;height:30px;line-height:30px;border-radius:50%;background-color:{cor_b};color:{cor_txt};text-align:center;margin:2px;font-weight:bold;border:{borda}'>{txt}</span>"
            html_seq_ab += "</div>"
            st.markdown(html_seq_ab, unsafe_allow_html=True)

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
